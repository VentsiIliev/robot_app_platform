import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from src.engine.vision.i_capture_snapshot_service import VisionCaptureSnapshot
from src.robot_systems.paint.processes.paint.config import PaintMagazineLoadConfig, PaintProcessConfig
from src.robot_systems.paint.processes.paint.execution_control import PaintExecutionControl
from src.robot_systems.paint.processes.paint.execution_machine import (
    PaintExecutionContext,
    PaintExecutionMachineFactory,
    PaintExecutionState,
    PaintExecutionTransitions,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.common.motion_handlers import (
    motion_failure_message,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff.dropoff_handlers import (
    open_dropoff_passage_for_preparation,
)
from src.robot_systems.paint.processes.paint.magazine_load_service import PaintMagazineLoadService


class TestDropoffPassagePreparation(unittest.TestCase):
    def test_opens_configured_passage_before_route_planning(self):
        robot_service = MagicMock()
        robot_service.set_motion_passage_closed.return_value = True
        executor = SimpleNamespace(
            _dropoff_motion_corridor_id="workpiece_drop_opening",
            _robot_service=robot_service,
            _dropoff_position_provider=object(),
            _last_process_end_pose=[0, 0, 10, 180, 0, 0],
            _configured_contact_motion_plane="xy_z_rz",
            _paint_process_config=lambda: SimpleNamespace(
                dropoff=SimpleNamespace(strategy="movement_group")
            ),
            _read_provider_position=lambda _provider: [0, 0, 10, 180, 0, 0],
        )

        ok, message = open_dropoff_passage_for_preparation(executor)

        self.assertTrue(ok)
        self.assertEqual("", message)
        robot_service.set_motion_passage_closed.assert_called_once_with(
            "workpiece_drop_opening", False
        )

    def test_rejects_preparation_when_passage_cannot_open(self):
        robot_service = MagicMock()
        robot_service.set_motion_passage_closed.return_value = False
        executor = SimpleNamespace(
            _dropoff_motion_corridor_id="workpiece_drop_opening",
            _robot_service=robot_service,
            _dropoff_position_provider=object(),
            _last_process_end_pose=[0, 0, 10, 180, 0, 0],
            _configured_contact_motion_plane="xy_z_rz",
            _paint_process_config=lambda: SimpleNamespace(
                dropoff=SimpleNamespace(strategy="movement_group")
            ),
            _read_provider_position=lambda _provider: [0, 0, 10, 180, 0, 0],
        )

        ok, message = open_dropoff_passage_for_preparation(executor)

        self.assertFalse(ok)
        self.assertIn("failed to open passage 'workpiece_drop_opening'", message)


class TestPaintExecutionMachineScaffold(unittest.TestCase):
    def test_starting_routes_to_capture_when_magazine_load_is_disabled(self):
        ctx = PaintExecutionContext(
            production_service=MagicMock(),
            stop_requested=lambda: False,
            control=PaintExecutionControl(),
            magazine_config=PaintMagazineLoadConfig(enabled=False),
        )
        machine = PaintExecutionMachineFactory().build(ctx)

        progressed = machine.step()

        self.assertTrue(progressed)
        self.assertEqual(PaintExecutionState.CAPTURE_WORKPIECE, machine.current_state)
        self.assertEqual(PaintExecutionState.STARTING, ctx.current_state)

    def test_starting_routes_to_magazine_load_when_enabled(self):
        ctx = PaintExecutionContext(
            production_service=MagicMock(),
            stop_requested=lambda: False,
            control=PaintExecutionControl(),
            magazine_config=PaintMagazineLoadConfig(enabled=True),
        )
        machine = PaintExecutionMachineFactory().build(ctx)

        progressed = machine.step()

        self.assertTrue(progressed)
        self.assertEqual(PaintExecutionState.MAGAZINE_LOAD, machine.current_state)

    def test_starting_routes_to_first_fine_magazine_state_for_real_magazine_service(self):
        service = MagicMock()
        service._magazine_load_service = PaintMagazineLoadService(
            navigation=MagicMock(),
            capture_snapshot_service=MagicMock(),
            path_executor=MagicMock(),
        )
        ctx = PaintExecutionContext(
            production_service=service,
            stop_requested=lambda: False,
            control=PaintExecutionControl(),
            magazine_config=PaintMagazineLoadConfig(enabled=True),
        )
        machine = PaintExecutionMachineFactory().build(ctx)

        progressed = machine.step()

        self.assertTrue(progressed)
        self.assertEqual(PaintExecutionState.MAGAZINE_MOVE_TO_MAGAZINE, machine.current_state)
        service._set_dashboard_live_view_paused.assert_called_once_with(
            True,
            reason="magazine workflow robot motion starting",
        )

    def test_starting_routes_to_stopped_when_stop_requested(self):
        ctx = PaintExecutionContext(
            production_service=object(),
            stop_requested=lambda: True,
            control=PaintExecutionControl(),
        )
        machine = PaintExecutionMachineFactory().build(ctx)

        progressed = machine.step()

        self.assertTrue(progressed)
        self.assertEqual(PaintExecutionState.STOPPED, machine.current_state)
        self.assertFalse(ctx.result_ok)
        self.assertEqual("Paint process stopped", ctx.result_message)

    def test_transition_rules_include_planned_execution_phases(self):
        rules = PaintExecutionTransitions.get_rules()

        self.assertIn(
            PaintExecutionState.EXECUTE_PAINT,
            rules[PaintExecutionState.BUILD_EXECUTION_PLAN],
        )
        self.assertIn(
            PaintExecutionState.COMPLETED,
            rules[PaintExecutionState.EXECUTE_PAINT],
        )

    def test_machine_records_state_timing_when_enabled(self):
        ctx = PaintExecutionContext(
            production_service=MagicMock(),
            stop_requested=lambda: False,
            control=PaintExecutionControl(),
            process_config=PaintProcessConfig(enable_execution_state_timing=True),
            magazine_config=PaintMagazineLoadConfig(enabled=False),
        )
        machine = PaintExecutionMachineFactory().build(ctx)

        machine.step()

        self.assertIsNotNone(ctx.state_timing_recorder)
        self.assertEqual(1, len(ctx.state_timing_recorder.state_records))
        record = ctx.state_timing_recorder.state_records[0]
        self.assertEqual("STARTING", record.state)
        self.assertEqual("CAPTURE_WORKPIECE", record.next_state)

    def test_machine_skips_state_timing_when_disabled(self):
        ctx = PaintExecutionContext(
            production_service=MagicMock(),
            stop_requested=lambda: False,
            control=PaintExecutionControl(),
            process_config=PaintProcessConfig(enable_execution_state_timing=False),
            magazine_config=PaintMagazineLoadConfig(enabled=False),
        )
        machine = PaintExecutionMachineFactory().build(ctx)

        machine.step()

        self.assertIsNone(ctx.state_timing_recorder)

    def test_machine_executes_mocked_single_cycle_to_completion(self):
        service = MagicMock()
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[
                np.array([[[0.0, 0.0]], [[2.0, 0.0]], [[2.0, 2.0]], [[0.0, 2.0]]], dtype=np.float32),
            ],
            source="paint_process",
        )
        service._workpiece_preparation.prepare_workpiece.return_value = (
            {"id": "wp-1"},
            "Prepared workpiece",
        )
        service._path_preparation_service.build_execution_plan.return_value = {"plan": 1}
        service._path_executor.execute_paint_process.return_value = (True, "Paint completed")
        service._pause_dashboard_live_view_after_capture.return_value = False
        service._path_debug_plots_enabled.return_value = False

        ctx = PaintExecutionContext(
            production_service=service,
            stop_requested=lambda: False,
            control=PaintExecutionControl(),
            magazine_config=PaintMagazineLoadConfig(enabled=False),
        )
        machine = PaintExecutionMachineFactory().build(ctx)

        machine.start_execution()

        self.assertTrue(ctx.result_ok)
        self.assertEqual("Prepared workpiece: Paint completed", ctx.result_message)
        self.assertEqual(PaintExecutionState.IDLE, machine.current_state)
        service._capture_snapshot_service.capture_snapshot.assert_called_once_with(source="paint_process")
        service._path_preparation_service.build_execution_plan.assert_called_once_with(
            {"id": "wp-1"},
            skip_debug_plot=True,
        )
        service._path_executor.execute_paint_process.assert_called_once()
        self.assertIs(service._path_executor.execute_paint_process.call_args.args[0], ctx.execution_plan)
        self.assertIs(service._path_executor.execute_paint_process.call_args.kwargs["control"], ctx.control)

    def test_machine_records_no_contour_as_error_result(self):
        service = MagicMock()
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[],
            source="paint_process",
        )
        service._pause_dashboard_live_view_after_capture.return_value = False

        ctx = PaintExecutionContext(
            production_service=service,
            stop_requested=lambda: False,
            control=PaintExecutionControl(),
            magazine_config=PaintMagazineLoadConfig(enabled=False),
        )
        machine = PaintExecutionMachineFactory().build(ctx)

        machine.start_execution()

        self.assertFalse(ctx.result_ok)
        self.assertEqual("No usable contour detected", ctx.result_message)
        self.assertEqual(PaintExecutionState.IDLE, machine.current_state)
        service._workpiece_preparation.prepare_workpiece.assert_not_called()

    def test_machine_uses_phased_motion_states_for_real_executor_shape(self):
        events = []
        service = MagicMock()
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[
                np.array([[[0.0, 0.0]], [[2.0, 0.0]], [[2.0, 2.0]], [[0.0, 2.0]]], dtype=np.float32),
            ],
            source="paint_process",
        )
        service._workpiece_preparation.prepare_workpiece.return_value = (
            {"id": "wp-1"},
            "Prepared workpiece",
        )
        service._path_preparation_service.build_execution_plan.return_value = SimpleNamespace(
            execution_jobs=[{"job": 1}],
        )
        service._path_executor = _FakePhasedPathExecutor(events)
        service._next_cycle_start_target.return_value = None
        service._pause_dashboard_live_view_after_capture.return_value = False
        service._path_debug_plots_enabled.return_value = False

        ctx = PaintExecutionContext(
            production_service=service,
            stop_requested=lambda: False,
            control=PaintExecutionControl(),
            magazine_config=PaintMagazineLoadConfig(enabled=False),
        )
        machine = PaintExecutionMachineFactory().build(ctx)

        machine.start_execution()

        self.assertTrue(ctx.result_ok)
        self.assertEqual(
            "Prepared workpiece: Paint process completed for 1 path(s), 5 waypoints",
            ctx.result_message,
        )
        self.assertEqual(
            [
                "pickup",
                "paint_contact",
                "Moving to dropoff pose before unwind",
                "unwind",
                "vacuum_off",
                "post_return",
            ],
            events,
        )
        self.assertEqual(PaintExecutionState.IDLE, machine.current_state)

