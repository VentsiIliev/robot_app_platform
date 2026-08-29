import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock, patch

import numpy as np

from src.engine.vision.i_capture_snapshot_service import VisionCaptureSnapshot
from src.robot_systems.paint.component_ids import ProcessID
from src.robot_systems.paint.processes.paint.config import PaintMagazineLoadConfig, PaintProcessConfig
from src.robot_systems.paint.processes.paint.dashboard_live_view_events import PaintDashboardLiveViewTopics
from src.robot_systems.paint.processes.paint.magazine_load.state import MagazineLoadState, MagazineLoadTransitions
from src.robot_systems.paint.processes.paint.magazine_load_result import NO_WORKPIECE_AT_MAGAZINE
from src.robot_systems.paint.processes.paint.magazine_load_service import PaintMagazineLoadService
from src.robot_systems.paint.processes.paint.paint_process import PaintProcess
from src.robot_systems.paint.processes.paint.paint_production_service import PaintProductionService
from src.robot_systems.paint.processes.paint.plan.workpiece_preparation_service import (
    PaintWorkpiecePreparationService,
)
from src.shared_contracts.events.process_events import ProcessState, ProcessTopics


def _square(size: float) -> np.ndarray:
    return np.array(
        [[[0.0, 0.0]], [[size, 0.0]], [[size, size]], [[0.0, size]]],
        dtype=np.float32,
    )


