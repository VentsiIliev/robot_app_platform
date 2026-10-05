import importlib.util
import json
from pathlib import Path
import platform
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "packaging/platform"))
spec = importlib.util.spec_from_file_location("platform_local_release", ROOT / "packaging/platform/local_release.py")
local_release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local_release)


class LocalReleaseTests(unittest.TestCase):
    def test_selects_latest_semantic_version_for_target_and_architecture(self):
        with tempfile.TemporaryDirectory() as directory:
            releases = Path(directory)
            target = local_release.load_target("paint_tray_dry")
            folder = releases / target['target']
            folder.mkdir()
            for version in ('1.9.0', '1.10.0', '1.0.2'):
                (folder / f"{target['product']}-installer-{version}-{platform.machine()}.tar.gz").touch()
            (folder / f"{target['product']}-installer-9.0.0-other-architecture.tar.gz").touch()
            (folder / f"glue-robot-installer-10.0.0-{platform.machine()}.tar.gz").touch()
            self.assertIn('-1.10.0-', local_release.latest_installer(releases, target).name)

    def test_run_uses_installed_helper_and_its_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'installed'
            target = local_release.load_target('paint_tray_dry')
            helper = root / 'tools/manage.py'
            helper.parent.mkdir(parents=True)
            helper.touch()
            manifest = root / 'current/manifest.json'
            manifest.parent.mkdir()
            manifest.write_text(json.dumps({'product': target['product']}))
            config = Path(directory) / 'updates.json'
            config.write_text(json.dumps({'install_root': str(root), 'product': target['product'], 'enabled': False}))
            with patch.object(local_release.subprocess, 'run') as launch:
                launch.return_value.returncode = 7
                self.assertEqual(7, local_release.run(target, config, None))
            self.assertEqual(['/usr/bin/python3', str(helper), '--config', str(config), 'launch'], launch.call_args.args[0])

    def test_run_rejects_another_robot_system_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            helper = root / 'tools/manage.py'
            helper.parent.mkdir()
            helper.touch()
            manifest = root / 'current/manifest.json'
            manifest.parent.mkdir()
            manifest.write_text(json.dumps({'product': 'glue-robot'}))
            with patch.object(local_release, 'default_config_path', return_value=root / 'missing.json'):
                with self.assertRaisesRegex(ValueError, 'another robot system/profile'):
                    local_release.run(local_release.load_target('paint_tray_dry'), None, root)
