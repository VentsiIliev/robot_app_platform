import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('platform_installer', ROOT / 'packaging/platform/manage.py')
manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manager)


class RemoteSupportInstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.payload = self.root / 'current/platform/installation/remote-support'
        self.payload.mkdir(parents=True)
        for name in ('install.sh', 'install_pl_remote_support.sh'):
            (self.payload / name).touch()

    def test_desktop_install_elevates_only_support_step_and_passes_vendor(self):
        with patch.object(manager.os, 'geteuid', return_value=1000), patch.object(manager.pwd, 'getpwuid', return_value=SimpleNamespace(pw_name='operator')), patch.object(manager.subprocess, 'run') as run:
            manager.install_remote_support(self.root)
        self.assertEqual(run.call_args.args[0], ['sudo', 'bash', str(self.payload / 'install.sh'), 'operator', '--vendor-installer', str(self.payload / 'install_pl_remote_support.sh')])
        self.assertTrue(run.call_args.kwargs['check'])

    def test_privileged_install_uses_original_desktop_user(self):
        with patch.object(manager.os, 'geteuid', return_value=0), patch.dict(manager.os.environ, SUDO_USER='operator'), patch.object(manager.subprocess, 'run') as run:
            manager.install_remote_support(self.root)
        self.assertEqual(run.call_args.args[0][:3], ['bash', str(self.payload / 'install.sh'), 'operator'])

    def test_failed_support_step_reports_retry_without_success(self):
        with patch.object(manager.os, 'geteuid', return_value=1000), patch.object(manager.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'sudo')):
            with self.assertRaisesRegex(RuntimeError, 'rerun the installer to retry'):
                manager.install_remote_support(self.root)

    def test_missing_payload_does_not_run_privileged_command(self):
        (self.payload / 'install.sh').unlink()
        with patch.object(manager.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'payload is missing'):
                manager.install_remote_support(self.root)
            run.assert_not_called()