class TestPaintProductionServiceIntegration(unittest.TestCase):

    def _make_service(self):
        return PaintProductionService(
            workpiece_preparation_service=MagicMock(),
            capture_snapshot_service=MagicMock(),
            path_preparation_service=MagicMock(),
            path_executor=MagicMock(),
        )

    def test_run_start_resets_learned_servo_pickup_height(self):
        service = self._make_service()
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame", contours=[], source="paint_process"
        )

        service.run_once()

        service._path_executor.reset_learned_servo_pickup_height.assert_called_once_with()

    def test_resume_resets_learned_servo_pickup_height(self):
        service = self._make_service()

        service.resume_current_phase()

        service._path_executor.reset_learned_servo_pickup_height.assert_called_once_with()

    def test_run_once_executes_capture_prepare_plan_and_paint_flow(self):
        service = self._make_service()
        small = _square(1.0)
        large = _square(3.0)
        snapshot = VisionCaptureSnapshot(frame="frame", contours=[small, large], source="paint_process")
        service._capture_snapshot_service.capture_snapshot.return_value = snapshot
        raw_workpiece = {"id": "wp-1"}
        execution_plan = {"plan": 1}
        service._workpiece_preparation.prepare_workpiece.return_value = (raw_workpiece, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.return_value = execution_plan
        service._path_executor.execute_paint_process.return_value = (True, "Paint completed")

        ok, msg = service.run_once()

        self.assertTrue(ok)
        self.assertEqual(msg, "Prepared workpiece: Paint completed")
        service._capture_snapshot_service.capture_snapshot.assert_called_once_with(source="paint_process")
        prepared_contour, prepared_frame = service._workpiece_preparation.prepare_workpiece.call_args.args
        self.assertTrue(np.array_equal(prepared_contour, large))
        self.assertEqual(prepared_frame, "frame")
        service._path_preparation_service.build_execution_plan.assert_called_once_with(
            raw_workpiece,
            skip_debug_plot=True,
        )
        service._path_executor.execute_paint_process.assert_called_once()
        self.assertIs(service._path_executor.execute_paint_process.call_args.args[0], execution_plan)
        self.assertIsNotNone(service._path_executor.execute_paint_process.call_args.kwargs.get("control"))

    def test_run_once_stops_before_planning_when_matching_returns_no_workpiece(self):
        service = self._make_service()
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[_square(2.0)],
            source="paint_process",
        )
        service._workpiece_preparation.prepare_workpiece.return_value = (
            None,
            "No matched workpiece",
        )

        ok, msg = service.run_once()

        self.assertFalse(ok)
        self.assertEqual(msg, "No matched workpiece")
        service._path_preparation_service.build_execution_plan.assert_not_called()
        service._path_executor.execute_paint_process.assert_not_called()

    def test_run_once_freezes_brightness_after_capture_when_auto_enabled(self):
        vision = MagicMock()
        vision.get_auto_brightness_enabled.return_value = True
        events = []
        service = self._make_service()
        service._vision_service = vision
        service._capture_snapshot_service.capture_snapshot.side_effect = (
            lambda **_kwargs: events.append("capture") or VisionCaptureSnapshot(
                frame="frame",
                contours=[_square(2.0)],
                source="paint_process",
            )
        )
        service._workpiece_preparation.prepare_workpiece.return_value = ({"id": "wp-1"}, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.return_value = {"plan": 1}
        service._path_executor.execute_paint_process.side_effect = (
            lambda *args, **kwargs: events.append("execute") or (True, "Paint completed")
        )
        vision.lock_auto_brightness_adjustment.side_effect = lambda: events.append("lock")
        vision.unlock_auto_brightness_adjustment.side_effect = lambda: events.append("unlock")

        ok, msg = service.run_once()

        self.assertTrue(ok, msg)
        vision.lock_auto_brightness_adjustment.assert_called_once_with()
        vision.unlock_auto_brightness_adjustment.assert_called_once_with()
        self.assertEqual(["capture", "lock", "execute", "unlock"], events)
        self.assertFalse(service._brightness_locked)

    def test_run_once_restores_existing_brightness_lock_before_magazine_and_paint_capture(self):
        vision = MagicMock()
        vision.get_auto_brightness_enabled.return_value = True
        config = PaintMagazineLoadConfig(enabled=True, camera_settle_s=0.0, release_settle_s=0.0)
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            run_while_workpiece_found=False,
            magazine_load=config,
        )
        magazine_load = MagicMock()
        events = []
        magazine_load.load_to_calibration.side_effect = lambda *_args: events.append("magazine_load") or (True, "Loaded")
        service = PaintProductionService(
            workpiece_preparation_service=MagicMock(),
            capture_snapshot_service=MagicMock(),
            path_preparation_service=MagicMock(),
            path_executor=MagicMock(),
            paint_process_config_service=config_service,
            magazine_load_service=magazine_load,
            vision_service=vision,
        )
        service._brightness_locked = True
        service._capture_snapshot_service.capture_snapshot.side_effect = (
            lambda **_kwargs: events.append("paint_capture") or VisionCaptureSnapshot(
                frame="frame",
                contours=[_square(2.0)],
                source="paint_process",
            )
        )
        service._workpiece_preparation.prepare_workpiece.return_value = ({"id": "wp-1"}, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.return_value = {"plan": 1}
        service._path_executor.execute_paint_process.side_effect = (
            lambda *args, **kwargs: events.append("paint_execution") or (True, "Paint completed")
        )
        vision.unlock_auto_brightness_adjustment.side_effect = lambda: events.append("unlock")
        vision.lock_auto_brightness_adjustment.side_effect = lambda: events.append("lock")

        ok, msg = service.run_once()

        self.assertTrue(ok, msg)
        self.assertEqual(
            ["unlock", "magazine_load", "paint_capture", "lock", "paint_execution", "unlock"],
            events,
        )
        self.assertEqual(2, vision.unlock_auto_brightness_adjustment.call_count)
        vision.lock_auto_brightness_adjustment.assert_called_once_with()
        self.assertFalse(service._brightness_locked)

    def test_run_once_pauses_dashboard_live_view_after_paint_capture_until_cycle_finishes(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            magazine_load=None,
            pause_dashboard_live_view_after_capture=True,
        )
        messaging = MagicMock()
        service = PaintProductionService(
            workpiece_preparation_service=MagicMock(),
            capture_snapshot_service=MagicMock(),
            path_preparation_service=MagicMock(),
            path_executor=MagicMock(),
            paint_process_config_service=config_service,
            messaging_service=messaging,
        )
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="captured-frame",
            contours=[_square(2.0)],
            source="paint_process",
        )
        service._workpiece_preparation.prepare_workpiece.return_value = ({"id": "wp-1"}, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.return_value = {"plan": 1}
        service._path_executor.execute_paint_process.return_value = (True, "Paint completed")

        ok, msg = service.run_once()

        self.assertTrue(ok, msg)
        published = [
            call.args[1]
            for call in messaging.publish.call_args_list
            if call.args[0] == PaintDashboardLiveViewTopics.STATE
        ]
        self.assertEqual([False, True, False], [event.paused for event in published])
        self.assertIsNone(published[0].image)
        self.assertEqual("captured-frame", published[1].image)
        self.assertIsNone(published[2].image)

    def test_run_once_keeps_dashboard_live_view_enabled_when_capture_pause_disabled(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            magazine_load=None,
            pause_dashboard_live_view_after_capture=False,
        )
        messaging = MagicMock()
        service = PaintProductionService(
            workpiece_preparation_service=MagicMock(),
            capture_snapshot_service=MagicMock(),
            path_preparation_service=MagicMock(),
            path_executor=MagicMock(),
            paint_process_config_service=config_service,
            messaging_service=messaging,
        )
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="captured-frame",
            contours=[_square(2.0)],
            source="paint_process",
        )
        service._workpiece_preparation.prepare_workpiece.return_value = ({"id": "wp-1"}, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.return_value = {"plan": 1}
        service._path_executor.execute_paint_process.return_value = (True, "Paint completed")

        ok, msg = service.run_once()

        self.assertTrue(ok, msg)
        published = [
            call.args[1]
            for call in messaging.publish.call_args_list
            if call.args[0] == PaintDashboardLiveViewTopics.STATE
        ]
        self.assertEqual([False, False], [event.paused for event in published])
        self.assertTrue(all(event.image is None for event in published))

    def test_run_once_restores_brightness_when_no_contour_found(self):
        vision = MagicMock()
        vision.get_auto_brightness_enabled.return_value = True
        service = self._make_service()
        service._vision_service = vision
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[],
            source="paint_process",
        )

        ok, msg = service.run_once()

        self.assertFalse(ok)
        self.assertEqual(msg, "No usable contour detected")
        vision.lock_auto_brightness_adjustment.assert_called_once_with()
        vision.unlock_auto_brightness_adjustment.assert_called_once_with()
        service._workpiece_preparation.prepare_workpiece.assert_not_called()

    def test_run_once_restores_brightness_after_execution_failure(self):
        vision = MagicMock()
        vision.get_auto_brightness_enabled.return_value = True
        service = self._make_service()
        service._vision_service = vision
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[_square(2.0)],
            source="paint_process",
        )
        service._workpiece_preparation.prepare_workpiece.return_value = ({"id": "wp-1"}, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.return_value = {"plan": 1}
        service._path_executor.execute_paint_process.return_value = (False, "pump fault")

        ok, msg = service.run_once()

        self.assertFalse(ok)
        self.assertEqual(msg, "Prepared workpiece: pump fault")
        vision.lock_auto_brightness_adjustment.assert_called_once_with()
        vision.unlock_auto_brightness_adjustment.assert_called_once_with()
        self.assertFalse(service._brightness_locked)

    def test_run_once_skips_brightness_lock_when_vision_missing(self):
        service = self._make_service()
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[_square(2.0)],
            source="paint_process",
        )
        service._workpiece_preparation.prepare_workpiece.return_value = ({"id": "wp-1"}, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.return_value = {"plan": 1}
        service._path_executor.execute_paint_process.return_value = (True, "Paint completed")

        ok, msg = service.run_once()

        self.assertTrue(ok, msg)
        self.assertFalse(service._brightness_locked)

    def test_run_once_skips_brightness_lock_when_auto_disabled(self):
        vision = MagicMock()
        vision.get_auto_brightness_enabled.return_value = False
        service = self._make_service()
        service._vision_service = vision
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[_square(2.0)],
            source="paint_process",
        )
        service._workpiece_preparation.prepare_workpiece.return_value = ({"id": "wp-1"}, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.return_value = {"plan": 1}
        service._path_executor.execute_paint_process.return_value = (True, "Paint completed")

        ok, msg = service.run_once()

        self.assertTrue(ok, msg)
        vision.lock_auto_brightness_adjustment.assert_not_called()
        vision.unlock_auto_brightness_adjustment.assert_not_called()
        self.assertFalse(service._brightness_locked)

    def test_pause_current_phase_requests_path_executor_pause(self):
        service = self._make_service()

        service.pause_current_phase()

        service._path_executor.pause_current_execution.assert_called_once_with()

    def test_run_once_enables_path_debug_plots_from_live_settings(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            enable_path_debug_plots=True,
            run_while_workpiece_found=False,
        )
        service = PaintProductionService(
            workpiece_preparation_service=MagicMock(),
            capture_snapshot_service=MagicMock(),
            path_preparation_service=MagicMock(),
            path_executor=MagicMock(),
            paint_process_config_service=config_service,
            navigation_service=MagicMock(move_to_calibration_position=MagicMock(return_value=True)),
        )
        contour = _square(2.0)
        raw_workpiece = {"id": "wp-1"}
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[contour],
            source="paint_process",
        )
        service._workpiece_preparation.prepare_workpiece.return_value = (raw_workpiece, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.return_value = {"plan": 1}
        service._path_executor.execute_paint_process.return_value = (True, "Paint completed")

        ok, msg = service.run_once()

        self.assertTrue(ok, msg)
        service._path_preparation_service.build_execution_plan.assert_called_once_with(
            raw_workpiece,
            skip_debug_plot=False,
        )

    def test_run_once_returns_no_contour_before_preparation(self):
        service = self._make_service()
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[],
            source="paint_process",
        )

        ok, msg = service.run_once()

        self.assertFalse(ok)
        self.assertEqual(msg, "No usable contour detected")
        service._workpiece_preparation.prepare_workpiece.assert_not_called()
        service._path_preparation_service.build_execution_plan.assert_not_called()

    def test_run_once_returns_plan_generation_failure(self):
        service = self._make_service()
        contour = _square(2.0)
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[contour],
            source="paint_process",
        )
        service._workpiece_preparation.prepare_workpiece.return_value = ({"id": "wp-1"}, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.side_effect = RuntimeError("bad plan")

        ok, msg = service.run_once()

        self.assertFalse(ok)
        self.assertEqual(msg, "Plan generation failed: bad plan")
        service._path_executor.execute_paint_process.assert_not_called()

    def test_run_once_honors_stop_requests_and_execution_failure(self):
        service = self._make_service()
        contour = _square(2.0)
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[contour],
            source="paint_process",
        )
        service._workpiece_preparation.prepare_workpiece.return_value = ({"id": "wp-1"}, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.return_value = {"plan": 1}
        service._path_executor.execute_paint_process.return_value = (False, "pump fault")

        stopped, stopped_msg = service.run_once(stop_requested=lambda: True)
        failed, failed_msg = service.run_once(stop_requested=lambda: False)

        self.assertFalse(stopped)
        self.assertEqual(stopped_msg, "Paint process stopped")
        self.assertFalse(failed)
        self.assertEqual(failed_msg, "Prepared workpiece: pump fault")

    def test_run_once_skips_magazine_load_when_disabled(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            run_while_workpiece_found=False,
            magazine_load=PaintMagazineLoadConfig(enabled=False),
        )
        magazine_load = MagicMock()
        navigation = MagicMock()
        navigation.move_to_calibration_position.return_value = True
        events = []
        service = PaintProductionService(
            workpiece_preparation_service=MagicMock(),
            capture_snapshot_service=MagicMock(),
            path_preparation_service=MagicMock(),
            path_executor=MagicMock(),
            paint_process_config_service=config_service,
            magazine_load_service=magazine_load,
            navigation_service=navigation,
        )
        contour = _square(2.0)
        navigation.move_to_calibration_position.side_effect = lambda **_kwargs: events.append("calibration") or True
        service._capture_snapshot_service.capture_snapshot.side_effect = (
            lambda **_kwargs: events.append("capture") or VisionCaptureSnapshot(
                frame="frame",
                contours=[contour],
                source="paint_process",
            )
        )
        service._workpiece_preparation.prepare_workpiece.return_value = ({"id": "wp-1"}, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.return_value = {"plan": 1}
        service._path_executor.execute_paint_process.return_value = (True, "Paint completed")

        ok, msg = service.run_once()

        self.assertTrue(ok, msg)
        magazine_load.load_to_calibration.assert_not_called()
        navigation.move_to_calibration_position.assert_called_once_with(wait_cancelled=ANY)
        service._capture_snapshot_service.capture_snapshot.assert_called_once_with(source="paint_process")
        self.assertEqual(["calibration", "capture"], events)

    def test_run_once_aborts_when_disabled_magazine_calibration_move_fails(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            run_while_workpiece_found=False,
            magazine_load=PaintMagazineLoadConfig(enabled=False, calibration_group_id="CALIBRATION"),
        )
        navigation = MagicMock()
        navigation.move_to_calibration_position.return_value = False
        service = PaintProductionService(
            workpiece_preparation_service=MagicMock(),
            capture_snapshot_service=MagicMock(),
            path_preparation_service=MagicMock(),
            path_executor=MagicMock(),
            paint_process_config_service=config_service,
            magazine_load_service=MagicMock(),
            navigation_service=navigation,
        )

        ok, msg = service.run_once()

        self.assertFalse(ok)
        self.assertEqual("Failed to move to calibration position 'CALIBRATION'", msg)
        service._capture_snapshot_service.capture_snapshot.assert_not_called()

    def test_run_once_executes_magazine_load_before_normal_paint_capture_when_enabled(self):
        config = PaintMagazineLoadConfig(enabled=True, camera_settle_s=0.0, release_settle_s=0.0)
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(magazine_load=config)
        magazine_load = MagicMock()
        magazine_load.load_to_calibration.side_effect = [
            (True, "Loaded"),
            (False, NO_WORKPIECE_AT_MAGAZINE),
        ]
        service = PaintProductionService(
            workpiece_preparation_service=MagicMock(),
            capture_snapshot_service=MagicMock(),
            path_preparation_service=MagicMock(),
            path_executor=MagicMock(),
            paint_process_config_service=config_service,
            magazine_load_service=magazine_load,
        )
        contour = _square(2.0)
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[contour],
            source="paint_process",
        )
        service._workpiece_preparation.prepare_workpiece.return_value = ({"id": "wp-1"}, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.return_value = {"plan": 1}
        service._path_executor.execute_paint_process.return_value = (True, "Paint completed")

        ok, msg = service.run_once()

        self.assertTrue(ok, msg)
        self.assertEqual("Magazine empty after 1 paint cycle(s)", msg)
        self.assertEqual(2, magazine_load.load_to_calibration.call_count)
        self.assertIs(config, magazine_load.load_to_calibration.call_args_list[0].args[0])
        service._capture_snapshot_service.capture_snapshot.assert_called_once_with(source="paint_process")

    def test_run_once_executes_single_magazine_cycle_when_looping_disabled(self):
        config = PaintMagazineLoadConfig(
            enabled=True,
            camera_settle_s=0.0,
            release_settle_s=0.0,
        )
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            run_while_workpiece_found=False,
            magazine_load=config,
        )
        magazine_load = MagicMock()
        magazine_load.load_to_calibration.return_value = (True, "Loaded")
        service = PaintProductionService(
            workpiece_preparation_service=MagicMock(),
            capture_snapshot_service=MagicMock(),
            path_preparation_service=MagicMock(),
            path_executor=MagicMock(),
            paint_process_config_service=config_service,
            magazine_load_service=magazine_load,
        )
        contour = _square(2.0)
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[contour],
            source="paint_process",
        )
        service._workpiece_preparation.prepare_workpiece.return_value = ({"id": "wp-1"}, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.return_value = {"plan": 1}
        service._path_executor.execute_paint_process.return_value = (True, "Paint completed")

        ok, msg = service.run_once()

        self.assertTrue(ok, msg)
        self.assertEqual("Prepared workpiece: Paint completed", msg)
        magazine_load.load_to_calibration.assert_called_once_with(config, ANY)
        service._capture_snapshot_service.capture_snapshot.assert_called_once_with(source="paint_process")

    def test_run_once_loops_manual_cycles_until_no_workpiece_when_looping_enabled(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            run_while_workpiece_found=True,
            magazine_load=PaintMagazineLoadConfig(enabled=False, release_settle_s=0.5),
        )
        navigation = MagicMock()
        navigation.move_to_calibration_position.return_value = True
        service = PaintProductionService(
            workpiece_preparation_service=MagicMock(),
            capture_snapshot_service=MagicMock(),
            path_preparation_service=MagicMock(),
            path_executor=MagicMock(),
            paint_process_config_service=config_service,
            magazine_load_service=MagicMock(),
            navigation_service=navigation,
        )
        contour = _square(2.0)
        service._capture_snapshot_service.capture_snapshot.side_effect = [
            VisionCaptureSnapshot(frame="frame-1", contours=[contour], source="paint_process"),
            VisionCaptureSnapshot(frame="frame-2", contours=[contour], source="paint_process"),
            VisionCaptureSnapshot(frame="frame-empty", contours=[], source="paint_process"),
        ]
        service._workpiece_preparation.prepare_workpiece.side_effect = [
            ({"id": "wp-1"}, "Prepared first workpiece"),
            ({"id": "wp-2"}, "Prepared second workpiece"),
        ]
        service._path_preparation_service.build_execution_plan.side_effect = [{"plan": 1}, {"plan": 2}]
        service._path_executor.execute_paint_process.return_value = (True, "Paint completed")

        ok, msg = service.run_once()

        self.assertTrue(ok, msg)
        self.assertEqual("No workpiece detected after 2 paint cycle(s)", msg)
        self.assertEqual(3, navigation.move_to_calibration_position.call_count)
        self.assertEqual(3, service._capture_snapshot_service.capture_snapshot.call_count)
        self.assertEqual(2, service._path_executor.execute_paint_process.call_count)

    def test_repeating_cycle_restores_brightness_after_reaching_calibration(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            run_while_workpiece_found=True,
            magazine_load=PaintMagazineLoadConfig(enabled=False),
        )
        events = []
        navigation = MagicMock()
        navigation.move_to_calibration_position.side_effect = (
            lambda **_kwargs: events.append("calibration") or True
        )
        vision = MagicMock()
        vision.get_auto_brightness_enabled.return_value = True
        vision.lock_auto_brightness_adjustment.side_effect = lambda: events.append("lock")
        vision.unlock_auto_brightness_adjustment.side_effect = lambda: events.append("unlock")
        service = PaintProductionService(
            workpiece_preparation_service=MagicMock(),
            capture_snapshot_service=MagicMock(),
            path_preparation_service=MagicMock(),
            path_executor=MagicMock(),
            paint_process_config_service=config_service,
            magazine_load_service=MagicMock(),
            navigation_service=navigation,
            vision_service=vision,
        )
        contour = _square(2.0)
        snapshots = iter([
            VisionCaptureSnapshot(frame="frame-1", contours=[contour], source="paint_process"),
            VisionCaptureSnapshot(frame="frame-empty", contours=[], source="paint_process"),
        ])
        service._capture_snapshot_service.capture_snapshot.side_effect = (
            lambda **_kwargs: events.append("capture") or next(snapshots)
        )
        service._workpiece_preparation.prepare_workpiece.return_value = ({"id": "wp-1"}, "Prepared")
        service._path_preparation_service.build_execution_plan.return_value = {"plan": 1}
        service._path_executor.execute_paint_process.side_effect = (
            lambda *_args, **_kwargs: events.append("execute") or (True, "Paint completed")
        )
        service._wait_for_capture_settle = MagicMock(
            side_effect=lambda *_args: events.append("settle") or True
        )

        ok, msg = service.run_once()

        self.assertTrue(ok, msg)
        self.assertEqual(
            [
                "calibration", "settle", "capture", "lock", "execute",
                "calibration", "unlock", "settle", "capture", "lock", "unlock",
            ],
            events,
        )
        self.assertEqual(
            [0.5, 0.5],
            [call.args[0] for call in service._wait_for_capture_settle.call_args_list],
        )

    def test_manual_loop_uses_any_captured_contour_when_matching_is_disabled(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            run_while_workpiece_found=True,
            enable_workpiece_matching=False,
            magazine_load=PaintMagazineLoadConfig(enabled=False),
        )
        match_workpiece = MagicMock(return_value=(False, None, "No matched workpiece"))
        preparation = PaintWorkpiecePreparationService(
            can_match_fn=lambda: True,
            match_workpiece_fn=match_workpiece,
        )
        navigation = MagicMock()
        navigation.move_to_calibration_position.return_value = True
        service = PaintProductionService(
            workpiece_preparation_service=preparation,
            capture_snapshot_service=MagicMock(),
            path_preparation_service=MagicMock(),
            path_executor=MagicMock(),
            paint_process_config_service=config_service,
            magazine_load_service=MagicMock(),
            navigation_service=navigation,
        )
        contour = _square(2.0)
        service._capture_snapshot_service.capture_snapshot.side_effect = [
            VisionCaptureSnapshot(frame="frame-1", contours=[contour], source="paint_process"),
            VisionCaptureSnapshot(frame="frame-2", contours=[contour], source="paint_process"),
            VisionCaptureSnapshot(frame="frame-empty", contours=[], source="paint_process"),
        ]
        service._path_preparation_service.build_execution_plan.side_effect = [{"plan": 1}, {"plan": 2}]
        service._path_executor.execute_paint_process.return_value = (True, "Paint completed")

        ok, msg = service.run_once()

        self.assertTrue(ok, msg)
        self.assertEqual("No workpiece detected after 2 paint cycle(s)", msg)
        match_workpiece.assert_not_called()
        self.assertEqual(3, service._capture_snapshot_service.capture_snapshot.call_count)
        self.assertEqual(2, service._path_preparation_service.build_execution_plan.call_count)
        prepared_workpieces = [
            call.args[0]
            for call in service._path_preparation_service.build_execution_plan.call_args_list
        ]
        self.assertEqual(["captured", "captured"], [item["workpieceId"] for item in prepared_workpieces])
        self.assertEqual(2, service._path_executor.execute_paint_process.call_count)

    def test_run_once_loops_magazine_cycles_until_empty(self):
        config = PaintMagazineLoadConfig(enabled=True, camera_settle_s=0.0, release_settle_s=0.0)
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(magazine_load=config)
        magazine_load = MagicMock()
        magazine_load.load_to_calibration.side_effect = [
            (True, "Loaded first"),
            (True, "Loaded second"),
            (False, NO_WORKPIECE_AT_MAGAZINE),
        ]
        service = PaintProductionService(
            workpiece_preparation_service=MagicMock(),
            capture_snapshot_service=MagicMock(),
            path_preparation_service=MagicMock(),
            path_executor=MagicMock(),
            paint_process_config_service=config_service,
            magazine_load_service=magazine_load,
        )
        contour = _square(2.0)
        service._capture_snapshot_service.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame="frame",
            contours=[contour],
            source="paint_process",
        )
        service._workpiece_preparation.prepare_workpiece.return_value = ({"id": "wp-1"}, "Prepared workpiece")
        service._path_preparation_service.build_execution_plan.return_value = {"plan": 1}
        service._path_executor.execute_paint_process.return_value = (True, "Paint completed")

        ok, msg = service.run_once()

        self.assertTrue(ok, msg)
        self.assertEqual("Magazine empty after 2 paint cycle(s)", msg)
        self.assertEqual(3, magazine_load.load_to_calibration.call_count)
        self.assertEqual(2, service._capture_snapshot_service.capture_snapshot.call_count)
        self.assertEqual(2, service._path_executor.execute_paint_process.call_count)

    def test_run_once_exits_cleanly_when_magazine_is_empty_before_first_cycle(self):
        config = PaintMagazineLoadConfig(enabled=True, camera_settle_s=0.0, release_settle_s=0.0)
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(magazine_load=config)
        magazine_load = MagicMock()
        magazine_load.load_to_calibration.return_value = (False, NO_WORKPIECE_AT_MAGAZINE)
        service = PaintProductionService(
            workpiece_preparation_service=MagicMock(),
            capture_snapshot_service=MagicMock(),
            path_preparation_service=MagicMock(),
            path_executor=MagicMock(),
            paint_process_config_service=config_service,
            magazine_load_service=magazine_load,
        )

        ok, msg = service.run_once()

        self.assertTrue(ok, msg)
        self.assertEqual(NO_WORKPIECE_AT_MAGAZINE, msg)
        magazine_load.load_to_calibration.assert_called_once()
        service._capture_snapshot_service.capture_snapshot.assert_not_called()

    def test_run_once_aborts_when_magazine_load_fails(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            magazine_load=PaintMagazineLoadConfig(enabled=True)
        )
        magazine_load = MagicMock()
        magazine_load.load_to_calibration.return_value = (False, "No usable magazine contour detected")
        service = PaintProductionService(
            workpiece_preparation_service=MagicMock(),
            capture_snapshot_service=MagicMock(),
            path_preparation_service=MagicMock(),
            path_executor=MagicMock(),
            paint_process_config_service=config_service,
            magazine_load_service=magazine_load,
        )

        ok, msg = service.run_once()

        self.assertFalse(ok)
        self.assertEqual("No usable magazine contour detected", msg)
        service._capture_snapshot_service.capture_snapshot.assert_not_called()


