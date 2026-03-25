import unittest
from unittest.mock import MagicMock, patch

from src.robot_systems.glue.processes.glue_dispensing.context_ops.pump_thread_ops import (
    DispensingPumpThreadOps,
)
from src.robot_systems.glue.processes.glue_dispensing.dispensing_config import GlueDispensingConfig
from src.robot_systems.glue.processes.glue_dispensing.dispensing_context import DispensingContext
from src.robot_systems.glue.processes.glue_dispensing.dispensing_error import (
    DispensingErrorCode,
    DispensingErrorKind,
)
from src.robot_systems.glue.processes.glue_dispensing.dispensing_machine_factory import DispensingMachineFactory
from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.startup.handle_issuing_move_to_first_point import (
    handle_issuing_move_to_first_point,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.startup.handle_loading_path import (
    handle_loading_path,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.startup.handle_loading_current_path import (
    handle_loading_current_path,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.terminal.terminal_handlers import (
    handle_completed,
    handle_error,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.motion.handle_advancing_path import (
    handle_advancing_path,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.motion.handle_moving_to_first_point import (
    handle_moving_to_first_point,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.hardware.generator_handlers import (
    handle_turning_off_generator,
    handle_turning_on_generator,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.hardware.pump_handlers import (
    handle_turning_off_pump,
    handle_turning_on_pump,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.startup.handle_resuming import (
    handle_resuming,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.motion.handle_sending_path_points import (
    handle_sending_path_points,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.startup.handle_starting import handle_starting
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.hardware.handle_starting_pump_adjustment_thread import (
    handle_starting_pump_adjustment_thread,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.hardware.handle_waiting_for_pump_thread_ready import (
    handle_waiting_for_pump_thread_ready,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.waiting.handle_routing_path_completion_wait import (
    handle_routing_path_completion_wait,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.waiting.handle_waiting_for_pump_thread import (
    handle_waiting_for_pump_thread,
)
from src.robot_systems.glue.processes.glue_dispensing.state_handlers.waiting.handle_waiting_for_final_position import (
    handle_waiting_for_final_position,
)
from src.robot_systems.glue.settings.glue import GlueSettingKey


def _settings(**overrides):
    values = {
        GlueSettingKey.GLUE_TYPE.value: "Type A",
        "velocity": 55.0,
        "acceleration": 66.0,
        GlueSettingKey.TIME_BETWEEN_GENERATOR_AND_GLUE.value: 0.0,
        GlueSettingKey.REACH_START_THRESHOLD.value: 1.0,
        GlueSettingKey.REACH_END_THRESHOLD.value: 1.0,
        GlueSettingKey.MOTOR_SPEED.value: 10000,
        GlueSettingKey.FORWARD_RAMP_STEPS.value: 1,
        GlueSettingKey.INITIAL_RAMP_SPEED.value: 5000,
        GlueSettingKey.INITIAL_RAMP_SPEED_DURATION.value: 1.0,
        GlueSettingKey.SPEED_REVERSE.value: 1000,
        GlueSettingKey.REVERSE_DURATION.value: 1.0,
        GlueSettingKey.REVERSE_RAMP_STEPS.value: 1,
    }
    values.update(overrides)
    return values


def _point(x):
    return [float(x), 0.0, 0.0, 0.0, 0.0, 0.0]


def _make_context():
    ctx = DispensingContext()
    ctx.run_allowed.set()
    ctx.robot_service = MagicMock()
    ctx.motor_service = MagicMock()
    ctx.generator = MagicMock()
    ctx.dispense_channel_service = MagicMock()
    ctx.dispense_channel_service.resolve_motor_address.return_value = -1
    ctx.dispense_channel_service.start_dispense.return_value = (True, "")
    ctx.dispense_channel_service.stop_dispense.return_value = (True, "")
    ctx.robot_tool = 3
    ctx.robot_user = 7
    ctx.global_velocity = 12.5
    ctx.global_acceleration = 34.0
    ctx.use_segment_motion_settings = True
    ctx.paths = [
        ([_point(1), _point(2), _point(3), _point(4)], _settings()),
        ([_point(10)], _settings(glue_type="Type B")),
    ]
    return ctx


def _make_machine_context():
    ctx = _make_context()
    ctx.paths = [
        ([_point(1.0)], _settings()),
    ]
    return ctx


class _FakePumpThread:
    def __init__(self, alive_values, result=None):
        self._alive_values = list(alive_values)
        self.result = result
        self.join_calls = []

    def is_alive(self):
        if self._alive_values:
            return self._alive_values.pop(0)
        return False

    def join(self, timeout=None):
        self.join_calls.append(timeout)


class TestHandleStarting(unittest.TestCase):
    def test_routes_fresh_start_to_loading_path(self):
        ctx = _make_context()

        state = handle_starting(ctx)

        self.assertEqual(state, GlueDispensingState.LOADING_PATH)
        ctx.robot_service.move_ptp.assert_not_called()

    def test_routes_resume_to_resuming_state(self):
        ctx = _make_context()
        ctx.is_resuming = True

        state = handle_starting(ctx)

        self.assertEqual(state, GlueDispensingState.RESUMING)
        self.assertFalse(ctx.is_resuming)


class TestHandleLoadingPath(unittest.TestCase):
    def test_routes_non_empty_path_to_loading_current_path(self):
        ctx = _make_context()

        state = handle_loading_path(ctx)

        self.assertEqual(state, GlueDispensingState.LOADING_CURRENT_PATH)
        self.assertIsNone(ctx.current_path)
        self.assertIsNone(ctx.current_settings)

    def test_skips_empty_paths_and_stays_in_loading_path(self):
        ctx = _make_context()
        ctx.paths[0] = ([], _settings())

        state = handle_loading_path(ctx)

        self.assertEqual(state, GlueDispensingState.LOADING_PATH)
        self.assertEqual(ctx.current_path_index, 1)
        self.assertEqual(ctx.current_point_index, 0)


class TestHandleLoadingCurrentPath(unittest.TestCase):
    def test_loads_current_path_and_prepares_first_move(self):
        ctx = _make_context()

        state = handle_loading_current_path(ctx)

        entry = ctx.paths[0]
        self.assertEqual(state, GlueDispensingState.ISSUING_MOVE_TO_FIRST_POINT)
        self.assertEqual(ctx.current_entry, entry)
        self.assertEqual(ctx.current_path, entry.points)
        self.assertEqual(ctx.current_settings, entry.settings)
        self.assertEqual(ctx.current_point_index, 0)


class TestHandleIssuingMoveToFirstPoint(unittest.TestCase):
    def test_commands_move_to_first_point_using_segment_motion_settings(self):
        ctx = _make_context()
        ctx.current_path = ctx.paths[0][0]
        ctx.current_settings = ctx.paths[0][1]

        state = handle_issuing_move_to_first_point(ctx)

        self.assertEqual(state, GlueDispensingState.MOVING_TO_FIRST_POINT)
        ctx.robot_service.move_ptp.assert_called_once_with(
            position=ctx.paths[0][0][0],
            tool=3,
            user=7,
            velocity=55.0,
            acceleration=66.0,
            wait_to_reach=False,
        )

    def test_commands_move_to_first_point_using_global_motion_settings_when_segment_disabled(self):
        ctx = _make_context()
        ctx.current_path = ctx.paths[0][0]
        ctx.current_settings = ctx.paths[0][1]
        ctx.use_segment_motion_settings = False

        state = handle_issuing_move_to_first_point(ctx)

        self.assertEqual(state, GlueDispensingState.MOVING_TO_FIRST_POINT)
        ctx.robot_service.move_ptp.assert_called_once_with(
            position=ctx.paths[0][0][0],
            tool=3,
            user=7,
            velocity=12.5,
            acceleration=34.0,
            wait_to_reach=False,
        )

    def test_records_error_when_move_to_first_point_raises(self):
        ctx = _make_context()
        ctx.current_path = ctx.paths[0][0]
        ctx.robot_service.move_ptp.side_effect = RuntimeError("boom")

        state = handle_issuing_move_to_first_point(ctx)

        self.assertEqual(state, GlueDispensingState.ERROR)
        self.assertIsNotNone(ctx.last_error)
        self.assertEqual(ctx.last_error.kind, DispensingErrorKind.MOTION)
        self.assertEqual(ctx.last_error.code, DispensingErrorCode.MOVE_TO_FIRST_POINT_FAILED)
        self.assertEqual(ctx.last_error.state, GlueDispensingState.ISSUING_MOVE_TO_FIRST_POINT)
        self.assertEqual(ctx.last_error.operation, "move_ptp_to_first_point")
        self.assertEqual(ctx.last_error.exception_type, "RuntimeError")
        self.assertEqual(ctx.last_error.path_index, 0)
        self.assertEqual(ctx.last_error.point_index, 0)

    def test_returns_paused_when_move_to_first_point_is_interrupted_by_pause(self):
        ctx = _make_context()
        ctx.current_path = ctx.paths[0][0]
        ctx.run_allowed.clear()
        ctx.robot_service.move_ptp.return_value = False

        state = handle_issuing_move_to_first_point(ctx)

        self.assertEqual(state, GlueDispensingState.PAUSED)
        self.assertEqual(ctx.paused_from_state, GlueDispensingState.ISSUING_MOVE_TO_FIRST_POINT)
        self.assertIsNone(ctx.last_error)

    def test_returns_stopped_when_move_to_first_point_is_interrupted_by_stop(self):
        ctx = _make_context()
        ctx.current_path = ctx.paths[0][0]
        ctx.stop_event.set()
        ctx.robot_service.move_ptp.return_value = False

        state = handle_issuing_move_to_first_point(ctx)

        self.assertEqual(state, GlueDispensingState.STOPPED)
        self.assertIsNone(ctx.last_error)


class TestHandleResuming(unittest.TestCase):
    def test_resume_from_execution_state_slices_path_from_saved_progress(self):
        ctx = _make_context()
        full_path, settings = ctx.paths[0]
        ctx.paused_from_state = GlueDispensingState.SENDING_PATH_POINTS
        ctx.current_point_index = 2

        state = handle_resuming(ctx)

        self.assertEqual(state, GlueDispensingState.TURNING_ON_GENERATOR)
        self.assertEqual(ctx.current_path, full_path[2:])
        self.assertEqual(ctx.current_settings, settings)
        ctx.robot_service.move_ptp.assert_not_called()

    def test_resume_after_path_completion_advances_to_next_path(self):
        ctx = _make_context()
        full_path, settings = ctx.paths[0]
        ctx.paused_from_state = GlueDispensingState.WAITING_FOR_PUMP_THREAD
        ctx.current_point_index = len(full_path)

        state = handle_resuming(ctx)

        self.assertEqual(state, GlueDispensingState.STARTING)
        self.assertEqual(ctx.current_path_index, 1)
        self.assertEqual(ctx.current_point_index, 0)

    def test_resume_before_execution_restarts_from_path_beginning(self):
        ctx = _make_context()
        full_path, settings = ctx.paths[0]
        ctx.paused_from_state = GlueDispensingState.MOVING_TO_FIRST_POINT

        state = handle_resuming(ctx)

        self.assertEqual(state, GlueDispensingState.ISSUING_MOVE_TO_FIRST_POINT)
        self.assertEqual(ctx.current_path, full_path)
        self.assertEqual(ctx.current_settings, settings)
        self.assertEqual(ctx.current_point_index, 0)

    def test_resume_waiting_for_final_position_restarts_segment_from_submission_point(self):
        ctx = _make_context()
        full_path, settings = ctx.paths[0]
        ctx.paused_from_state = GlueDispensingState.WAITING_FOR_FINAL_POSITION
        ctx.current_point_index = 1
        ctx.current_segment_start_index = 1
        ctx.segment_trajectory_submitted = True
        ctx.segment_trajectory_completed = False

        state = handle_resuming(ctx)

        self.assertEqual(state, GlueDispensingState.TURNING_ON_GENERATOR)
        self.assertEqual(ctx.current_path, full_path[1:])
        self.assertEqual(ctx.current_settings, settings)
        self.assertEqual(ctx.current_segment_start_index, 1)

    def test_resume_waiting_for_final_position_after_completion_routes_to_pump_shutdown(self):
        ctx = _make_context()
        ctx.paused_from_state = GlueDispensingState.WAITING_FOR_FINAL_POSITION
        ctx.segment_trajectory_completed = True

        state = handle_resuming(ctx)

        self.assertEqual(state, GlueDispensingState.TURNING_OFF_PUMP)


class TestHandleSendingPathPoints(unittest.TestCase):
    def test_pause_before_trajectory_submission_saves_progress_and_origin_state(self):
        ctx = _make_context()
        ctx.current_path_index = 0
        ctx.current_path = ctx.paths[0][0]
        ctx.current_settings = ctx.paths[0][1]
        ctx.current_point_index = 1
        ctx.run_allowed.clear()

        state = handle_sending_path_points(ctx)

        self.assertEqual(state, GlueDispensingState.PAUSED)
        self.assertEqual(ctx.current_path_index, 0)
        self.assertEqual(ctx.current_point_index, 1)
        self.assertEqual(ctx.paused_from_state, GlueDispensingState.SENDING_PATH_POINTS)
        ctx.robot_service.execute_trajectory.assert_not_called()

    def test_submits_remaining_segment_as_single_trajectory(self):
        ctx = _make_context()
        ctx.current_path_index = 0
        ctx.current_path = ctx.paths[0][0]
        ctx.current_settings = ctx.paths[0][1]
        ctx.current_point_index = 1
        ctx.robot_service.get_last_trajectory_command_info.return_value = {"task_id": 17}

        state = handle_sending_path_points(ctx)

        self.assertEqual(state, GlueDispensingState.ROUTING_PATH_COMPLETION_WAIT)
        ctx.robot_service.execute_trajectory.assert_called_once_with(
            path=ctx.current_path[1:],
            rx=0.0,
            ry=0.0,
            rz=0.0,
            vel=55.0,
            acc=66.0,
            blocking=False,
        )
        self.assertTrue(ctx.segment_trajectory_submitted)
        self.assertFalse(ctx.segment_trajectory_completed)
        self.assertEqual(ctx.current_segment_start_index, 1)
        self.assertEqual(ctx.current_segment_task_id, 17)
        self.assertEqual(ctx.current_point_index, 1)

    def test_records_error_when_trajectory_submission_fails(self):
        ctx = _make_context()
        ctx.current_path_index = 0
        ctx.current_path = ctx.paths[0][0]
        ctx.current_settings = ctx.paths[0][1]
        ctx.current_point_index = 1
        ctx.robot_service.execute_trajectory.return_value = False

        state = handle_sending_path_points(ctx)

        self.assertEqual(state, GlueDispensingState.ERROR)
        self.assertIsNotNone(ctx.last_error)
        self.assertEqual(ctx.last_error.kind, DispensingErrorKind.MOTION)
        self.assertEqual(ctx.last_error.code, DispensingErrorCode.EXECUTE_TRAJECTORY_FAILED)
        self.assertEqual(ctx.last_error.operation, "execute_trajectory")
        self.assertEqual(ctx.last_error.path_index, 0)
        self.assertEqual(ctx.last_error.point_index, 1)


class TestHandleMovingToFirstPoint(unittest.TestCase):
    def test_reaching_first_point_advances_send_cursor_to_second_point(self):
        ctx = _make_context()
        ctx.current_path = ctx.paths[0][0]
        ctx.current_settings = ctx.paths[0][1]
        ctx.robot_service.get_current_position.return_value = ctx.current_path[0]

        state = handle_moving_to_first_point(ctx)

        self.assertEqual(state, GlueDispensingState.TURNING_ON_GENERATOR)
        self.assertEqual(ctx.current_point_index, 1)

    def test_records_error_when_current_path_is_missing(self):
        ctx = _make_context()
        ctx.current_path = None
        ctx.current_settings = None

        state = handle_moving_to_first_point(ctx)

        self.assertEqual(state, GlueDispensingState.ERROR)
        self.assertIsNotNone(ctx.last_error)
        self.assertEqual(ctx.last_error.kind, DispensingErrorKind.STATE)
        self.assertEqual(ctx.last_error.code, DispensingErrorCode.MISSING_CURRENT_PATH)
        self.assertEqual(ctx.last_error.state, GlueDispensingState.MOVING_TO_FIRST_POINT)
        self.assertEqual(ctx.last_error.operation, "validate_current_path")
        self.assertIsNone(ctx.last_error.exception_type)


class TestHandlePathCompletionWait(unittest.TestCase):
    def test_routes_to_pump_thread_wait_when_thread_exists(self):
        ctx = _make_context()
        ctx.pump_thread = _FakePumpThread([False], result=(True, 3))

        state = handle_routing_path_completion_wait(ctx)

        self.assertEqual(state, GlueDispensingState.WAITING_FOR_PUMP_THREAD)

    def test_routes_to_final_position_wait_when_no_thread_exists(self):
        ctx = _make_context()

        state = handle_routing_path_completion_wait(ctx)

        self.assertEqual(state, GlueDispensingState.WAITING_FOR_FINAL_POSITION)

    def test_pause_while_waiting_for_pump_thread_captures_progress(self):
        ctx = _make_context()
        ctx.run_allowed.clear()
        ctx.current_path_index = 0
        ctx.pump_thread = _FakePumpThread([True], result=(False, 3))

        state = handle_waiting_for_pump_thread(ctx)

        self.assertEqual(state, GlueDispensingState.PAUSED)
        self.assertEqual(ctx.paused_from_state, GlueDispensingState.WAITING_FOR_PUMP_THREAD)
        self.assertEqual(ctx.current_point_index, 3)
        self.assertIsNone(ctx.pump_thread)

    def test_waiting_for_pump_thread_records_error_details(self):
        ctx = _make_context()
        ctx.current_path_index = 0
        ctx.current_point_index = 2
        ctx.pump_thread = MagicMock()
        ctx.pump_thread.is_alive.side_effect = RuntimeError("thread failed")

        state = handle_waiting_for_pump_thread(ctx)

        self.assertEqual(state, GlueDispensingState.ERROR)
        self.assertIsNone(ctx.pump_thread)
        self.assertIsNotNone(ctx.last_error)
        self.assertEqual(ctx.last_error.kind, DispensingErrorKind.THREAD)
        self.assertEqual(ctx.last_error.code, DispensingErrorCode.PUMP_THREAD_WAIT_FAILED)
        self.assertEqual(ctx.last_error.state, GlueDispensingState.WAITING_FOR_PUMP_THREAD)
        self.assertEqual(ctx.last_error.operation, "wait_for_pump_thread")
        self.assertEqual(ctx.last_error.exception_type, "RuntimeError")
        self.assertEqual(ctx.last_error.point_index, 2)

    def test_waiting_for_pump_thread_records_worker_exception(self):
        ctx = _make_context()
        ctx.current_path_index = 0
        ctx.current_point_index = 1
        ctx.pump_thread = _FakePumpThread([False], result=(False, 4, RuntimeError("worker failed")))

        state = handle_waiting_for_pump_thread(ctx)

        self.assertEqual(state, GlueDispensingState.ERROR)
        self.assertIsNone(ctx.pump_thread)
        self.assertEqual(ctx.current_point_index, 4)
        self.assertIsNotNone(ctx.last_error)
        self.assertEqual(ctx.last_error.kind, DispensingErrorKind.THREAD)
        self.assertEqual(ctx.last_error.code, DispensingErrorCode.PUMP_THREAD_EXECUTION_FAILED)
        self.assertEqual(ctx.last_error.operation, "pump_thread_execution")
        self.assertEqual(ctx.last_error.exception_type, "RuntimeError")

    def test_position_poll_path_completes_when_robot_reaches_final_point(self):
        ctx = _make_context()
        ctx.current_path = ctx.paths[0][0]
        ctx.current_settings = ctx.paths[0][1]
        ctx.current_segment_start_index = 1
        ctx.segment_trajectory_submitted = True
        ctx.robot_service.get_execution_status.return_value = None
        ctx.robot_service.get_current_position.return_value = ctx.current_path[-1]

        state = handle_waiting_for_final_position(ctx)

        self.assertEqual(state, GlueDispensingState.TURNING_OFF_PUMP)
        self.assertTrue(ctx.segment_trajectory_completed)
        self.assertEqual(ctx.current_point_index, len(ctx.current_path))

    def test_waiting_for_final_position_uses_execution_status_before_completing(self):
        ctx = _make_context()
        ctx.current_path = ctx.paths[0][0]
        ctx.current_settings = ctx.paths[0][1]
        ctx.current_segment_start_index = 1
        ctx.current_segment_task_id = 17
        ctx.segment_trajectory_submitted = True
        final_point = ctx.current_path[-1]
        ctx.robot_service.get_execution_status.side_effect = [
            {"is_executing": True, "queue_size": 0, "current_task_id": 17},
            {"is_executing": False, "queue_size": 0, "last_completed_task_id": 17, "last_completed_result": 0},
        ]
        ctx.robot_service.get_current_position.return_value = final_point

        state = handle_waiting_for_final_position(ctx)

        self.assertEqual(state, GlueDispensingState.TURNING_OFF_PUMP)
        self.assertEqual(ctx.robot_service.get_execution_status.call_count, 2)
        self.assertTrue(ctx.segment_trajectory_completed)

    def test_pause_waiting_for_final_position_preserves_segment_start_for_resume(self):
        ctx = _make_context()
        ctx.current_path = ctx.paths[0][0]
        ctx.current_entry = ctx.path_ops.get_current_path_entry()
        ctx.current_settings = ctx.current_entry.settings
        ctx.current_segment_start_index = 1
        ctx.segment_trajectory_submitted = True
        ctx.run_allowed.clear()
        ctx.robot_service.get_current_position.return_value = _point(3)

        state = handle_waiting_for_final_position(ctx)

        self.assertEqual(state, GlueDispensingState.PAUSED)
        self.assertEqual(ctx.paused_from_state, GlueDispensingState.WAITING_FOR_FINAL_POSITION)
        self.assertEqual(ctx.current_point_index, 3)

    def test_resume_waiting_for_final_position_uses_saved_mid_segment_progress(self):
        ctx = _make_context()
        full_path, settings = ctx.paths[0]
        ctx.paused_from_state = GlueDispensingState.WAITING_FOR_FINAL_POSITION
        ctx.current_point_index = 3
        ctx.current_segment_start_index = 1
        ctx.segment_trajectory_submitted = True
        ctx.segment_trajectory_completed = False

        state = handle_resuming(ctx)

        self.assertEqual(state, GlueDispensingState.TURNING_ON_GENERATOR)
        self.assertEqual(ctx.current_path, full_path[3:])
        self.assertEqual(ctx.current_segment_start_index, 3)

    def test_waiting_for_final_position_fails_when_reported_task_finishes_with_error(self):
        ctx = _make_context()
        ctx.current_path = ctx.paths[0][0]
        ctx.current_settings = ctx.paths[0][1]
        ctx.current_segment_start_index = 1
        ctx.current_segment_task_id = 17
        ctx.segment_trajectory_submitted = True
        ctx.robot_service.get_execution_status.return_value = {
            "is_executing": False,
            "queue_size": 0,
            "last_completed_task_id": 17,
            "last_completed_result": -8,
        }

        state = handle_waiting_for_final_position(ctx)

        self.assertEqual(state, GlueDispensingState.ERROR)
        self.assertIsNotNone(ctx.last_error)
        self.assertEqual(ctx.last_error.kind, DispensingErrorKind.MOTION)
        self.assertEqual(ctx.last_error.code, DispensingErrorCode.EXECUTE_TRAJECTORY_FAILED)
        self.assertEqual(ctx.last_error.operation, "wait_for_trajectory_completion")


class TestHandlePumpAdjustmentStartup(unittest.TestCase):
    @patch.object(DispensingPumpThreadOps, "start_for_current_path", autospec=True)
    def test_starts_thread_with_saved_progress_and_waits_for_ready(self, start_thread):
        ctx = _make_context()
        ctx.current_path = ctx.paths[0][0]
        ctx.current_settings = ctx.paths[0][1]
        ctx.current_point_index = 2
        ctx.spray_on = True
        ctx.dispense_channel_service.resolve_motor_address.return_value = 42

        def _start_thread(self, motor_address, reach_end_threshold):
            self._context.pump_thread = MagicMock()
            self._context.pump_ready_event.set()

        start_thread.side_effect = _start_thread

        state = handle_starting_pump_adjustment_thread(ctx, adjust_pump_speed=True)

        self.assertEqual(state, GlueDispensingState.WAITING_FOR_PUMP_THREAD_READY)
        self.assertIsNotNone(ctx.pump_ready_event)
        start_thread.assert_called_once()
        self.assertEqual(
            start_thread.call_args.kwargs["motor_address"],
            42,
        )
        self.assertEqual(
            start_thread.call_args.kwargs["reach_end_threshold"],
            ctx.current_settings[GlueSettingKey.REACH_END_THRESHOLD.value],
        )

    def test_waiting_for_ready_transitions_to_sending_points(self):
        ctx = _make_context()
        ctx.pump_thread = MagicMock()
        ctx.pump_ready_event = MagicMock()
        ctx.pump_ready_event.wait.return_value = True

        state = handle_waiting_for_pump_thread_ready(ctx)

        self.assertEqual(state, GlueDispensingState.SENDING_PATH_POINTS)
        ctx.pump_ready_event.wait.assert_called_once_with(timeout=5.0)

    def test_waiting_for_ready_without_thread_skips_to_sending_points(self):
        ctx = _make_context()
        ctx.pump_thread = None
        ctx.pump_ready_event = threading_event = MagicMock()

        state = handle_waiting_for_pump_thread_ready(ctx)

        self.assertEqual(state, GlueDispensingState.SENDING_PATH_POINTS)
        threading_event.wait.assert_not_called()

    def test_waiting_for_ready_records_error_without_ready_event(self):
        ctx = _make_context()
        ctx.pump_thread = MagicMock()
        ctx.pump_ready_event = None

        state = handle_waiting_for_pump_thread_ready(ctx)

        self.assertEqual(state, GlueDispensingState.ERROR)
        self.assertIsNotNone(ctx.last_error)
        self.assertEqual(ctx.last_error.kind, DispensingErrorKind.THREAD)
        self.assertEqual(ctx.last_error.code, DispensingErrorCode.PUMP_THREAD_READY_MISSING)
        self.assertEqual(ctx.last_error.state, GlueDispensingState.WAITING_FOR_PUMP_THREAD_READY)
        self.assertEqual(ctx.last_error.operation, "wait_for_pump_ready")
        self.assertIsNone(ctx.last_error.exception_type)

    @patch.object(DispensingPumpThreadOps, "start_for_current_path", autospec=True)
    def test_starting_thread_records_startup_exception(self, start_thread):
        ctx = _make_context()
        ctx.current_path = ctx.paths[0][0]
        ctx.current_settings = ctx.paths[0][1]
        ctx.current_point_index = 1
        ctx.spray_on = True
        ctx.dispense_channel_service.resolve_motor_address.return_value = 42
        start_thread.side_effect = RuntimeError("cannot start thread")

        state = handle_starting_pump_adjustment_thread(ctx, adjust_pump_speed=True)

        self.assertEqual(state, GlueDispensingState.ERROR)
        self.assertIsNotNone(ctx.last_error)
        self.assertEqual(ctx.last_error.kind, DispensingErrorKind.THREAD)
        self.assertEqual(ctx.last_error.code, DispensingErrorCode.PUMP_THREAD_START_FAILED)
        self.assertEqual(ctx.last_error.state, GlueDispensingState.STARTING_PUMP_ADJUSTMENT_THREAD)
        self.assertEqual(ctx.last_error.operation, "start_pump_adjustment_thread")
        self.assertEqual(ctx.last_error.exception_type, "RuntimeError")


class TestHandlePumpStates(unittest.TestCase):
    def test_turning_on_pump_starts_motor_once(self):
        ctx = _make_context()
        ctx.current_settings = ctx.paths[0][1]
        ctx.spray_on = True
        ctx.dispense_channel_service.resolve_motor_address.return_value = 8

        state = handle_turning_on_pump(ctx)

        self.assertEqual(state, GlueDispensingState.STARTING_PUMP_ADJUSTMENT_THREAD)
        self.assertTrue(ctx.motor_started)
        ctx.dispense_channel_service.start_dispense.assert_called_once()

    def test_turning_on_pump_records_error_for_invalid_motor_address(self):
        ctx = _make_context()
        ctx.current_settings = ctx.paths[0][1]
        ctx.spray_on = True
        ctx.dispense_channel_service.resolve_motor_address.return_value = -1

        state = handle_turning_on_pump(ctx)

        self.assertEqual(state, GlueDispensingState.ERROR)
        self.assertIsNotNone(ctx.last_error)
        self.assertEqual(ctx.last_error.kind, DispensingErrorKind.CONFIG)
        self.assertEqual(ctx.last_error.code, DispensingErrorCode.INVALID_MOTOR_ADDRESS)
        self.assertEqual(ctx.last_error.state, GlueDispensingState.TURNING_ON_PUMP)
        self.assertEqual(ctx.last_error.operation, "resolve_motor_address")
        self.assertEqual(ctx.last_error.exception_type, None)

    def test_turns_pump_off_before_advancing_path(self):
        ctx = _make_context()
        ctx.current_path_index = 0
        ctx.current_settings = ctx.paths[0][1]
        ctx.spray_on = True
        ctx.motor_started = True
        ctx.dispense_channel_service.resolve_motor_address.return_value = 8

        state = handle_turning_off_pump(ctx, turn_off_pump=True)

        self.assertEqual(state, GlueDispensingState.ADVANCING_PATH)
        self.assertFalse(ctx.motor_started)
        ctx.dispense_channel_service.stop_dispense.assert_called_once()

    def test_turning_on_pump_records_controller_exception_details(self):
        ctx = _make_context()
        ctx.current_settings = ctx.paths[0][1]
        ctx.spray_on = True
        ctx.dispense_channel_service.resolve_motor_address.return_value = 8
        ctx.dispense_channel_service.start_dispense.return_value = (False, "pump on failed")
        ctx.dispense_channel_service.get_last_exception.return_value = RuntimeError("pump on failed")

        state = handle_turning_on_pump(ctx)

        self.assertEqual(state, GlueDispensingState.ERROR)
        self.assertIsNotNone(ctx.last_error)
        self.assertEqual(ctx.last_error.kind, DispensingErrorKind.PUMP)
        self.assertEqual(ctx.last_error.code, DispensingErrorCode.PUMP_ON_FAILED)
        self.assertEqual(ctx.last_error.operation, "pump_on")
        self.assertEqual(ctx.last_error.exception_type, "RuntimeError")

    def test_advancing_path_moves_to_next_path(self):
        ctx = _make_context()
        ctx.current_path_index = 0

        state = handle_advancing_path(ctx)

        self.assertEqual(state, GlueDispensingState.STARTING)
        self.assertEqual(ctx.current_path_index, 1)
        self.assertEqual(ctx.current_point_index, 0)

    def test_advancing_last_path_routes_to_completed(self):
        ctx = _make_context()
        ctx.current_path_index = len(ctx.paths) - 1

        state = handle_advancing_path(ctx)

        self.assertEqual(state, GlueDispensingState.COMPLETED)
        self.assertEqual(ctx.current_path_index, len(ctx.paths))

    def test_turning_off_pump_records_controller_exception_details(self):
        ctx = _make_context()
        ctx.current_path_index = 0
        ctx.current_settings = ctx.paths[0][1]
        ctx.spray_on = True
        ctx.motor_started = True
        ctx.dispense_channel_service.resolve_motor_address.return_value = 8
        ctx.dispense_channel_service.stop_dispense.return_value = (False, "pump off failed")
        ctx.dispense_channel_service.get_last_exception.return_value = RuntimeError("pump off failed")

        state = handle_turning_off_pump(ctx, turn_off_pump=True)

        self.assertEqual(state, GlueDispensingState.ERROR)
        self.assertTrue(ctx.motor_started)
        self.assertIsNotNone(ctx.last_error)
        self.assertEqual(ctx.last_error.kind, DispensingErrorKind.PUMP)
        self.assertEqual(ctx.last_error.code, DispensingErrorCode.PUMP_OFF_FAILED)
        self.assertEqual(ctx.last_error.operation, "pump_off")
        self.assertEqual(ctx.last_error.exception_type, "RuntimeError")


class TestHandleGeneratorStates(unittest.TestCase):
    def test_turning_on_generator_starts_generator_once(self):
        ctx = _make_context()
        ctx.spray_on = True
        ctx.generator_started = False

        with patch(
            "src.robot_systems.glue.processes.glue_dispensing.state_handlers.hardware.generator_handlers.time.sleep"
        ) as sleep_mock:
            state = handle_turning_on_generator(ctx)

        self.assertEqual(state, GlueDispensingState.TURNING_ON_PUMP)
        self.assertTrue(ctx.generator_started)
        ctx.generator.turn_on.assert_called_once_with()
        sleep_mock.assert_not_called()

    def test_turning_on_generator_waits_before_starting_pump_when_configured(self):
        ctx = _make_context()
        ctx.spray_on = True
        ctx.generator_started = False
        ctx.current_settings = _settings(time_between_generator_and_glue=1.25)

        with patch(
            "src.robot_systems.glue.processes.glue_dispensing.state_handlers.hardware.generator_handlers.time.sleep"
        ) as sleep_mock:
            state = handle_turning_on_generator(ctx)

        self.assertEqual(state, GlueDispensingState.TURNING_ON_PUMP)
        ctx.generator.turn_on.assert_called_once_with()
        sleep_mock.assert_called_once_with(1.25)

    def test_completed_keeps_pump_cleanup_and_routes_to_generator_shutdown(self):
        ctx = _make_context()
        ctx.spray_on = True
        ctx.motor_started = True
        ctx.generator_started = True
        ctx.current_settings = ctx.paths[0][1]
        ctx.get_segment_settings()  # convert raw dict to DispensingSegmentSettings
        ctx.dispense_channel_service.resolve_motor_address.return_value = 11

        state = handle_completed(ctx)

        self.assertEqual(state, GlueDispensingState.TURNING_OFF_GENERATOR)
        self.assertFalse(ctx.motor_started)
        self.assertTrue(ctx.generator_started)
        ctx.dispense_channel_service.stop_dispense.assert_called_once()
        ctx.generator.turn_off.assert_not_called()

    def test_turning_off_generator_finishes_completion(self):
        ctx = _make_context()
        ctx.generator_started = True

        state = handle_turning_off_generator(ctx)

        self.assertEqual(state, GlueDispensingState.IDLE)
        self.assertFalse(ctx.generator_started)
        self.assertTrue(ctx.operation_just_completed)
        ctx.generator.turn_off.assert_called_once_with()

    def test_turning_off_generator_records_error_details(self):
        ctx = _make_context()
        ctx.generator_started = True
        ctx.current_point_index = 3
        ctx.generator.turn_off.side_effect = RuntimeError("gen off failed")

        state = handle_turning_off_generator(ctx)

        self.assertEqual(state, GlueDispensingState.ERROR)
        self.assertIsNotNone(ctx.last_error)
        self.assertEqual(ctx.last_error.kind, DispensingErrorKind.GENERATOR)
        self.assertEqual(ctx.last_error.code, DispensingErrorCode.GENERATOR_STOP_FAILED)
        self.assertEqual(ctx.last_error.state, GlueDispensingState.TURNING_OFF_GENERATOR)
        self.assertEqual(ctx.last_error.operation, "turn_off_generator")
        self.assertEqual(ctx.last_error.exception_type, "RuntimeError")
        self.assertEqual(ctx.last_error.point_index, 3)


class TestTerminalErrorHandling(unittest.TestCase):
    def test_error_state_cleans_up_and_returns_idle(self):
        ctx = _make_context()
        ctx.spray_on = True
        ctx.generator_started = True
        ctx.motor_started = True
        ctx.current_settings = ctx.paths[0][1]
        ctx.get_segment_settings()  # convert raw dict to DispensingSegmentSettings
        ctx.dispense_channel_service.resolve_motor_address.return_value = 11
        ctx.fail(
            kind=DispensingErrorKind.PUMP,
            code=DispensingErrorCode.PUMP_ON_FAILED,
            state=GlueDispensingState.TURNING_ON_PUMP,
            operation="pump_on",
            message="pump_on failed",
            exc=RuntimeError("pump failure"),
        )

        state = handle_error(ctx)

        self.assertEqual(state, GlueDispensingState.IDLE)
        ctx.robot_service.stop_motion.assert_called_once_with()
        ctx.dispense_channel_service.stop_dispense.assert_called_once()
        ctx.generator.turn_off.assert_called_once_with()
        self.assertFalse(ctx.motor_started)
        self.assertFalse(ctx.generator_started)
        self.assertFalse(ctx.last_error.recoverable)


class TestDispensingMachineIntegration(unittest.TestCase):
    def test_machine_submits_multi_point_path_as_single_trajectory(self):
        ctx = _make_context()
        path = [_point(1.0), _point(2.0), _point(3.0)]
        ctx.paths = [
            (path, _settings()),
        ]
        ctx.spray_on = False
        ctx.robot_service.move_ptp.return_value = True
        ctx.robot_service.get_current_position.side_effect = [path[0], path[-1]]

        machine = DispensingMachineFactory().build(
            ctx,
            GlueDispensingConfig(
                turn_off_pump_between_paths=True,
                adjust_pump_speed_while_spray=False,
            ),
        )

        machine.start_execution()

        self.assertEqual(machine.current_state, GlueDispensingState.IDLE)
        ctx.robot_service.move_ptp.assert_called_once()
        ctx.robot_service.execute_trajectory.assert_called_once_with(
            path=path[1:],
            rx=0.0,
            ry=0.0,
            rz=0.0,
            vel=55.0,
            acc=66.0,
            blocking=False,
        )
        ctx.robot_service.move_linear.assert_not_called()

    def test_machine_completes_single_point_path(self):
        ctx = _make_machine_context()
        ctx.spray_on = False
        ctx.robot_service.move_ptp.return_value = True
        ctx.robot_service.get_current_position.return_value = ctx.paths[0][0][0]

        machine = DispensingMachineFactory().build(
            ctx,
            GlueDispensingConfig(
                turn_off_pump_between_paths=True,
                adjust_pump_speed_while_spray=False,
            ),
        )

        machine.start_execution()

        self.assertEqual(machine.current_state, GlueDispensingState.IDLE)
        self.assertTrue(ctx.operation_just_completed)
        ctx.robot_service.move_ptp.assert_called_once()
        ctx.robot_service.execute_trajectory.assert_not_called()
        ctx.generator.turn_on.assert_not_called()
        ctx.dispense_channel_service.start_dispense.assert_not_called()

    def test_machine_stops_and_cleans_up_when_stop_requested_before_start(self):
        ctx = _make_machine_context()
        ctx.spray_on = True
        ctx.generator_started = True
        ctx.motor_started = True
        ctx.current_settings = ctx.paths[0][1]
        ctx.get_segment_settings()  # convert raw dict to DispensingSegmentSettings
        ctx.stop_event.set()
        ctx.dispense_channel_service.resolve_motor_address.return_value = 9

        machine = DispensingMachineFactory().build(ctx, GlueDispensingConfig())

        machine.start_execution()

        self.assertEqual(machine.current_state, GlueDispensingState.IDLE)
        ctx.robot_service.stop_motion.assert_called_once_with()
        ctx.generator.turn_off.assert_called_once_with()
        ctx.dispense_channel_service.stop_dispense.assert_called_once()
        self.assertFalse(ctx.generator_started)
        self.assertFalse(ctx.motor_started)

    def test_machine_skips_empty_path_and_completes_next_path(self):
        ctx = _make_context()
        next_point = _point(2.0)
        ctx.paths = [
            ([], _settings()),
            ([next_point], _settings(glue_type="Type B")),
        ]
        ctx.spray_on = False
        ctx.robot_service.move_ptp.return_value = True
        ctx.robot_service.get_current_position.return_value = next_point

        machine = DispensingMachineFactory().build(
            ctx,
            GlueDispensingConfig(
                turn_off_pump_between_paths=True,
                adjust_pump_speed_while_spray=False,
            ),
        )

        machine.start_execution()

        self.assertEqual(machine.current_state, GlueDispensingState.IDLE)
        self.assertTrue(ctx.operation_just_completed)
        self.assertEqual(ctx.current_path_index, 2)
        self.assertEqual(ctx.robot_service.move_ptp.call_count, 1)
        ctx.robot_service.execute_trajectory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
    def test_submits_trajectory_using_global_motion_settings_when_segment_disabled(self):
        ctx = _make_context()
        ctx.current_path_index = 0
        ctx.current_path = ctx.paths[0][0]
        ctx.current_settings = ctx.paths[0][1]
        ctx.current_point_index = 1
        ctx.use_segment_motion_settings = False

        state = handle_sending_path_points(ctx)

        self.assertEqual(state, GlueDispensingState.ROUTING_PATH_COMPLETION_WAIT)
        ctx.robot_service.execute_trajectory.assert_called_once_with(
            path=ctx.current_path[1:],
            rx=0.0,
            ry=0.0,
            rz=0.0,
            vel=12.5,
            acc=34.0,
            blocking=False,
        )
