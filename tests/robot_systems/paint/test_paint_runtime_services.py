from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import numpy as np

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
from src.engine.hardware.vacuum_pump.models.vacuum_pump_config import VacuumPumpConfig
from src.engine.hardware.vacuum_pump.modbus.modbus_vacuum_pump_transport import ModbusVacuumPumpTransport
from src.engine.hardware.vacuum_pump.vacuum_pump_controller import VacuumPumpController
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

    def test_transform_debug_uses_calibrated_transformer_not_raw_ppm(self) -> None:
        transformer = MagicMock()
        transformer.is_available.return_value = True
        transformer.transform.side_effect = lambda x, y: (x + 100.0, y + 200.0)
        transformer._model = SimpleNamespace(
            homography_matrix=np.array(
                [
                    [2.0, 0.0, 0.0],
                    [0.0, 3.0, 0.0],
                    [0.0, 0.0, 1.0],
                ],
                dtype=float,
            )
        )
        resolver = SimpleNamespace(_base=transformer)
        service = PaintDashboardService(
            MagicMock(process_id="paint"),
            resolver_getter=lambda: resolver,
        )

        raw_pixels, transformed, homography_only = service._transform_like_pick_target(
            np.array([[[10.0, 20.0]], [[30.0, 40.0]]], dtype=np.float32)
        )

        self.assertEqual(raw_pixels, [[10.0, 20.0], [30.0, 40.0]])
        self.assertEqual([point[:2] for point in transformed], [[110.0, 220.0], [130.0, 240.0]])
        self.assertEqual([point[:2] for point in homography_only], [[20.0, 60.0], [60.0, 120.0]])


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


class TestVacuumPumpController(unittest.TestCase):
    def test_turn_on_and_off_write_configured_values(self) -> None:
        transport = MagicMock()
        controller = VacuumPumpController(
            transport,
            VacuumPumpConfig(pump_register=128, on_value=1, off_value=0),
        )

        self.assertTrue(controller.turn_on())
        self.assertTrue(controller.turn_off())

        transport.write_register.assert_any_call(128, 1)
        transport.write_register.assert_any_call(128, 0)

    def test_turn_off_pulses_blow_off_after_pump_off(self) -> None:
        transport = MagicMock()
        controller = VacuumPumpController(
            transport,
            VacuumPumpConfig(
                pump_register=128,
                blow_off_register=129,
                blow_off_pulse_seconds=0.0,
            ),
        )

        self.assertTrue(controller.turn_off())

        self.assertEqual(
            transport.write_register.call_args_list,
            [
                call(128, 0),
                call(129, 1),
                call(129, 0),
            ],
        )

    def test_transport_failures_return_false(self) -> None:
        transport = MagicMock()
        transport.write_register.side_effect = RuntimeError("boom")
        controller = VacuumPumpController(transport)

        self.assertFalse(controller.turn_on())
        self.assertFalse(controller.turn_off())


class TestModbusVacuumPumpTransport(unittest.TestCase):
    def test_no_response_write_is_treated_as_success_for_write_only_relay(self) -> None:
        class NoResponseError(Exception):
            pass

        inst = MagicMock()
        inst.write_bits.side_effect = NoResponseError("no answer")
        session = MagicMock()
        session.__enter__.return_value = inst
        session.__exit__.return_value = None
        transport = ModbusVacuumPumpTransport(
            port="/dev/null",
            slave_address=1,
            no_response_retry_delay_s=0.0,
        )
        transport._session = MagicMock(return_value=session)

        transport.write_register(128, 1)

        self.assertEqual(inst.write_bits.call_count, 3)
        inst.write_bits.assert_called_with(128, [1])

    def test_no_response_write_returns_after_successful_retry(self) -> None:
        class NoResponseError(Exception):
            pass

        inst = MagicMock()
        inst.write_bits.side_effect = [NoResponseError("no answer"), None]
        session = MagicMock()
        session.__enter__.return_value = inst
        session.__exit__.return_value = None
        transport = ModbusVacuumPumpTransport(
            port="/dev/null",
            slave_address=1,
            no_response_retry_delay_s=0.0,
        )
        transport._session = MagicMock(return_value=session)

        transport.write_register(128, 0)

        self.assertEqual(inst.write_bits.call_count, 2)
        inst.write_bits.assert_called_with(128, [0])

    def test_other_write_errors_still_raise(self) -> None:
        inst = MagicMock()
        inst.write_bits.side_effect = RuntimeError("serial failed")
        session = MagicMock()
        session.__enter__.return_value = inst
        session.__exit__.return_value = None
        transport = ModbusVacuumPumpTransport(port="/dev/null", slave_address=1)
        transport._session = MagicMock(return_value=session)

        with self.assertRaises(RuntimeError):
            transport.write_register(128, 1)


if __name__ == "__main__":
    unittest.main()