class TestPaintMagazineLoadService(unittest.TestCase):
    def test_magazine_load_allows_resume_to_interrupted_execution_state(self):
        rules = MagazineLoadTransitions.get_rules()

        self.assertIn(
            MagazineLoadState.EXECUTE_PICKUP_AND_RELEASE,
            rules[MagazineLoadState.STARTING],
        )

    def test_load_to_calibration_uses_simple_contour_center_without_full_paint_planning(self):
        navigation = MagicMock()
        navigation.move_to_group.return_value = True
        navigation.get_group_position.side_effect = lambda group: {
            "Magazine": [0, 0, 30, 180, 0, 0],
            "CALIBRATION": [10, 20, 30, 180, 0, 0],
        }[group]
        work_area_service = MagicMock()
        work_area_service.get_work_area.return_value = [
            [0.25, 0.25],
            [0.75, 0.25],
            [0.75, 0.75],
            [0.25, 0.75],
        ]
        capture = MagicMock()
        capture.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame=np.zeros((20, 40, 3), dtype=np.uint8),
            contours=[_square(3.0)],
            source="paint_magazine_load",
        )
        preparation = MagicMock()
        path_preparation = MagicMock()
        executor = MagicMock()
        resolver = MagicMock()
        resolver.registry.by_name.side_effect = lambda name: SimpleNamespace(name=name, offset_x=0.0, offset_y=0.0)
        resolver.resolve.side_effect = lambda request, _point, frame="": SimpleNamespace(
            final_xy=(float(request.x_pixels), float(request.y_pixels))
        )
        service = PaintMagazineLoadService(
            navigation=navigation,
            capture_snapshot_service=capture,
            path_executor=executor,
            resolver_getter=lambda: resolver,
            work_area_service=work_area_service,
        )

        with patch(
            "src.robot_systems.paint.processes.paint.magazine_load.handlers.execute_magazine_pickup_release",
            return_value=(True, "Workpiece transferred to paint work area center"),
        ) as execute_transfer:
            ok, msg = service.load_to_calibration(
                PaintMagazineLoadConfig(
                    enabled=True,
                    move_to_magazine_vel_percent=17.0,
                    move_to_magazine_acc_percent=18.0,
                    camera_settle_s=0.0,
                    release_settle_s=0.0,
                ),
                stop_requested=lambda: False,
            )

        self.assertTrue(ok, msg)
        self.assertEqual("Magazine contour: Workpiece transferred to paint work area center", msg)
        self.assertEqual(2, navigation.move_to_group.call_count)
        navigation.move_to_group.assert_any_call(
            "Magazine", wait_cancelled=ANY, velocity=17.0, acceleration=18.0
        )
        navigation.move_to_group.assert_any_call(
            "CALIBRATION", wait_cancelled=ANY, velocity=30.0, acceleration=30.0
        )
        capture.capture_snapshot.assert_called_once_with(source="paint_magazine_load")
        work_area_service.get_work_area.assert_called_once_with("paint")
        preparation.prepare_workpiece.assert_not_called()
        path_preparation.build_execution_plan.assert_not_called()
        execute_transfer.assert_called_once_with(
            service,
            pickup_xy=ANY,
            pickup_rz=ANY,
            pickup_base_pose=[0, 0, 30, 180, 0, 0],
            release_pose=[20.0, 10.0, 30, 180, 0, 0],
            workpiece_height_mm=0.0,
            release_label="paint work area center",
            resume_from_current_pose=False,
        )
        pickup_xy = execute_transfer.call_args.kwargs["pickup_xy"]
        self.assertAlmostEqual(1.5, pickup_xy[0])
        self.assertAlmostEqual(1.5, pickup_xy[1])
        navigation.mark_group_observed_area_verified.assert_called_once_with("CALIBRATION")

    def test_load_to_calibration_can_pause_and_resume_during_magazine_move(self):
        class PauseNavigation:
            def __init__(self):
                self.entered_first_move = threading.Event()
                self.cancelled_first_move = threading.Event()
                self.move_calls = []
                self.stop_motion_calls = 0

            def move_to_group(self, group, wait_cancelled=None, velocity=None, acceleration=None):
                self.move_calls.append((group, velocity, acceleration))
                if group == "Magazine" and len(self.move_calls) == 1:
                    self.entered_first_move.set()
                    deadline = time.monotonic() + 2.0
                    while time.monotonic() < deadline:
                        if wait_cancelled is not None and wait_cancelled():
                            self.cancelled_first_move.set()
                            return False
                        time.sleep(0.01)
                    return False
                return True

            def get_group_position(self, group):
                return {
                    "Magazine": [0, 0, 30, 180, 0, 0],
                    "CALIBRATION": [10, 20, 30, 180, 0, 0],
                }[group]

            def mark_group_observed_area_verified(self, _group):
                return None

            def stop_motion(self):
                self.stop_motion_calls += 1
                return True

        navigation = PauseNavigation()
        work_area_service = MagicMock()
        work_area_service.get_work_area.return_value = [
            [0.25, 0.25],
            [0.75, 0.25],
            [0.75, 0.75],
            [0.25, 0.75],
        ]
        capture = MagicMock()
        capture.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame=np.zeros((20, 40, 3), dtype=np.uint8),
            contours=[_square(3.0)],
            source="paint_magazine_load",
        )
        executor = MagicMock()
        resolver = MagicMock()
        resolver.registry.by_name.side_effect = lambda name: SimpleNamespace(name=name, offset_x=0.0, offset_y=0.0)
        resolver.resolve.side_effect = lambda request, _point, frame="": SimpleNamespace(
            final_xy=(float(request.x_pixels), float(request.y_pixels))
        )
        service = PaintMagazineLoadService(
            navigation=navigation,
            capture_snapshot_service=capture,
            path_executor=executor,
            resolver_getter=lambda: resolver,
            work_area_service=work_area_service,
        )
        result = {}

        with patch(
            "src.robot_systems.paint.processes.paint.magazine_load.handlers.execute_magazine_pickup_release",
            return_value=(True, "Workpiece transferred to paint work area center"),
        ):
            thread = threading.Thread(
                target=lambda: result.update(
                    value=service.load_to_calibration(
                        PaintMagazineLoadConfig(
                            enabled=True,
                            camera_settle_s=0.0,
                            release_settle_s=0.0,
                        ),
                        stop_requested=lambda: False,
                    )
                )
            )
            thread.start()
            self.assertTrue(navigation.entered_first_move.wait(timeout=1.0))

            service.pause_current_load()
            self.assertTrue(navigation.cancelled_first_move.wait(timeout=1.0))
            for _ in range(100):
                if service.get_control_snapshot().get("current_state") == "PAUSED":
                    break
                time.sleep(0.01)
            self.assertEqual("PAUSED", service.get_control_snapshot().get("current_state"))
            self.assertEqual(1, navigation.stop_motion_calls)

            service.resume_current_load()
            thread.join(timeout=2.0)

        self.assertFalse(thread.is_alive())
        self.assertEqual((True, "Magazine contour: Workpiece transferred to paint work area center"), result["value"])
        self.assertEqual("Magazine", navigation.move_calls[0][0])
        self.assertEqual("Magazine", navigation.move_calls[1][0])
        self.assertEqual("CALIBRATION", navigation.move_calls[-1][0])

    def test_load_to_calibration_retries_interrupted_move_once_after_pause_resume(self):
        class ResumeFailureNavigation:
            def __init__(self):
                self.entered_first_move = threading.Event()
                self.cancelled_first_move = threading.Event()
                self.move_calls = []
                self.stop_motion_calls = 0

            def move_to_group(self, group, wait_cancelled=None, velocity=None, acceleration=None):
                self.move_calls.append((group, velocity, acceleration))
                if group == "Magazine" and len([call for call in self.move_calls if call[0] == "Magazine"]) == 1:
                    self.entered_first_move.set()
                    deadline = time.monotonic() + 2.0
                    while time.monotonic() < deadline:
                        if wait_cancelled is not None and wait_cancelled():
                            self.cancelled_first_move.set()
                            return False
                        time.sleep(0.01)
                    return False
                if group == "Magazine" and len([call for call in self.move_calls if call[0] == "Magazine"]) == 2:
                    return False
                return True

            def get_group_position(self, group):
                return {
                    "Magazine": [0, 0, 30, 180, 0, 0],
                    "CALIBRATION": [10, 20, 30, 180, 0, 0],
                }[group]

            def mark_group_observed_area_verified(self, _group):
                return None

            def stop_motion(self):
                self.stop_motion_calls += 1
                return True

        navigation = ResumeFailureNavigation()
        work_area_service = MagicMock()
        work_area_service.get_work_area.return_value = [
            [0.25, 0.25],
            [0.75, 0.25],
            [0.75, 0.75],
            [0.25, 0.75],
        ]
        capture = MagicMock()
        capture.capture_snapshot.return_value = VisionCaptureSnapshot(
            frame=np.zeros((20, 40, 3), dtype=np.uint8),
            contours=[_square(3.0)],
            source="paint_magazine_load",
        )
        executor = MagicMock()
        resolver = MagicMock()
        resolver.registry.by_name.side_effect = lambda name: SimpleNamespace(name=name, offset_x=0.0, offset_y=0.0)
        resolver.resolve.side_effect = lambda request, _point, frame="": SimpleNamespace(
            final_xy=(float(request.x_pixels), float(request.y_pixels))
        )
        service = PaintMagazineLoadService(
            navigation=navigation,
            capture_snapshot_service=capture,
            path_executor=executor,
            resolver_getter=lambda: resolver,
            work_area_service=work_area_service,
        )
        service._wait_after_pause_resume = lambda _context: True
        result = {}

        with patch(
            "src.robot_systems.paint.processes.paint.magazine_load.handlers.execute_magazine_pickup_release",
            return_value=(True, "Workpiece transferred to paint work area center"),
        ):
            thread = threading.Thread(
                target=lambda: result.update(
                    value=service.load_to_calibration(
                        PaintMagazineLoadConfig(
                            enabled=True,
                            camera_settle_s=0.0,
                            release_settle_s=0.0,
                        ),
                        stop_requested=lambda: False,
                    )
                )
            )
            thread.start()
            self.assertTrue(navigation.entered_first_move.wait(timeout=1.0))

            service.pause_current_load()
            self.assertTrue(navigation.cancelled_first_move.wait(timeout=1.0))
            for _ in range(100):
                if service.get_control_snapshot().get("current_state") == "PAUSED":
                    break
                time.sleep(0.01)

            service.resume_current_load()
            thread.join(timeout=2.0)

        self.assertFalse(thread.is_alive())
        self.assertEqual((True, "Magazine contour: Workpiece transferred to paint work area center"), result["value"])
        self.assertEqual(["Magazine", "Magazine", "Magazine", "CALIBRATION"], [call[0] for call in navigation.move_calls])


