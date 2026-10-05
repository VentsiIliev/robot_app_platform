import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from src.engine.updates.config import UpdateConfig, default_config_path, default_install_root
from src.engine.updates.updater import PlatformUpdater

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("platform_release_targets", ROOT / "packaging/platform/targets.py")
targets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(targets)


class ReleaseTargetTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        os_patch = patch("platform.freedesktop_os_release", return_value={"ID": "ubuntu", "VERSION_ID": "24.04"})
        os_patch.start()
        self.addCleanup(os_patch.stop)

    def archive(self, target_name, version="1.0.0", *, override=None, factory=None):
        target = targets.load_target(target_name)
        manifest = {"format": 2, "product": target["product"], "version": version,
                    "architecture": platform.machine(), "os": "ubuntu-24.04", "storage_schema": 1,
                    **{k: target[k] for k in ("robot_system", "profile", "storage_system", "executable")}}
        manifest.update(override or {})
        marker = dict(target, **{k: manifest[k] for k in ("robot_system", "profile", "storage_system", "executable")})
        startup = {"robot_system": manifest["robot_system"], "supported_robot_systems": [manifest["robot_system"]]}
        seed = {"product": target["product"], "enabled": False,
                "repository_url": f"https://{target_name}.example/releases/", "public_key": None}
        files = {"platform/installation/remote-support/install.sh": b"#!/bin/sh\nexit 0\n",
                 "platform/installation/remote-support/install_pl_remote_support.sh": b"#!/bin/sh\nexit 0\n",
                 "manifest.json": json.dumps(manifest).encode(),
                 f"platform/{target['executable']}": b"#!/bin/sh\nexit 0\n",
                 "platform/_internal/config/release-target.json": json.dumps(marker).encode(),
                 "platform/_internal/config/platform.json": json.dumps(startup).encode(),
                 f"platform/_internal/config/update-source/{manifest['robot_system']}.json": json.dumps(seed).encode()}
        if factory is not None:
            files["platform/_internal/config/factory-defaults.json"] = json.dumps(factory).encode()
        archive = self.directory / f"{target_name}-{version}.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            for name, content in files.items():
                member = tarfile.TarInfo(name)
                member.size = len(content)
                member.mode = 0o755 if name == f"platform/{target['executable']}" else 0o644
                bundle.addfile(member, io.BytesIO(content))
        return archive

    def test_each_target_has_a_unique_product_and_valid_bootstrap_provider(self):
        from src.bootstrap.startup_config import load_startup_config, load_bootstrap_provider
        products = set()
        for name in json.loads(targets.CATALOG.read_text()):
            with self.subTest(target=name):
                target = targets.prepare_target(name, self.directory / name)
                self.assertNotIn(target["product"], products)
                products.add(target["product"])
                config = load_startup_config(self.directory / name / "platform.json")
                provider = load_bootstrap_provider(config)
                self.assertEqual((name,), config.supported_robot_systems)
                self.assertIn(provider.system_class.__module__.split(".")[2], target["packages"])

    def test_dedicated_configuration_and_installation_paths_do_not_collide(self):
        catalog = json.loads(targets.CATALOG.read_text())
        with patch("pathlib.Path.home", return_value=self.directory), patch.dict(os.environ, {}, clear=True):
            paths = [default_config_path(item["product"]) for item in catalog.values()]
            roots = [default_install_root(item["product"]) for item in catalog.values()]
        self.assertEqual(len(catalog), len(set(paths)))
        self.assertEqual(len(catalog), len(set(roots)))
        self.assertTrue(all(path.name == "updates.json" for path in paths))

    def test_each_target_has_its_own_matching_source_configuration(self):
        repositories = set()
        for name, target in json.loads(targets.CATALOG.read_text()).items():
            with self.subTest(target=name):
                source = json.loads((ROOT / "config/update_sources" / f"{name}.json").read_text())
                self.assertEqual(target["product"], source["product"])
                self.assertNotIn(source["repository_url"], repositories)
                repositories.add(source["repository_url"])
                self.assertFalse(source["enabled"])

    def test_shared_editor_can_load_without_the_paint_package(self):
        script = (
            "import sys; sys.modules['src.robot_systems.paint'] = None; "
            "from src.applications.workpiece_editor.editor_core.config import SegmentEditorConfig"
        )
        subprocess.run([str(ROOT / ".venv/bin/python"), "-c", script],
                       cwd=ROOT, check=True, capture_output=True)

    def test_legacy_paint_paths_are_preserved_when_already_installed(self):
        legacy_config = self.directory / ".config/robot-platform/updates.json"
        legacy_config.parent.mkdir(parents=True)
        legacy_config.write_text("{}")
        legacy_data = self.directory / ".local/share/robot-platform/data"
        legacy_data.mkdir(parents=True)
        with patch("pathlib.Path.home", return_value=self.directory), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(legacy_config, default_config_path("paint-robot"))
            self.assertEqual(legacy_data.parent, default_install_root("paint-robot"))
            self.assertNotEqual(legacy_config, default_config_path("paint-tray-dry-robot"))

    def test_tray_install_rejects_an_automatic_dryer_release(self):
        root = self.directory / "tray"
        updater = PlatformUpdater(UpdateConfig(root, "", None, product="paint-tray-dry-robot"))
        updater.stage_local(self.archive("paint_tray_dry"))
        updater.queue()
        updater.apply_pending()
        with self.assertRaises(ValueError):
            updater.stage_local(self.archive("paint_auto_dry", "1.1.0"))
        self.assertEqual("tray_dryer", updater.installed()["profile"])
        with self.assertRaises(ValueError):
            PlatformUpdater(UpdateConfig(root, "https://other.example/", None, product="paint-auto-dry-robot"))

    def test_same_product_with_wrong_profile_is_rejected(self):
        updater = PlatformUpdater(UpdateConfig(self.directory / "tray", "", None, product="paint-tray-dry-robot"))
        updater.stage_local(self.archive("paint_tray_dry"))
        updater.queue()
        updater.apply_pending()
        with self.assertRaisesRegex(ValueError, "another robot system/profile"):
            updater.stage_local(self.archive("paint_tray_dry", "1.1.0", override={"profile": "automatic_dryer"}))

    def test_separate_products_can_use_the_same_version_and_different_repositories(self):
        for name in ("paint_tray_dry", "paint_auto_dry", "glue", "twin_robot"):
            target = targets.load_target(name)
            updater = PlatformUpdater(UpdateConfig(self.directory / name, f"https://{name}.example/", None, product=target["product"]))
            updater.stage_local(self.archive(name))
            updater.queue()
            updater.apply_pending()
            self.assertEqual("1.0.0", updater.installed()["version"])
            self.assertEqual(target["product"], updater.installed()["product"])

    def test_installer_creates_each_products_source_file_and_preserves_it(self):
        manager = ROOT / "packaging/platform/manage.py"
        fake_bin = self.directory / "bin"
        fake_bin.mkdir()
        fake_sudo = fake_bin / "sudo"
        fake_sudo.write_text('#!/bin/sh\nexec "$@"\n')
        fake_sudo.chmod(0o755)
        environment = dict(os.environ, PYTHONPATH="", PATH=str(fake_bin) + os.pathsep + os.environ['PATH'], SUDO_USER="ilv")
        for name in ("paint_tray_dry", "paint_auto_dry", "glue", "twin_robot"):
            config = self.directory / name / "updates.json"
            root = self.directory / name / "installed"
            archive = self.archive(name)
            args = ["/usr/bin/python3", str(manager), "--config", str(config), "install", str(archive), "--root", str(root)]
            subprocess.run(args, check=True, capture_output=True, env=environment, cwd="/tmp")
            raw = json.loads(config.read_text())
            self.assertEqual(f"https://{name}.example/releases/", raw["repository_url"])
            raw["repository_url"] = f"https://custom-{name}.example/"
            config.write_text(json.dumps(raw))
            before = config.read_bytes()
            subprocess.run(args, check=True, capture_output=True, env=environment, cwd="/tmp")
            self.assertEqual(before, config.read_bytes())
            # Installed helpers find their own dedicated file without --config.
            subprocess.run(["/usr/bin/python3", str(root / "tools/manage.py"), "recover"], check=True, capture_output=True, env=environment, cwd="/tmp")

    def test_release_builder_rejects_a_bundle_for_another_profile(self):
        bundle = self.directory / "wrong-bundle"
        marker = bundle / "_internal/config/release-target.json"
        marker.parent.mkdir(parents=True)
        marker.write_text(json.dumps(targets.load_target("paint_tray_dry")))
        (bundle / "paint-auto-dry-robot").write_text("wrong profile")
        result = subprocess.run(["/usr/bin/python3", str(ROOT / "packaging/platform/build_release.py"), "paint_auto_dry", "1.0.0", "--bundle", str(bundle), "--output", str(self.directory / "output")], capture_output=True, text=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Bundle identity does not match", result.stderr)
        self.assertFalse((self.directory / "output").exists())

    def test_activation_seeds_factory_files_without_replacing_existing_settings(self):
        factory = json.loads((ROOT / "config/factory_defaults/paint_tray_dry.json").read_text())
        updater = PlatformUpdater(UpdateConfig(self.directory / "tray", "", None, product="paint-tray-dry-robot"))
        settings = updater.data / "paint/profiles/tray_dryer/storage/settings"
        saved = settings / "hardware/modbus.json"
        saved.parent.mkdir(parents=True)
        saved.write_text('{"port": "operator-port", "baudrate": 9600}')
        before = saved.read_bytes()
        updater.stage_local(self.archive("paint_tray_dry", factory=factory))
        updater.queue()
        updater.apply_pending()
        self.assertEqual(before, saved.read_bytes())
        devices = settings / "hardware/peripherals.json"
        self.assertIn("tray_fan", json.loads(devices.read_text()))
        devices.write_text('{"operator_device": {"enabled": false}}')
        before_devices = devices.read_bytes()
        updater.stage_local(self.archive("paint_tray_dry", "1.1.0", factory=factory))
        updater.queue()
        updater.apply_pending()
        self.assertEqual(before, saved.read_bytes())
        self.assertEqual(before_devices, devices.read_bytes())


if __name__ == "__main__":
    unittest.main()
