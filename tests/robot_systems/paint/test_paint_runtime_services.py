from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.shared_contracts.events.process_events import (
    ProcessBusyEvent,
    ProcessState,
    ProcessTopics,
)
from src.robot_systems.paint.applications.dashboard.service.paint_dashboard_service import (
    PaintDashboardService,
)
from src.robot_systems.paint.calibration.coordinator import PaintCalibrationCoordinator
from src.robot_systems.paint.component_ids import ProcessID
from src.robot_systems.paint.domain.vacuum_pump.relay_vacuum_pump_controller import (
    RelayVacuumPumpController,
)
from src.robot_systems.paint.processes.robot_calibration_process import (
    RobotCalibrationProcess,
)


class TestPaintDashboardService(unittest.TestCase):
    def test_load_state_maps_process_state_into_dashboard_contract(self) -> None:
        process = MagicMock(process_id="paint")
        service = PaintDashboardService(process)

        process.state = ProcessState.IDLE
        idle = service.load_state()
        self.assertEqual(idle.process_state, ProcessState.IDLE.value)
        self.assertEqual(idle.active_job_label, "No active job")
        self.assertTrue(idle.can_start)
        self.assertFalse(idle.can_stop)
        self.assertEqual(idle.pause_label, "Pause")

        process.state = ProcessState.RUNNING
        running = service.load_state()
        self.assertEqual(running.active_job_label, "Paint job running")
        self.assertTrue(running.can_stop)
        self.assertTrue(running.can_pause)

        process.state = ProcessState.PAUSED
        paused = service.load_state()
        self.assertEqual(paused.active_job_label, "Paint job paused")
        self.assertEqual(paused.pause_label, "Resume")

        process.state = ProcessState.STOPPED
        stopped = service.load_state()
        self.assertEqual(stopped.active_job_label, "Paint job stopped")
        self.assertTrue(stopped.can_start)

        process.state = ProcessState.ERROR
        error = service.load_state()
        self.assertEqual(error.active_job_label, "Paint job error")

    def test_control_methods_delegate_to_process(self) -> None:
        process = MagicMock(process_id="paint")
        service = PaintDashboardService(process)

        self.assertEqual(service.get_process_id(), "paint")
        service.start()
        service.stop()
        service.pause()
        service.resume()
        service.reset_errors()

        process.start.assert_called_once_with()
        process.stop.assert_called_once_with()
        process.pause.assert_called_once_with()
        process.resume.assert_called_once_with()
        process.reset_errors.assert_called_once_with()


class TestPaintCalibrationCoordinator(unittest.TestCase):
    def test_calibrate_publishes_busy_event_when_calibration_already_running(self) -> None:
        calibration_process = MagicMock()
        calibration_process.state = ProcessState.RUNNING
        messaging = MagicMock()
        coordinator = PaintCalibrationCoordinator(calibration_process, messaging)
        coordinator._active_process = calibration_process

        coordinator.calibrate()

        messaging.publish.assert_called_once()
        topic, event = messaging.publish.call_args.args
        self.assertEqual(topic, ProcessTopics.busy(ProcessID.ROBOT_CALIBRATION))
        self.assertIsInstance(event, ProcessBusyEvent)
        self.assertIn("already running", event.message)
        calibration_process.start.assert_not_called()

    def test_calibrate_resets_error_and_starts_process(self) -> None:
        calibration_process = MagicMock()
        calibration_process.state = ProcessState.ERROR
        messaging = MagicMock()
        coordinator = PaintCalibrationCoordinator(calibration_process, messaging)

        coordinator.calibrate()

        calibration_process.reset_errors.assert_called_once_with()
        calibration_process.start.assert_called_once_with()
        self.assertIs(coordinator._active_process, calibration_process)

    def test_stop_calibration_clears_active_process_and_stops_only_when_active(self) -> None:
        calibration_process = MagicMock()
        calibration_process.state = ProcessState.RUNNING
        coordinator = PaintCalibrationCoordinator(calibration_process, MagicMock())
        coordinator._active_process = calibration_process

        coordinator.stop_calibration()
        self.assertIsNone(coordinator._active_process)
        calibration_process.stop.assert_called_once_with()

        calibration_process.stop.reset_mock()
        coordinator.stop_calibration()
        calibration_process.stop.assert_not_called()


