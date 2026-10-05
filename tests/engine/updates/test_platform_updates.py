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

from src.engine.updates.config import UpdateConfig
from src.engine.updates.files import atomic_json, lock
from src.engine.updates.migrations import migrate
from src.engine.updates.paths import system_path
from src.engine.updates.releases import extract_release
from src.engine.updates.updater import PlatformUpdater


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.root = self.directory / "installed"
        self.updater = PlatformUpdater(UpdateConfig(self.root, "https://server.example/releases/", None))
        self.os_patch = patch("platform.freedesktop_os_release", return_value={"ID": "ubuntu", "VERSION_ID": "24.04"})
        self.os_patch.start()
        self.addCleanup(self.os_patch.stop)

    def release(self, version, schema=1, migrations=None):
        manifest = {"format": 1, "product": "paint-robot", "version": version,
                    "os": "ubuntu-24.04", "architecture": platform.machine(), "storage_schema": schema}
        archive = self.directory / f"{version}.tar.gz"
        files = {"manifest.json": json.dumps(manifest).encode(), "platform/paint-robot": b"#!/bin/sh\nexit 0\n"}
        for number, operations in (migrations or {}).items():
            files[f"migrations/{number}.json"] = json.dumps(operations).encode()
        with tarfile.open(archive, "w:gz") as bundle:
            for name, content in files.items():
                member = tarfile.TarInfo(name)
                member.size = len(content)
                member.mode = 0o755 if name.endswith("paint-robot") else 0o644
                bundle.addfile(member, io.BytesIO(content))
        return archive

    def install(self, version="1.0.0"):
        self.updater.stage_local(self.release(version))
        self.updater.queue()
        self.updater.apply_pending()

    def seed(self):
        target = self.updater.data / "paint/storage/settings/custom.json"
        atomic_json(target, {"speed": 35, "obsolete": 9, "unknown": {"custom": "keep"}})
        workpiece = self.updater.data / "paint/storage/workpieces/part.bin"
        workpiece.parent.mkdir(parents=True)
        workpiece.write_bytes(b"machine-specific-workpiece")
        return target, workpiece

    def test_update_preserves_every_unmodified_file_byte_for_byte(self):
        self.install()
        self.seed()
        before = {str(p.relative_to(self.updater.data)): p.read_bytes() for p in self.updater.data.rglob("*") if p.is_file()}
        self.updater.stage_local(self.release("1.1.0"))
        self.updater.queue()
        self.assertTrue(self.updater.apply_pending())
        after = {str(p.relative_to(self.updater.data)): p.read_bytes() for p in self.updater.data.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual("1.1.0", self.updater.installed()["version"])

    def test_explicit_migrations_preserve_values_unknown_fields_and_workpieces(self):
        self.install()
        target, workpiece = self.seed()
        operations = [
            {"file": "paint/storage/settings/custom.json", "action": "add", "path": ["speed"], "value": 99},
            {"file": "paint/storage/settings/custom.json", "action": "add", "path": ["retries"], "value": 3},
            {"file": "paint/storage/settings/custom.json", "action": "remove", "path": ["obsolete"]},
            {"file": "paint/storage/settings/custom.json", "action": "rename", "path": ["speed"], "to": "velocity"},
        ]
        self.updater.stage_local(self.release("1.1.0", 2, {2: operations}))
        self.updater.queue()
        self.updater.apply_pending()
        self.assertEqual({"velocity": 35, "retries": 3, "unknown": {"custom": "keep"}}, json.loads(target.read_text()))
        self.assertEqual(b"machine-specific-workpiece", workpiece.read_bytes())

    def test_failed_migration_leaves_current_release_and_storage_unchanged(self):
        self.install()
        target, _ = self.seed()
        before = target.read_bytes()
        self.updater.stage_local(self.release("1.1.0", 2))
        self.updater.queue()
        with self.assertRaises(FileNotFoundError):
            self.updater.apply_pending()
        self.assertEqual(before, target.read_bytes())
        self.assertEqual("1.0.0", self.updater.installed()["version"])

    def test_runtime_lock_blocks_activation(self):
        self.install()
        self.updater.stage_local(self.release("1.1.0"))
        self.updater.queue()
        with lock(self.updater.state / "runtime.lock", shared=True):
            with self.assertRaises(RuntimeError):
                self.updater.apply_pending()
        self.assertEqual("1.0.0", self.updater.installed()["version"])

    def test_failure_after_data_swap_restores_data_and_release(self):
        self.install()
        target, _ = self.seed()
        before = target.read_bytes()
        self.updater.stage_local(self.release("1.1.0"))
        self.updater.queue()
        pointer = self.updater._pointer
        def fail_new(version):
            if version == "1.1.0":
                raise OSError("simulated activation failure")
            pointer(version)
        with patch.object(self.updater, "_pointer", side_effect=fail_new):
            with self.assertRaises(OSError):
                self.updater.apply_pending()
        self.assertEqual(before, target.read_bytes())
        self.assertEqual("1.0.0", self.updater.installed()["version"])
        self.assertFalse((self.updater.state / "transaction.json").exists())

    def test_recover_after_interrupted_activation(self):
        self.install()
        target, _ = self.seed()
        self.updater.stage_local(self.release("1.1.0"))
        backup = self.root / "backups/crash"
        backup.parent.mkdir(exist_ok=True)
        atomic_json(self.updater.state / "transaction.json", {"previous": "1.0.0", "backup": "crash"})
        os.rename(self.updater.data, backup)
        self.updater.data.mkdir()
        self.updater._pointer("1.1.0")
        self.updater.recover()
        self.assertEqual(35, json.loads(target.read_text())["speed"])
        self.assertEqual("1.0.0", self.updater.installed()["version"])

    def test_rollback_restores_old_schema_and_preserves_post_update_snapshot(self):
        self.install()
        target, _ = self.seed()
        self.updater.stage_local(self.release("1.1.0"))
        self.updater.queue()
        self.updater.apply_pending()
        atomic_json(target, {"speed": 77})
        self.updater.rollback()
        self.assertEqual(35, json.loads(target.read_text())["speed"])
        self.assertEqual("1.0.0", self.updater.installed()["version"])
        self.assertTrue(any(p.read_text().find('77') >= 0 for p in (self.root / "backups").rglob("custom.json")))

    def test_reject_version_reuse(self):
        self.install()
        with self.assertRaises(ValueError):
            self.updater.stage_local(self.release("1.0.0"))

    def test_reject_wrong_product(self):
        archive = self.release("1.0.0")
        updater = PlatformUpdater(UpdateConfig(self.root, "", None, product="glue-robot"))
        with self.assertRaises(ValueError):
            updater.stage_local(archive)
        self.assertFalse((self.root / "current").exists())

    def test_archive_traversal_links_and_storage_are_rejected(self):
        for name, kind in (("../outside", tarfile.REGTYPE), ("platform/link", tarfile.SYMTYPE),
                           ("platform/_internal/src/robot_systems/paint/storage/users/users.csv", tarfile.REGTYPE)):
            with self.subTest(name=name):
                archive = self.directory / "unsafe.tar.gz"
                with tarfile.open(archive, "w:gz") as bundle:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.linkname = "/tmp/outside"
                    bundle.addfile(member, io.BytesIO(b""))
                with self.assertRaises(ValueError):
                    extract_release(archive, self.directory / "extracted", 1000)
                self.assertFalse((self.directory / "extracted").exists())

    def test_archive_size_limit(self):
        with self.assertRaises(ValueError):
            extract_release(self.release("1.0.0"), self.directory / "extracted", 1)

    def test_configuration_rejects_numeric_public_key_with_clear_error(self):
        config = self.directory / "updates.json"
        atomic_json(config, {"install_root": str(self.root), "enabled": False, "public_key": 123})
        with self.assertRaisesRegex(ValueError, "public_key must be a quoted file path or null"):
            UpdateConfig.load(config)

    def test_local_feed_checks_stages_and_preserves_settings_without_a_key(self):
        self.install()
        settings, workpiece = self.seed()
        before = settings.read_bytes()
        feed = self.directory / "feed/stable"
        feed.mkdir(parents=True)
        archive = self.release("1.1.0")
        with tarfile.open(archive) as bundle:
            manifest = json.load(bundle.extractfile("manifest.json"))
        manifest.update(channel="stable", archive=archive.name, sha256=self.updater._digest(archive))
        archive.rename(feed / archive.name)
        atomic_json(feed / "latest.json", manifest)
        path = self.directory / "updates.json"
        for folder in (feed.parent, feed):
            atomic_json(path, {"enabled": True, "install_root": str(self.root),
                               "repository_url": str(folder), "public_key": None})
            updater = PlatformUpdater(UpdateConfig.load(path))
            self.assertTrue(updater.check()["available"])
        updater.stage_latest()
        updater.queue()
        updater.apply_pending()
        self.assertFalse(updater.check()["available"])
        self.assertEqual(before, settings.read_bytes())
        self.assertEqual(b"machine-specific-workpiece", workpiece.read_bytes())

    def test_local_feed_reports_missing_manifest_and_rejects_file_escape(self):
        feed = self.directory / "feed/stable"
        feed.mkdir(parents=True)
        updater = PlatformUpdater(UpdateConfig(self.root, str(feed), None, enabled=True))
        with self.assertRaisesRegex(ValueError, "Local release file is missing"):
            updater.check()
        outside = self.directory / "outside.json"
        outside.write_text('{}')
        (feed / 'latest.json').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "must remain in the configured feed"):
            updater.check()

    def test_local_feed_enforces_checksum_before_staging(self):
        feed = self.directory / "feed/stable"
        feed.mkdir(parents=True)
        archive = self.release("1.0.0")
        with tarfile.open(archive) as bundle:
            manifest = json.load(bundle.extractfile("manifest.json"))
        manifest.update(channel="stable", archive=archive.name, sha256="0" * 64)
        archive.rename(feed / archive.name)
        atomic_json(feed / "latest.json", manifest)
        updater = PlatformUpdater(UpdateConfig(self.root, str(feed), None, enabled=True))
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            updater.stage_latest()
        self.assertIsNone(updater.installed())

    def test_configuration_rejects_http_missing_key_and_relative_root(self):
        path = self.directory / "updates.json"
        for payload in ({"install_root": str(self.root), "enabled": True, "repository_url": "http://server/"},
                        {"install_root": str(self.root), "enabled": True, "repository_url": "https://server/"},
                        {"install_root": "relative"}):
            atomic_json(path, payload)
            with self.assertRaises(ValueError):
                UpdateConfig.load(path)

    def test_signed_manifest_verification_and_tampering(self):
        private = self.directory / "private.pem"
        public = self.directory / "public.pem"
        subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(private)], check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)], check=True, capture_output=True)
        self.updater = PlatformUpdater(UpdateConfig(self.root, "https://server/releases/", public, enabled=True))
        archive = self.release("1.0.0")
        with tarfile.open(archive) as bundle:
            manifest = json.load(bundle.extractfile("manifest.json"))
        manifest.update(channel="stable", archive=archive.name, sha256=self.updater._digest(archive))
        source = self.directory / "latest.json"
        source.write_text(json.dumps(manifest))
        signature = Path(str(source) + ".sig")
        subprocess.run(["openssl", "dgst", "-sha256", "-sign", str(private), "-out", str(signature), str(source)], check=True)
        def fetch(url, target, limit):
            target.write_bytes((signature if url.endswith(".sig") else source).read_bytes())
        with patch.object(self.updater, "_fetch", side_effect=fetch):
            self.assertTrue(self.updater.check()["available"])
            source.write_text(source.read_text().replace('1.0.0', '9.0.0'))
            with self.assertRaises(subprocess.CalledProcessError):
                self.updater.check()

    def test_installer_imports_profiles_and_preserves_configuration_on_reinstall(self):
        manager = Path("packaging/platform/manage.py").resolve()
        source = self.directory / "old-paint"
        atomic_json(source / "storage/settings/custom.json", {"speed": 35})
        atomic_json(source / "profiles/tray_dryer/storage/settings/custom.json", {"speed": 17})
        config = self.directory / "updates.json"
        archive = self.release("1.0.0")
        environment = dict(os.environ, PYTHONPATH="")
        arguments = ["/usr/bin/python3", str(manager), "--config", str(config), "install", str(archive), "--root", str(self.root)]
        subprocess.run(arguments + ["--storage-from", str(source)], check=True, capture_output=True, env=environment, cwd="/tmp")
        self.assertEqual(35, json.loads((self.updater.data / "paint/storage/settings/custom.json").read_text())["speed"])
        self.assertEqual(17, json.loads((self.updater.data / "paint/profiles/tray_dryer/storage/settings/custom.json").read_text())["speed"])
        raw = json.loads(config.read_text())
        raw["repository_url"] = "https://my-server.example/platform/"
        atomic_json(config, raw)
        before = config.read_bytes()
        subprocess.run(arguments, check=True, capture_output=True, env=environment, cwd="/tmp")
        self.assertEqual(before, config.read_bytes())
        subprocess.run(["/usr/bin/python3", str(self.root / "tools/manage.py"), "--config", str(config), "launch"], check=True, capture_output=True, env=environment, cwd="/tmp")
        with self.assertRaises(subprocess.CalledProcessError):
            subprocess.run(arguments + ["--storage-from", str(source)], check=True, capture_output=True, env=environment, cwd="/tmp")

    def test_candidate_self_test_failure_does_not_stage_or_replace_release(self):
        self.install()
        target, _ = self.seed()
        original = target.read_bytes()
        archive = self.release("1.1.0")
        with patch("src.engine.updates.updater.subprocess.run", side_effect=subprocess.CalledProcessError(1, "self-test")):
            with self.assertRaises(subprocess.CalledProcessError):
                self.updater.stage_local(archive)
        self.assertFalse((self.root / "releases/1.1.0").exists())
        self.assertEqual("1.0.0", self.updater.installed()["version"])
        self.assertEqual(original, target.read_bytes())

    def test_settings_factory_reads_existing_external_profile_settings(self):
        from tests.engine.repositories.test_settings_service_factory import _Ser, SettingsIDTestEnum
        from src.engine.repositories.settings_service_factory import build_from_specs
        from src.shared_contracts.declarations import SettingsSpec
        class Fake:
            __module__ = "src.robot_systems.paint.paint_robot_system"
        root = self.directory / "data"
        atomic_json(root / "paint/profiles/tray_dryer/storage/settings/config.json", {"value": "custom-machine-value"})
        with patch.dict(os.environ, {"ROBOT_PLATFORM_DATA_ROOT": str(root)}):
            service = build_from_specs([SettingsSpec(SettingsIDTestEnum.A, _Ser(), "config.json")], "profiles/tray_dryer/storage/settings", Fake)
            self.assertEqual("custom-machine-value", service.get(SettingsIDTestEnum.A).value)

    def test_profiles_use_external_root_without_collisions(self):
        class Fake:
            __module__ = "src.robot_systems.paint.paint_robot_system"
            @classmethod
            def package_root(cls): return "/source/paint"
        with patch.dict(os.environ, {"ROBOT_PLATFORM_DATA_ROOT": str(self.directory / "data")}):
            result = system_path(Fake, "profiles/tray_dryer/storage/settings")
            self.assertEqual(str(self.directory / "data/paint/profiles/tray_dryer/storage/settings"), result)
            with self.assertRaises(ValueError): system_path(Fake, "../escape")
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual("/source/paint/storage", system_path(Fake, "storage"))


if __name__ == "__main__":
    unittest.main()
