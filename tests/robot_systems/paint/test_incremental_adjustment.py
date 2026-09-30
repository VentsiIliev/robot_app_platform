import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.robot_systems.paint.processes.paint.incremental_adjustment import (
    AdjustmentStep,
    PaintAdjustmentSession,
    PaintPathCursor,
)
from src.robot_systems.paint.processes.paint.execute.incremental_paint_executor import (
    run_incremental_paint_contact,
)
from src.robot_systems.paint.processes.paint.adjustment_settings_serializer import (
    PaintAdjustmentSettingsSerializer,
)
from src.robot_systems.paint.processes.paint.paint_process import PaintProcess
from src.shared_contracts.events.process_events import ProcessState


class IncrementalAdjustmentTests(unittest.TestCase):
    def test_settings_serializer_defaults_require_explicit_inspection_offset(self):
        serializer = PaintAdjustmentSettingsSerializer()
        self.assertEqual(serializer.get_default(), AdjustmentStep(10, 0, 0))
        with self.assertRaises(ValueError):
            serializer.get_default().validate()
        self.assertEqual(
            serializer.from_dict({"length_mm": 12, "paint_axis_offset_mm": 30}),
            AdjustmentStep(12, 30, 0),
        )

    def test_adjustment_process_requires_explicit_finish(self):
        production = MagicMock()
        entered = threading.Event()
        release = threading.Event()

        def run_once(_stop, *, adjustment_session=None):
            self.assertIsNotNone(adjustment_session)
            adjustment_session.inspection_ready(10, 10, complete=True)
            entered.set()
            release.wait(timeout=1)
            return True, "Paint completed"

        production.run_once.side_effect = run_once
        process = PaintProcess(production_service=production, messaging=MagicMock())
        self.assertTrue(process.start_adjustment_cycle())
        self.assertTrue(entered.wait(timeout=1))
        self.assertEqual(process.state, ProcessState.RUNNING)
        self.assertFalse(process.paint_next_adjustment_section(AdjustmentStep(10, 30, -20)))
        self.assertTrue(process.finish_adjustment_cycle())
        release.set()
        process._thread.join(timeout=1)
        self.assertEqual(process.state, ProcessState.STOPPED)

    def test_cursor_splits_exact_cartesian_lengths_without_repainting(self):
        cursor = PaintPathCursor([(0, 0, 0, 0, 0, 0), (7, 0, 0, 0, 0, 70), (25, 0, 0, 0, 0, 250)])
        first = cursor.take(10)
        self.assertAlmostEqual(first[-1][0], 10)
        self.assertAlmostEqual(first[-1][5], 100)
        second = cursor.take(10)
        self.assertEqual(second[0], first[-1])
        self.assertAlmostEqual(second[-1][0], 20)
        third = cursor.take(10)
        self.assertAlmostEqual(third[-1][0], 25)
        self.assertAlmostEqual(cursor.travelled_mm, 25)
        self.assertTrue(cursor.complete)
        self.assertEqual(cursor.take(10), [])

    def test_finish_after_final_section_and_explicit_request(self):
        session = PaintAdjustmentSession()
        step = AdjustmentStep(10, 30, -20)
        session.inspection_ready(0, 25, complete=False)
        self.assertFalse(session.request_finish())
        self.assertTrue(session.request_next(step))
        self.assertFalse(session.request_next(step))
        self.assertEqual(session.wait_for_command(lambda: False), ("next", step))
        session.inspection_ready(25, 25, complete=True)
        self.assertFalse(session.request_next(step))
        self.assertTrue(session.request_finish())
        self.assertEqual(session.wait_for_command(lambda: False), ("finish", None))

    def test_finish_after_partial_section_skips_remaining_path(self):
        session = PaintAdjustmentSession()
        session.inspection_ready(0, 25, complete=False)
        self.assertFalse(session.request_finish())
        session.inspection_ready(10, 25, complete=False)
        self.assertTrue(session.request_finish())
        self.assertEqual(session.wait_for_command(lambda: False), ("finish", None))

    def test_executor_waits_for_each_press_then_detaches_and_finishes(self):
        owner = MagicMock()
        owner._contact_motion_config.planar_axes = ("x", "y")
        owner._contact_motion_config.translation_axis = "x"
        owner._contact_motion_config.planar_coordinate_indices = (0, 1)
        owner._contact_motion_config.direction_sign = 1
        owner._pickup_tool = 2
        owner._pickup_user = 1
        owner._robot_service.execute_ordered_motion_chain.return_value = 0

        def prepare(_plan, **kwargs):
            kwargs["collected_command_paths"].append([
                [0, 0, 0, 0, 0, 0], [25, 0, 0, 0, 0, 250]
            ])
            kwargs["collected_command_jobs"].append(
                SimpleNamespace(velocity_percent=10, acceleration_percent=10)
            )
            return True, "", 2

        owner._paint_contact.execute.side_effect = prepare
        session = PaintAdjustmentSession()
        ctx = SimpleNamespace(
            production_service=SimpleNamespace(_path_executor=owner),
            adjustment_session=session,
            execution_plan=object(),
            should_stop=lambda: False,
            run_allowed=threading.Event(),
            control=SimpleNamespace(pause_requested=lambda: False),
        )
        ctx.run_allowed.set()
        result = []
        worker = threading.Thread(target=lambda: result.append(run_incremental_paint_contact(ctx)))
        worker.start()
        for expected in (10, 20, 25):
            self._wait_for(session, "inspect", expected - (10 if expected < 25 else 5))
            self.assertTrue(session.request_next(AdjustmentStep(10, 30, -20)))
            self._wait_for(session, "inspect", expected)
        self.assertEqual(owner._robot_service.execute_ordered_motion_chain.call_count, 3)
        first, second, third = [
            call.kwargs["segments"]
            for call in owner._robot_service.execute_ordered_motion_chain.call_args_list
        ]
        self.assertEqual([command.label for command in first], [
            "Adjustment attach to paint contact",
            "Adjustment paint section 1",
            "Adjustment detach along paint axis",
            "Adjustment move to camera inspection pose",
        ])
        self.assertEqual(second[0].label, "Adjustment return to paint-axis clearance")
        self.assertEqual(second[1].label, "Adjustment attach to paint contact")
        self.assertEqual(third[0].label, "Adjustment return to paint-axis clearance")
        self.assertTrue(session.request_finish())
        worker.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, [(True, "")])
        self.assertAlmostEqual(owner._last_process_end_pose[0], -5)
        self.assertAlmostEqual(owner._last_process_end_pose[1], -20)
        self.assertAlmostEqual(owner._last_paint_contact_end_rz, 250)

    def test_executor_finishes_from_partial_inspection_pose(self):
        owner = MagicMock()
        owner._contact_motion_config.planar_axes = ("x", "y")
        owner._contact_motion_config.translation_axis = "x"
        owner._contact_motion_config.planar_coordinate_indices = (0, 1)
        owner._contact_motion_config.direction_sign = 1
        owner._robot_service.execute_ordered_motion_chain.return_value = 0

        def prepare(_plan, **kwargs):
            kwargs["collected_command_paths"].append([
                [0, 0, 0, 0, 0, 0], [25, 0, 0, 0, 0, 250]
            ])
            kwargs["collected_command_jobs"].append(
                SimpleNamespace(velocity_percent=10, acceleration_percent=10)
            )
            return True, "", 2

        owner._paint_contact.execute.side_effect = prepare
        session = PaintAdjustmentSession()
        allowed = threading.Event()
        allowed.set()
        ctx = SimpleNamespace(
            production_service=SimpleNamespace(_path_executor=owner),
            adjustment_session=session,
            execution_plan=object(),
            should_stop=lambda: False,
            run_allowed=allowed,
            control=SimpleNamespace(pause_requested=lambda: False),
        )
        result = []
        worker = threading.Thread(target=lambda: result.append(run_incremental_paint_contact(ctx)))
        worker.start()
        self._wait_for(session, "inspect", 0)
        self.assertFalse(session.request_finish())
        self.assertTrue(session.request_next(AdjustmentStep(10, 30, -20)))
        self._wait_for(session, "inspect", 10)
        self.assertTrue(session.request_finish())
        worker.join(timeout=1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(result, [(True, "")])
        self.assertEqual(owner._robot_service.execute_ordered_motion_chain.call_count, 1)
        self.assertAlmostEqual(owner._last_process_end_pose[0], -20)
        self.assertAlmostEqual(owner._last_paint_contact_end_rz, 100)

    def _wait_for(self, session, phase, distance):
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            state, travelled, _total = session.snapshot()
            if state == phase and abs(travelled - distance) < 1e-6:
                return
            time.sleep(0.005)
        self.fail(f"Expected {phase} at {distance} mm, got {session.snapshot()}")