class TestPaintProcessIntegration(unittest.TestCase):

    def _make_process(self, production_result):
        production_service = MagicMock()
        production_service.run_once.return_value = production_result
        messaging = MagicMock()
        process = PaintProcess(production_service=production_service, messaging=messaging)
        return process, production_service, messaging

    def test_successful_run_transitions_process_to_stopped(self):
        process, production_service, messaging = self._make_process((True, "Paint completed"))
        published = []
        stop_seen = threading.Event()

        def _publish(topic, event):
            published.append((topic, event))
            if topic == ProcessTopics.state(ProcessID.MAIN_PROCESS) and event.state == ProcessState.STOPPED:
                stop_seen.set()

        messaging.publish.side_effect = _publish

        process.start()
        self.assertTrue(stop_seen.wait(timeout=1.0), "paint process did not reach stopped state")
        process._thread.join(timeout=1.0)

        self.assertEqual(process.state, ProcessState.STOPPED)
        self.assertTrue(process._stopping)
        production_service.run_once.assert_called_once()
        self.assertTrue(
            any(
                topic == ProcessTopics.state(ProcessID.MAIN_PROCESS) and event.state == ProcessState.RUNNING
                for topic, event in published
            )
        )
        self.assertTrue(
            any(
                topic == ProcessTopics.state(ProcessID.MAIN_PROCESS) and event.state == ProcessState.STOPPED
                for topic, event in published
            )
        )

    def test_no_workpiece_successful_stop_publishes_operator_message(self):
        process, _production_service, messaging = self._make_process((True, "No workpiece detected after 2 paint cycle(s)"))
        published = []
        stop_seen = threading.Event()

        def _publish(topic, event):
            published.append((topic, event))
            if topic == ProcessTopics.state(ProcessID.MAIN_PROCESS) and event.state == ProcessState.STOPPED:
                stop_seen.set()

        messaging.publish.side_effect = _publish

        process.start()
        self.assertTrue(stop_seen.wait(timeout=1.0), "paint process did not reach stopped state")
        process._thread.join(timeout=1.0)

        stopped_events = [
            event
            for topic, event in published
            if topic == ProcessTopics.state(ProcessID.MAIN_PROCESS)
            and event.state == ProcessState.STOPPED
        ]
        self.assertEqual(stopped_events[-1].message, "No workpiece detected after 2 paint cycle(s)")

    def test_failed_run_transitions_process_to_error(self):
        process, production_service, messaging = self._make_process((False, "No usable contour detected"))
        error_seen = threading.Event()

        def _publish(topic, event):
            if topic == ProcessTopics.state(ProcessID.MAIN_PROCESS) and event.state == ProcessState.ERROR:
                error_seen.set()

        messaging.publish.side_effect = _publish

        process.start()
        self.assertTrue(error_seen.wait(timeout=1.0), "paint process did not reach error state")
        process._thread.join(timeout=1.0)

        self.assertEqual(process.state, ProcessState.ERROR)
        production_service.run_once.assert_called_once()

    def test_exception_and_reset_paths_update_internal_stop_flag(self):
        production_service = MagicMock()
        production_service.run_once.side_effect = RuntimeError("boom")
        process = PaintProcess(production_service=production_service, messaging=MagicMock())
        set_error = MagicMock()
        process.set_error = set_error

        process._stopping = False
        process._run_in_background()
        set_error.assert_called_once_with("boom")

        set_error.reset_mock()
        process._stopping = True
        process._run_in_background()
        set_error.assert_not_called()

        process._stopping = True
        process._on_reset_errors()
        self.assertFalse(process._stopping)

    def test_pause_resume_and_stop_delegate_to_current_production_phase(self):
        production_service = MagicMock()
        process = PaintProcess(production_service=production_service, messaging=MagicMock())

        process._on_pause()
        process._on_resume()
        process._on_stop()

        production_service.pause_current_phase.assert_called_once_with()
        production_service.resume_current_phase.assert_called_once_with()
        production_service.stop_current_phase.assert_called_once_with()

    def test_stop_requests_robot_motion_stop_and_vacuum_off(self):
        robot = MagicMock()
        vacuum = MagicMock()
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(enable_vacuum_pump=True)
        process = PaintProcess(
            production_service=MagicMock(),
            messaging=MagicMock(),
            robot_service=robot,
            vacuum_pump=vacuum,
            paint_process_config_service=config_service,
        )

        process._on_stop()
        process._stop_thread.join(timeout=1.0)

        self.assertTrue(process._stopping)
        robot.stop_motion.assert_called_once_with()
        vacuum.turn_off.assert_called_once_with()

    def test_stop_does_not_turn_vacuum_off_when_vacuum_is_disabled(self):
        robot = MagicMock()
        vacuum = MagicMock()
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(enable_vacuum_pump=False)
        process = PaintProcess(
            production_service=MagicMock(),
            messaging=MagicMock(),
            robot_service=robot,
            vacuum_pump=vacuum,
            paint_process_config_service=config_service,
        )

        process._on_stop()
        process._stop_thread.join(timeout=1.0)

        self.assertTrue(process._stopping)
        robot.stop_motion.assert_called_once_with()
        vacuum.turn_off.assert_not_called()


if __name__ == "__main__":
    unittest.main()