class TestRobotCalibrationProcess(unittest.TestCase):
    def _make_process(self) -> tuple[RobotCalibrationProcess, MagicMock]:
        service = MagicMock()
        process = RobotCalibrationProcess(calibration_service=service, messaging=MagicMock())
        return process, service

    def test_on_start_spawns_named_daemon_thread(self) -> None:
        process, _service = self._make_process()
        thread = MagicMock()

        with patch(
            "src.robot_systems.paint.processes.robot_calibration_process.threading.Thread",
            return_value=thread,
        ) as thread_cls:
            process._on_start()

        kwargs = thread_cls.call_args.kwargs
        self.assertEqual(kwargs["target"], process._run_in_background)
        self.assertTrue(kwargs["daemon"])
        self.assertEqual(kwargs["name"], "RobotCalibrationProcess")
        thread.start.assert_called_once_with()
        self.assertFalse(process._stopping)
        self.assertIs(process._thread, thread)

    def test_on_stop_sets_flag_and_requests_service_stop(self) -> None:
        process, service = self._make_process()

        process._on_stop()

        self.assertTrue(process._stopping)
        service.stop_calibration.assert_called_once_with()

    def test_on_reset_errors_clears_stop_flag(self) -> None:
        process, _service = self._make_process()
        process._stopping = True

        process._on_reset_errors()

        self.assertFalse(process._stopping)

    def test_run_in_background_stops_process_on_success(self) -> None:
        process, service = self._make_process()
        service.run_calibration.return_value = (True, "ok")
        process.stop = MagicMock()

        process._run_in_background()

        process.stop.assert_called_once_with()

    def test_run_in_background_sets_error_on_failure(self) -> None:
        process, service = self._make_process()
        service.run_calibration.return_value = (False, "bad")
        process.set_error = MagicMock()

        process._run_in_background()

        process.set_error.assert_called_once_with("bad")

    def test_run_in_background_sets_error_on_exception_unless_stopping(self) -> None:
        process, service = self._make_process()
        service.run_calibration.side_effect = RuntimeError("boom")
        process.set_error = MagicMock()

        process._run_in_background()
        process.set_error.assert_called_once_with("boom")

        process._stopping = True
        process.set_error.reset_mock()
        process._run_in_background()
        process.set_error.assert_not_called()


class TestRelayVacuumPumpController(unittest.TestCase):
    def test_turn_on_and_off_delegate_to_state_setter(self) -> None:
        controller = RelayVacuumPumpController("/tmp/relay_client.py")
        controller._set_state = MagicMock(side_effect=[True, False])

        self.assertTrue(controller.turn_on())
        self.assertFalse(controller.turn_off())
        controller._set_state.assert_any_call("on")
        controller._set_state.assert_any_call("off")

    def test_set_state_returns_false_when_module_missing(self) -> None:
        controller = RelayVacuumPumpController("/tmp/missing.py")
        controller._load_module = MagicMock(return_value=None)

        self.assertFalse(controller._set_state("on"))

    def test_set_state_calls_control_relay_and_returns_success_flag(self) -> None:
        module = SimpleNamespace(control_relay=MagicMock(return_value={"success": True}))
        controller = RelayVacuumPumpController("/tmp/relay_client.py", host="host", port=55, output_num=7)
        controller._load_module = MagicMock(return_value=module)

        self.assertTrue(controller._set_state("on"))
        module.control_relay.assert_called_once_with(7, "on", host="host", port=55)

        module.control_relay.reset_mock()
        module.control_relay.return_value = {"success": False}
        self.assertFalse(controller._set_state("off"))
        module.control_relay.assert_called_once_with(7, "off", host="host", port=55)

    def test_set_state_returns_false_on_client_exception(self) -> None:
        module = SimpleNamespace(control_relay=MagicMock(side_effect=RuntimeError("boom")))
        controller = RelayVacuumPumpController("/tmp/relay_client.py")
        controller._load_module = MagicMock(return_value=module)

        self.assertFalse(controller._set_state("on"))

    def test_load_module_handles_missing_and_invalid_paths_and_caches_success(self) -> None:
        missing = RelayVacuumPumpController("/tmp/definitely-missing.py")
        self.assertIsNone(missing._load_module())

        with tempfile.TemporaryDirectory() as tmp:
            relay_path = Path(tmp) / "relay_client.py"
            relay_path.write_text(
                "def control_relay(output_num, state, host='x', port=1):\n"
                "    return {'success': True, 'output_num': output_num, 'state': state}\n",
                encoding="utf-8",
            )
            controller = RelayVacuumPumpController(str(relay_path))
            module = controller._load_module()

            self.assertIsNotNone(module)
            self.assertIs(module, controller._load_module())
            self.assertTrue(module.control_relay(1, 'on')["success"])

        with tempfile.TemporaryDirectory() as tmp:
            bad_path = Path(tmp) / "bad_relay.py"
            bad_path.write_text("raise RuntimeError('import failed')\n", encoding="utf-8")
            self.assertIsNone(RelayVacuumPumpController(str(bad_path))._load_module())


if __name__ == "__main__":
    unittest.main()