class TestMotionFailureMessage(unittest.TestCase):
    def test_uses_backend_error_from_latest_trajectory_response(self):
        service = MagicMock()
        service.get_last_trajectory_command_info.return_value = {
            "raw": {
                "error": (
                    "ordered-chain planning failed: follow path direct contour IK failed: "
                    "batch_ik_failed index=613"
                ),
                "result": -1,
            }
        }

        message = motion_failure_message(service, "chain failed with code -1")

        self.assertEqual(
            "ordered-chain planning failed: follow path direct contour IK failed: "
            "batch_ik_failed index=613",
            message,
        )

    def test_uses_fallback_when_backend_has_no_detail(self):
        service = MagicMock()
        service.get_last_trajectory_command_info.return_value = {"raw": {"result": -1}}
        service.get_connection_details.return_value = {}

        message = motion_failure_message(service, "chain failed with code -1")

        self.assertEqual("chain failed with code -1", message)


class _FakePhasedPathExecutor:
    supports_paint_motion_states = True

    def __init__(self, events: list[str]) -> None:
        self._events = events
        self._active_execution_control = None
        self._debug_dump_dir = None
        self._dropoff_unwind_prepared = False
        self._configured_contact_motion_plane = "xy_z_rz"
        self._last_process_end_pose = [1, 2, 3, 4, 5, 6]
        self._last_pickup_plan = SimpleNamespace(align_pose=[1, 2, 3, 4, 5, 6])
        self._dropoff_position_provider = object()
        self._robot_service = SimpleNamespace(unwind_joint6=self._unwind_joint6)
        self._motion = SimpleNamespace(
            move_pickup_phase=self._move_pickup_phase,
            turn_vacuum_off=self._turn_vacuum_off,
        )
        self._pickup = SimpleNamespace(execute=self._pickup_execute)
        self._paint_contact = SimpleNamespace(execute=self._paint_contact_execute)
        self._edge_cleanup = SimpleNamespace(
            cancel_early_preplanning=lambda: events.append("cancel_cleanup"),
            should_run_after_xz_ry=lambda: False,
            should_run_after_xy_rz=lambda: False,
        )
        self._post_execute_callback = self._post_return

    def _refresh_paint_process_config_snapshot(self) -> None:
        pass

    def _apply_paint_process_contact_config(self) -> None:
        pass

    def _diagnostics_artifacts_enabled(self) -> bool:
        return False

    def _read_provider_position(self, _provider):
        return [1, 2, 3, 4, 5, 6]

    def _paint_process_config(self):
        return SimpleNamespace(
            dropoff=SimpleNamespace(
                strategy="movement_group",
                release_align_vel_percent=20.0,
                release_align_acc_percent=20.0,
                release_align_motion_type="ptp",
                release_align_blendR=0.0,
                allow_sub_zero_dropoff=False,
            ),
            dropoff_safe_travel=SimpleNamespace(
                enabled=False,
                positions=[],
                position=[],
            ),
            navigation_return=SimpleNamespace(
                unwind_vel_percent=10.0,
                unwind_acc_percent=10.0,
            ),
        )

    def _wait_for_paint_resume(self, _control) -> bool:
        return True

    def _read_configured_waypoints(self, *_args, **_kwargs):
        return []

    def _pickup_execute(self, _plan) -> tuple[bool, str]:
        self._events.append("pickup")
        return True, ""

    def _paint_contact_execute(self, _plan, *, control=None) -> tuple[bool, str, int]:
        self._events.append("paint_contact")
        return True, "", 5

    def _prepare_dropoff_joint6_unwind(self) -> tuple[bool, str]:
        raise AssertionError("dropoff preparation should be owned by the handler")

    def _move_pickup_phase(
        self, label: str, pose: list[float], *, velocity: float, acceleration: float, **_kwargs
    ) -> bool:
        self._events.append(label)
        return True

    def _unwind_joint6(self, **_kwargs) -> bool:
        self._events.append("unwind")
        return True

    def _turn_vacuum_off(self) -> tuple[bool, str]:
        self._events.append("vacuum_off")
        return True, ""

    def _post_return(self) -> bool:
        self._events.append("post_return")
        return True


if __name__ == "__main__":
    unittest.main()
