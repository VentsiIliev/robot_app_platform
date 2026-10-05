import tempfile
import socket
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from src.engine.remote_support import controller
from src.applications.network_settings.service.remote_support_client import RemoteSupportClient


class RemoteSupportControllerTests(unittest.TestCase):
    def test_protocol_rejects_arbitrary_commands(self) -> None:
        for request in (
            {"operation": "start", "unit": "ssh.service"},
            {"operation": "restart"},
            {"operation": "status", "command": "id"},
        ):
            with self.subTest(request=request), self.assertRaises(ValueError):
                controller.handle_request(request)

    def test_enable_marker_precedes_start_and_disable_removes_it_before_stop(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state_dir = Path(temp)
            marker = state_dir / "enabled"
            active = False

            def systemctl(*args):
                nonlocal active
                if args[0] == "enable":
                    self.assertTrue(marker.exists())
                    self.assertEqual(args[1], "--now")
                    active = True
                elif args[0] == "stop":
                    self.assertFalse(marker.exists())
                    active = False
                elif args[0] == "show":
                    state = "active" if active else "inactive"
                    return self._result(f"LoadState=loaded\nActiveState={state}\n")
                return self._result("")

            with patch.object(controller, "STATE_DIR", state_dir), \
                 patch.object(controller, "ENABLE_MARKER", marker), \
                 patch.object(controller, "_systemctl", side_effect=systemctl):
                self.assertEqual(controller.handle_request({"operation": "enable"})["active"], True)
                self.assertTrue(marker.exists())
                self.assertEqual(controller.handle_request({"operation": "disable"})["active"], False)
                self.assertFalse(marker.exists())

    def test_status_rejects_missing_unit(self) -> None:
        with patch.object(controller, "_systemctl", return_value=self._result("LoadState=not-found\nActiveState=inactive\n")):
            with self.assertRaisesRegex(RuntimeError, "not installed"):
                controller.handle_request({"operation": "status"})

    def test_failed_enable_restores_off_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state_dir = Path(temp)
            marker = state_dir / "enabled"
            operations = []

            def systemctl(*args):
                operations.append(args[0])
                if args[0] == "enable":
                    self.assertTrue(marker.exists())
                    from subprocess import CompletedProcess
                    return CompletedProcess([], 1, "", "Start failed")
                return self._result("LoadState=loaded\nActiveState=inactive\n")

            with patch.object(controller, "STATE_DIR", state_dir), \
                 patch.object(controller, "ENABLE_MARKER", marker), \
                 patch.object(controller, "_systemctl", side_effect=systemctl):
                with self.assertRaisesRegex(RuntimeError, "Start failed"):
                    controller.handle_request({"operation": "enable"})
                self.assertFalse(marker.exists())
                self.assertEqual(operations[-1], "stop")

    def test_client_and_controller_exchange_status_over_unix_socket(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            socket_path = str(Path(temp) / "support.sock")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(socket_path)
                listener.listen(1)

                def serve_once():
                    with listener.accept()[0] as connection:
                        controller._serve_connection(connection)

                thread = threading.Thread(target=serve_once)
                thread.start()
                expected = {"enabled": False, "active": False, "service_state": "inactive"}
                with patch.object(controller, "_status", return_value=expected):
                    self.assertEqual(RemoteSupportClient(socket_path).status(), expected)
                thread.join(timeout=2)
                self.assertFalse(thread.is_alive())

    @staticmethod
    def _result(stdout: str):
        from subprocess import CompletedProcess
        return CompletedProcess([], 0, stdout, "")
