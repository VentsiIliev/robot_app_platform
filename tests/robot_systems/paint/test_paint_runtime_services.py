from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import numpy as np

from src.robot_systems.paint.processes.paint.config import (
    PaintDropoffConfig,
    PaintNavigationReturnConfig,
    PaintProcessConfig,
)

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
from src.engine.hardware.vacuum_pump.modbus.modbus_vacuum_pump_transport import (
    ModbusVacuumPumpTransport,
    _crc16,
)
from src.engine.hardware.vacuum_pump.vacuum_pump_controller import VacuumPumpController
from src.engine.hardware.laser import ModbusLaserControl
from src.engine.hardware.fan.modbus.modbus_fan_control import ModbusFanControl
from src.engine.hardware.vacuum_sensor.models.vacuum_sensor_config import VacuumSensorConfig
from src.engine.hardware.vacuum_sensor.vacuum_sensor_service import VacuumSensorService
from src.engine.hardware.xinje import XinjeMA8X8YR
from src.robot_systems.paint.processes.robot_calibration_process import (
    RobotCalibrationProcess,
)


class TestPaintDashboardService(unittest.TestCase):
    def test_auxiliary_state_reads_active_manual_tray_fan_output(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.IDLE
        fan = MagicMock()
        fan.read_state.return_value = True
        tray_fan = MagicMock()
        tray_fan.read_state.return_value = False
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            dropoff=PaintDropoffConfig(strategy="plate_layout")
        )
        service = PaintDashboardService(
            process,
            fan_control=fan,
            tray_fan_control=tray_fan,
            paint_process_config_service=config_service,
        )

        states = service.get_auxiliary_states()

        self.assertFalse(states["fan"])
        tray_fan.read_state.assert_called_once_with()
        fan.read_state.assert_not_called()

    def test_failed_auxiliary_state_read_clears_stale_on_indication(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.IDLE
        fan = MagicMock()
        fan.read_state.side_effect = OSError("offline")
        service = PaintDashboardService(process, fan_control=fan)

        self.assertFalse(service.get_auxiliary_states()["fan"])

    def test_fan_control_routes_to_tray_fan_in_manual_drying_mode(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.IDLE
        fan = MagicMock()
        tray_fan = MagicMock()
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            dropoff=PaintDropoffConfig(strategy="plate_layout")
        )
        service = PaintDashboardService(
            process,
            fan_control=fan,
            tray_fan_control=tray_fan,
            paint_process_config_service=config_service,
        )

        result = service.set_auxiliary_enabled("fan", True)

        self.assertTrue(result.success)
        tray_fan.turn_on.assert_called_once_with()
        fan.turn_on.assert_not_called()

    def test_fan_control_routes_to_standard_fan_in_auto_drying_mode(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.IDLE
        fan = MagicMock()
        tray_fan = MagicMock()
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            dropoff=PaintDropoffConfig(strategy="movement_group")
        )
        service = PaintDashboardService(
            process,
            fan_control=fan,
            tray_fan_control=tray_fan,
            paint_process_config_service=config_service,
        )

        result = service.set_auxiliary_enabled("fan", False)

        self.assertTrue(result.success)
        fan.turn_off.assert_called_once_with()
        tray_fan.turn_off.assert_not_called()

    def test_enabling_dryer_then_switching_auto_persists_both_settings(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.IDLE
        dryer = MagicMock()
        dryer.is_healthy.return_value = False
        dryer.enable.return_value = True
        persist_enabled = MagicMock()
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            dropoff=PaintDropoffConfig(strategy="plate_layout")
        )
        service = PaintDashboardService(
            process,
            dryer_service=dryer,
            persist_dryer_enabled=persist_enabled,
            paint_process_config_service=config_service,
        )

        result = service.enable_dryer_and_set_auto_mode()

        self.assertTrue(result.success)
        dryer.enable.assert_called_once_with()
        persist_enabled.assert_called_once_with(True)
        self.assertEqual("movement_group", config_service.save.call_args.args[0].dropoff.strategy)

    def test_failed_dryer_enable_does_not_switch_auto_mode(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.IDLE
        dryer = MagicMock()
        dryer.is_healthy.return_value = False
        dryer.enable.return_value = False
        dryer.last_error = "Dryer did not initialize"
        persist_enabled = MagicMock()
        config_service = MagicMock()
        service = PaintDashboardService(
            process,
            dryer_service=dryer,
            persist_dryer_enabled=persist_enabled,
            paint_process_config_service=config_service,
        )

        result = service.enable_dryer_and_set_auto_mode()

        self.assertFalse(result.success)
        self.assertEqual("Dryer did not initialize", result.message)
        persist_enabled.assert_called_once_with(False)
        config_service.save.assert_not_called()

    def test_drying_mode_persists_matching_dropoff_strategy(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.IDLE
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            dropoff=PaintDropoffConfig(strategy="movement_group")
        )
        service = PaintDashboardService(
            process,
            paint_process_config_service=config_service,
        )

        self.assertEqual("auto", service.get_drying_mode())
        result = service.set_drying_mode("manual")

        self.assertTrue(result.success)
        self.assertEqual("plate_layout", config_service.save.call_args.args[0].dropoff.strategy)

    def test_demo_drying_mode_persists_alternation_starting_with_auto(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.IDLE
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig()
        service = PaintDashboardService(
            process,
            paint_process_config_service=config_service,
        )

        result = service.set_drying_mode("demo")

        self.assertTrue(result.success)
        saved_dropoff = config_service.save.call_args.args[0].dropoff
        self.assertTrue(saved_dropoff.alternate_drying_demo)
        self.assertEqual("movement_group", saved_dropoff.strategy)

    def test_demo_drying_mode_resolves_odd_auto_and_even_manual_cycles(self) -> None:
        from src.robot_systems.paint.processes.paint.paint_production_service import (
            PaintProductionService,
        )

        config = PaintProcessConfig(
            dropoff=PaintDropoffConfig(alternate_drying_demo=True)
        )

        self.assertEqual(
            "movement_group",
            PaintProductionService._effective_dropoff_strategy(config, 1),
        )
        self.assertEqual(
            "plate_layout",
            PaintProductionService._effective_dropoff_strategy(config, 2),
        )
        self.assertEqual(
            "movement_group",
            PaintProductionService._effective_dropoff_strategy(config, 3),
        )

    def test_drying_mode_cannot_change_while_running(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.RUNNING
        config_service = MagicMock()
        service = PaintDashboardService(
            process,
            paint_process_config_service=config_service,
        )

        result = service.set_drying_mode("manual")

        self.assertFalse(result.success)
        config_service.save.assert_not_called()

    def test_cable_relief_uses_configured_unwind_motion_values(self) -> None:
        process = MagicMock(process_id="paint")
        robot = MagicMock()
        robot.unwind_joint6.return_value = True
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            navigation_return=PaintNavigationReturnConfig(
                unwind_vel_percent=42.0,
                unwind_acc_percent=27.0,
                unwind_queue_if_busy=False,
            )
        )
        service = PaintDashboardService(
            process,
            robot_service=robot,
            paint_process_config_service=config_service,
        )

        result = service.relieve_cable()

        self.assertTrue(result.success)
        robot.unwind_joint6.assert_called_once_with(
            blocking=True,
            queue_if_busy=False,
            vel=42.0,
            acc=27.0,
        )

    def test_unmatched_paint_settings_persist_and_replace_runtime_snapshot(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.IDLE
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            default_paint_velocity_percent=10.0,
            default_paint_acceleration_percent=10.0,
            default_paint_offset_mm=0.0,
        )
        service = PaintDashboardService(
            process,
            paint_process_config_service=config_service,
        )

        result = service.save_unmatched_paint_settings(25.0, 35.0, -4.5)

        self.assertTrue(result.success)
        saved = config_service.save.call_args.args[0]
        self.assertEqual(25.0, saved.default_paint_velocity_percent)
        self.assertEqual(35.0, saved.default_paint_acceleration_percent)
        self.assertEqual(-4.5, saved.default_paint_offset_mm)

    def test_unmatched_paint_settings_cannot_change_while_running(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.RUNNING
        config_service = MagicMock()
        service = PaintDashboardService(
            process,
            paint_process_config_service=config_service,
        )

        result = service.save_unmatched_paint_settings(25.0, 35.0, -4.5)

        self.assertFalse(result.success)
        config_service.save.assert_not_called()

    def test_unmatched_paint_settings_can_change_while_running_when_enabled(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.RUNNING
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig()
        service = PaintDashboardService(
            process,
            paint_process_config_service=config_service,
            allow_running_paint_settings_updates=True,
        )

        result = service.save_unmatched_paint_settings(25.0, 35.0, -4.5)

        self.assertTrue(result.success)
        saved = config_service.save.call_args.args[0]
        self.assertEqual(25.0, saved.default_paint_velocity_percent)
        self.assertEqual(35.0, saved.default_paint_acceleration_percent)
        self.assertEqual(-4.5, saved.default_paint_offset_mm)

    def test_acceleration_scale_can_change_while_paused_when_enabled(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.PAUSED
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig()
        service = PaintDashboardService(
            process,
            paint_process_config_service=config_service,
            allow_running_paint_settings_updates=True,
        )

        result = service.save_acceleration_scale(72.0)

        self.assertTrue(result.success)
        saved = config_service.save.call_args.args[0]
        self.assertEqual(72.0, saved.paint_process_acceleration_scale_percent)

    def test_load_state_maps_process_state_into_dashboard_contract(self) -> None:
        process = MagicMock(process_id="paint")
        robot = MagicMock()
        robot.get_state.return_value = "idle"
        robot.is_healthy.return_value = True
        vision = MagicMock()
        vision.is_healthy.return_value = True
        service = PaintDashboardService(process, robot_service=robot, vision_service=vision)

        process.state = ProcessState.IDLE
        idle = service.load_state()
        self.assertEqual(idle.process_state, ProcessState.IDLE.value)
        self.assertEqual(idle.active_job_label, "No active job")
        self.assertEqual(idle.card_states[1].title, "Robot Status")
        self.assertEqual(idle.card_states[1].value, "IDLE")
        self.assertEqual(idle.card_states[2].title, "Vision Status")
        self.assertEqual(idle.card_states[2].value, "ONLINE")
        self.assertEqual(idle.card_states[3].title, "Process Status")
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
        self.assertFalse(error.can_start)
        self.assertFalse(error.can_stop)
        self.assertFalse(error.can_pause)

    def test_load_state_reports_unavailable_or_unhealthy_status_cards(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.IDLE
        robot = MagicMock()
        robot.get_state.return_value = "disconnected"
        robot.is_healthy.return_value = False
        robot.get_connection_details.return_value = {
            "state": "disconnected",
            "last_error": "bridge down",
        }

        state = PaintDashboardService(process, robot_service=robot, vision_service=None).load_state()

        self.assertEqual(state.card_states[1].value, "DISCONNECTED")
        self.assertEqual(state.card_states[1].note, "Robot bridge is disconnected")
        self.assertEqual(state.card_states[2].value, "UNAVAILABLE")

    def test_load_state_prefers_robot_connection_details_over_stale_idle_state(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.IDLE
        robot = MagicMock()
        robot.get_state.return_value = "idle"
        robot.is_healthy.return_value = True
        robot.get_connection_state.return_value = "disconnected"
        robot.get_connection_details.return_value = {
            "state": "disconnected",
            "last_error": "HTTPConnectionPool: Failed to establish a new connection: Connection refused",
        }

        state = PaintDashboardService(process, robot_service=robot).load_state()

        self.assertEqual(state.card_states[1].value, "DISCONNECTED")
        self.assertEqual(state.card_states[1].note, "ROS2 bridge is not reachable")

    def test_load_state_prefers_live_robot_connection_state_over_stale_connection_details(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.IDLE
        robot = MagicMock()
        robot.get_state.return_value = "idle"
        robot.is_healthy.return_value = False
        robot.get_connection_state.return_value = "disconnected"
        robot.get_connection_details.return_value = {
            "state": "idle",
            "last_error": "Connection refused",
        }

        state = PaintDashboardService(process, robot_service=robot).load_state()

        self.assertEqual(state.card_states[1].value, "DISCONNECTED")
        self.assertEqual(state.card_states[1].note, "ROS2 bridge is not reachable")

    def test_load_state_sanitizes_robot_connection_exceptions(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.IDLE
        robot = MagicMock()
        robot.get_connection_details.side_effect = RuntimeError(
            "HTTPConnectionPool(host='localhost', port=5000): Max retries exceeded with url: /health "
            "(Caused by NewConnectionError: Failed to establish a new connection: [Errno 111] Connection refused)"
        )

        state = PaintDashboardService(process, robot_service=robot).load_state()

        self.assertEqual(state.card_states[1].value, "ERROR")
        self.assertEqual(state.card_states[1].note, "ROS2 bridge is not reachable")
        self.assertNotIn("HTTPConnectionPool", state.card_states[1].note)

    def test_load_state_reports_robot_runtime_starting(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.IDLE
        robot = MagicMock()
        robot.get_connection_details.return_value = {
            "state": "starting",
            "startup": {
                "phase": "initializing_runtime",
                "message": "ROS runtime is initializing",
            },
        }
        robot.get_connection_state.return_value = "starting"

        state = PaintDashboardService(process, robot_service=robot).load_state()

        self.assertEqual(state.card_states[1].value, "STARTING")
        self.assertEqual(state.card_states[1].note, "ROS runtime is initializing")
        robot.get_drive_status.assert_not_called()

    def test_load_state_reports_drive_not_ready_when_bridge_is_online(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.IDLE
        robot = MagicMock()
        robot.get_connection_details.return_value = {"state": "idle"}
        robot.get_connection_state.return_value = "idle"
        robot.get_drive_status.return_value = {
            "success": True,
            "requested_enabled": True,
            "actual_enabled": False,
            "motion_allowed_by_drive_enable": False,
            "status_state": ["operation_enabled", "switch_on_disabled"],
        }

        state = PaintDashboardService(process, robot_service=robot).load_state()

        self.assertEqual(state.card_states[1].value, "DRIVE NOT READY")
        self.assertEqual(state.card_states[1].note, "Drive state: operation_enabled, switch_on_disabled")

    def test_load_state_reports_ethercat_drive_status_error(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.IDLE
        robot = MagicMock()
        robot.get_connection_details.return_value = {"state": "idle"}
        robot.get_connection_state.return_value = "idle"
        robot.get_drive_status.return_value = {
            "success": False,
            "error": "Failed to upload SDO: Invalid argument",
        }

        state = PaintDashboardService(process, robot_service=robot).load_state()

        self.assertEqual(state.card_states[1].value, "DRIVE NOT READY")
        self.assertEqual(state.card_states[1].note, "EtherCAT communication error")

    def test_load_state_uses_vision_health_details_for_offline_camera(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.IDLE
        vision = MagicMock()
        vision.is_healthy.return_value = True
        vision.get_health_details.return_value = {
            "healthy": False,
            "message": "No fresh camera frame available",
        }

        state = PaintDashboardService(process, vision_service=vision).load_state()

        self.assertEqual(state.card_states[2].value, "OFFLINE")
        self.assertEqual(state.card_states[2].note, "No fresh camera frame available")

    def test_load_state_reports_intentionally_paused_vision_as_paused(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.RUNNING
        vision = MagicMock()
        vision.is_healthy.return_value = True
        vision.get_health_details.return_value = {
            "healthy": True,
            "processing_paused": True,
            "message": "Vision processing paused by paint process",
        }

        state = PaintDashboardService(process, vision_service=vision).load_state()

        self.assertEqual(state.card_states[2].value, "PAUSED")
        self.assertEqual(
            state.card_states[2].note,
            "Vision processing paused by paint process",
        )

    def test_control_methods_delegate_to_process(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.ERROR
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

    def test_reset_errors_is_ignored_while_process_is_running(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.RUNNING

        PaintDashboardService(process).reset_errors()

        process.reset_errors.assert_not_called()

    def test_get_process_id_uses_enum_value(self) -> None:
        process = MagicMock(process_id=ProcessID.MAIN_PROCESS)
        service = PaintDashboardService(process)

        self.assertEqual(service.get_process_id(), "main_process")

    def test_dashboard_service_does_not_expose_legacy_transform_debug_helper(self) -> None:
        service = PaintDashboardService(MagicMock(process_id="paint"))

        self.assertFalse(hasattr(service, "_transform_like_pick_target"))

    def test_tray_edits_update_shared_layout_while_stopped(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.STOPPED
        plate_layout = MagicMock()
        plate_layout.remove.return_value = True
        service = PaintDashboardService(process, plate_layout_service=plate_layout)

        clear_result = service.clear_plate_layout()
        remove_result = service.remove_plate_placement(7)

        self.assertTrue(clear_result.success)
        self.assertTrue(remove_result.success)
        plate_layout.clear.assert_called_once_with()
        plate_layout.remove.assert_called_once_with(7)

    def test_tray_edits_are_rejected_while_process_is_active(self) -> None:
        process = MagicMock(process_id="paint")
        process.state = ProcessState.RUNNING
        plate_layout = MagicMock()
        service = PaintDashboardService(process, plate_layout_service=plate_layout)

        clear_result = service.clear_plate_layout()
        remove_result = service.remove_plate_placement(7)

        self.assertFalse(clear_result.success)
        self.assertFalse(remove_result.success)
        plate_layout.clear.assert_not_called()
        plate_layout.remove.assert_not_called()


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
    def test_read_state_reads_configured_register_without_writing(self) -> None:
        transport = MagicMock()
        transport.read_register.return_value = 1
        controller = VacuumPumpController(
            transport,
            VacuumPumpConfig(pump_register="Y2", on_value=1),
        )

        self.assertTrue(controller.read_state())
        transport.read_register.assert_called_once_with(130)
        transport.write_register.assert_not_called()

    def test_xinje_ma8x8yr_output_labels_resolve_to_modbus_addresses(self) -> None:
        self.assertEqual(128, XinjeMA8X8YR.resolve_output("Y0"))
        self.assertEqual(130, XinjeMA8X8YR.resolve_output("y2"))
        self.assertEqual(135, XinjeMA8X8YR.resolve_output("Y7"))

    def test_turn_on_and_off_resolve_configured_xinje_output_labels(self) -> None:
        transport = MagicMock()
        controller = VacuumPumpController(
            transport,
            VacuumPumpConfig(pump_register="Y2", blow_off_register="Y3"),
        )

        self.assertTrue(controller.turn_on())
        self.assertTrue(controller.turn_off())

        self.assertEqual(
            transport.write_register.call_args_list,
            [
                call(131, 0),
                call(130, 1),
                call(130, 0),
                call(131, 1),
                call(131, 0),
            ],
        )

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

    def test_turn_on_closes_blow_off_before_pump_on(self) -> None:
        transport = MagicMock()
        controller = VacuumPumpController(
            transport,
            VacuumPumpConfig(
                pump_register=128,
                blow_off_register=129,
                blow_off_pulse_seconds=0.0,
            ),
        )

        self.assertTrue(controller.turn_on())

        self.assertEqual(
            transport.write_register.call_args_list,
            [
                call(129, 0),
                call(128, 1),
            ],
        )

    def test_transport_failures_return_false(self) -> None:
        transport = MagicMock()
        transport.write_register.side_effect = RuntimeError("boom")
        controller = VacuumPumpController(transport)

        self.assertFalse(controller.turn_on())
        self.assertFalse(controller.turn_off())
        self.assertFalse(controller.is_healthy())


class TestModbusFanControl(unittest.TestCase):
    def test_operations_update_cached_health(self) -> None:
        transport = MagicMock()
        transport.read_register.return_value = 1
        fan = ModbusFanControl(transport, register="Y3")

        self.assertFalse(fan.is_healthy())
        self.assertTrue(fan.read_state())
        self.assertTrue(fan.is_healthy())

        transport.write_register.side_effect = OSError("offline")
        with self.assertRaises(OSError):
            fan.turn_off()
        self.assertFalse(fan.is_healthy())


class TestVacuumSensorService(unittest.TestCase):
    def test_repeated_sensor_state_logs_are_throttled_but_transitions_log_immediately(self) -> None:
        transport = MagicMock()
        transport.read_register.side_effect = [1, 1, 0]
        service = VacuumSensorService(
            transport,
            VacuumSensorConfig(sensor_register="Y4"),
        )

        with patch(
            "src.engine.hardware.vacuum_sensor.vacuum_sensor_service._logger.debug"
        ) as debug:
            self.assertTrue(service.is_vacuum_detected())
            self.assertTrue(service.is_vacuum_detected())
            self.assertFalse(service.is_vacuum_detected())

        self.assertEqual(debug.call_count, 2)

    def test_sensor_register_accepts_xinje_output_label(self) -> None:
        transport = MagicMock()
        transport.read_register.return_value = 1
        service = VacuumSensorService(
            transport,
            VacuumSensorConfig(sensor_register="Y4"),
        )

        self.assertTrue(service.is_vacuum_detected())
        transport.read_register.assert_called_once_with(132)

    def test_sensor_register_accepts_xinje_input_label(self) -> None:
        transport = MagicMock()
        transport.read_input.return_value = 1
        service = VacuumSensorService(
            transport,
            VacuumSensorConfig(sensor_register="X4"),
        )

        self.assertTrue(service.is_vacuum_detected())
        transport.read_input.assert_called_once_with(4)
        transport.read_register.assert_not_called()


class TestModbusLaserControl(unittest.TestCase):
    def test_laser_register_accepts_xinje_output_label(self) -> None:
        transport = MagicMock()
        laser = ModbusLaserControl(transport, register="Y5")

        laser.turn_on()
        self.assertTrue(laser.is_healthy())
        laser.turn_off()

        self.assertEqual(
            transport.write_register.call_args_list,
            [call(133, 1), call(133, 0)],
        )


class TestModbusVacuumPumpTransport(unittest.TestCase):
    def test_ma_output_write_uses_fc15_output_bank_frame(self) -> None:
        transport = ModbusVacuumPumpTransport(
            port="/dev/test-ma-frame",
            slave_address=10,
            write_retry_delay_s=0.0,
        )
        transport._raw_send = MagicMock(return_value=b"")

        transport.write_register(130, 1)

        frame = bytes([10, 15, 0, 128, 0, 16, 2, 0b00000100, 0])
        expected = frame + _crc16(frame).to_bytes(2, "little")
        transport._raw_send.assert_called_once_with(expected)

    def test_ma_output_shadow_preserves_previous_bank_values(self) -> None:
        transport = ModbusVacuumPumpTransport(
            port="/dev/test-ma-shadow",
            slave_address=10,
            write_retry_delay_s=0.0,
        )
        transport._raw_send = MagicMock(return_value=b"")

        transport.write_register(130, 1)
        transport.write_register(131, 1)

        frame = bytes([10, 15, 0, 128, 0, 16, 2, 0b00001100, 0])
        expected = frame + _crc16(frame).to_bytes(2, "little")
        transport._raw_send.assert_called_with(expected)

    def test_non_ma_output_write_uses_fc5_single_coil_frame(self) -> None:
        transport = ModbusVacuumPumpTransport(
            port="/dev/null",
            slave_address=10,
            write_retry_delay_s=0.0,
        )
        transport._raw_send = MagicMock(return_value=b"")

        transport.write_register(200, 1)

        frame = bytes([10, 5, 0, 200, 0xFF, 0])
        expected = frame + _crc16(frame).to_bytes(2, "little")
        transport._raw_send.assert_called_once_with(expected)

    def test_send_failures_are_retried_then_raised(self) -> None:
        class NoResponseError(Exception):
            pass

        transport = ModbusVacuumPumpTransport(
            port="/dev/null",
            slave_address=1,
            write_retry_delay_s=0.0,
        )
        transport._raw_send = MagicMock(side_effect=NoResponseError("no answer"))

        with self.assertRaises(RuntimeError):
            transport.write_register(128, 1)

        self.assertEqual(transport._raw_send.call_count, 3)

    def test_no_response_write_returns_after_successful_retry(self) -> None:
        class NoResponseError(Exception):
            pass

        transport = ModbusVacuumPumpTransport(
            port="/dev/null",
            slave_address=1,
            write_retry_delay_s=0.0,
        )
        transport._raw_send = MagicMock(side_effect=[NoResponseError("no answer"), None])

        transport.write_register(128, 0)

        self.assertEqual(transport._raw_send.call_count, 2)

    def test_explicit_modbus_exception_response_raises(self) -> None:
        transport = ModbusVacuumPumpTransport(port="/dev/null", slave_address=1)
        request = bytes([1, 5, 0, 128, 0xFF, 0])
        response_payload = bytes([1, 0x85, 1])
        response = response_payload + _crc16(response_payload).to_bytes(2, "little")

        with self.assertRaises(RuntimeError):
            transport._validate_response(response, request)

    def test_padded_modbus_exception_response_raises_clear_exception(self) -> None:
        transport = ModbusVacuumPumpTransport(port="/dev/null", slave_address=1)
        request = bytes([1, 5, 0, 130, 0xFF, 0])
        response_payload = bytes([1, 0x85, 0x12])
        response = b"\x00" + response_payload + _crc16(response_payload).to_bytes(2, "little") + b"\x00"

        with self.assertRaisesRegex(RuntimeError, "Modbus exception response"):
            transport._validate_response(response, request)


if __name__ == "__main__":
    unittest.main()
