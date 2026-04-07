"""
Tests for calibration state handlers in
src/engine/robot/calibration/robot_calibration/states/

Each handler receives a context and returns a RobotCalibrationStates value.
Tests verify:
  - stop_event is respected (returns CANCELLED, not ERROR)
  - normal happy/sad paths return correct next states
"""
import threading
import unittest
from unittest.mock import MagicMock, patch

from src.engine.robot.calibration.robot_calibration.RobotCalibrationContext import (
    RobotCalibrationContext,
)
from src.engine.robot.calibration.robot_calibration.overlay_renderer import (
    NoOpCalibrationRenderer,
)
from src.engine.robot.calibration.robot_calibration.states.align_robot import (
    handle_align_robot_state,
)
from src.engine.robot.calibration.robot_calibration.states.handle_height_sample_state import (
    handle_height_sample_state,
)
from src.engine.robot.calibration.robot_calibration.states.iterate_alignment import (
    handle_iterate_alignment_state,
)
from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import RobotCalibrationStates
from src.engine.robot.calibration.robot_calibration.states.looking_for_aruco_markers_handler import (
    handle_looking_for_aruco_markers_state,
)
from src.engine.robot.calibration.robot_calibration.states.looking_for_chessboard_handler import (
    handle_looking_for_chessboard_state,
)
from src.engine.robot.calibration.robot_calibration.states.tcp_offset_state import (
    handle_capture_tcp_offset_state,
)
from src.engine.robot.calibration.robot_calibration.states.terminal_states import (
    handle_done_state,
)


# ── Context factory ────────────────────────────────────────────────────────────

def _make_context(**overrides):
    ctx = RobotCalibrationContext()
    ctx.stop_event = threading.Event()
    ctx.debug = False
    ctx.live_visualization = False
    ctx.broadcast_events = False
    ctx.calibration_renderer = NoOpCalibrationRenderer()
    ctx.iteration_count = 0
    ctx.max_iterations = 50
    ctx.alignment_threshold_mm = 1.0
    ctx.fast_iteration_wait = 0.01   # fast for tests
    ctx.required_ids = {0, 1}
    ctx.target_plan.required_ids = [0, 1]
    ctx.target_plan.target_marker_ids = [0, 1]
    ctx.current_marker_id = 0
    ctx.robot_positions_for_calibration = {}
    ctx.Z_target = 100.0
    ctx.ppm_scale = 1.0
    ctx.markers_offsets_mm = {0: (0, 0), 1: (10, 10)}
    ctx.image_to_robot_mapping = MagicMock()
    ctx.image_to_robot_mapping.map.return_value = (0.0, 0.0)
    ctx.calibration_robot_controller = MagicMock()
    ctx.calibration_robot_controller.adaptive_movement_config = MagicMock(
        initial_align_y_scale=1.0,
    )
    ctx.calibration_robot_controller.get_current_position.return_value = [0, 0, 100, 0, 0, 0]
    ctx.calibration_robot_controller.get_calibration_position.return_value = [0, 0, 100, 0, 0, 0]
    ctx.calibration_robot_controller.move_to_position.return_value = True
    ctx.calibration_robot_controller.get_iterative_align_position.return_value = [1, 1, 100, 0, 0, 0]
    ctx.calibration_vision = MagicMock()
    ctx.calibration_vision.PPM = 10.0
    ctx.calibration_vision.marker_top_left_corners = {}
    ctx.vision_service = MagicMock()
    ctx.vision_service.get_latest_frame.return_value = MagicMock()
    ctx.vision_service.get_camera_width.return_value = 640
    ctx.vision_service.get_camera_height.return_value = 480
    ctx.debug_draw = MagicMock()
    ctx.camera_tcp_offset_config = MagicMock(
        run_during_robot_calibration=False,
        iterations=0,
        max_markers_for_tcp_capture=2,
        rotation_step_deg=15.0,
        approach_rz=0.0,
        settle_time_s=0.0,
        velocity=20,
        acceleration=10,
        recenter_max_iterations=5,
        min_samples=3,
        max_acceptance_std_mm=10.0,
    )
    ctx.camera_tcp_offset_samples = []
    ctx.camera_tcp_offset_captured_markers = set()
    ctx.run_height_measurement = True
    ctx.height_map_samples = []
    ctx.robot_config = MagicMock()
    ctx.settings_service = MagicMock()
    ctx.robot_config_key = "robot_config"

    for k, v in overrides.items():
        setattr(ctx, k, v)
    if ctx.target_plan.required_ids is None:
        ctx.target_plan.required_ids = sorted(list(ctx.required_ids))
    if not ctx.target_plan.target_marker_ids:
        ctx.target_plan.target_marker_ids = list(ctx.target_plan.required_ids)
    return ctx


# ══════════════════════════════════════════════════════════════════════════════
# handle_looking_for_chessboard_state
# ══════════════════════════════════════════════════════════════════════════════

class TestLookingForChessboardHandler(unittest.TestCase):

    def test_returns_cancelled_when_stop_event_set_before_call(self):
        ctx = _make_context()
        ctx.stop_event.set()
        ctx.vision_service.get_latest_frame.return_value = None  # would block without stop check
        result = handle_looking_for_chessboard_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.CANCELLED)

    def test_returns_cancelled_when_stop_event_set_while_waiting_for_frame(self):
        ctx = _make_context()

        call_count = [0]
        def _frame():
            call_count[0] += 1
            if call_count[0] == 1:
                ctx.stop_event.set()
            return None  # always None — would loop forever without stop check

        ctx.vision_service.get_latest_frame.side_effect = _frame
        result = handle_looking_for_chessboard_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.CANCELLED)

    def test_chessboard_found_returns_chessboard_found(self):
        ctx = _make_context()
        ctx.calibration_vision.find_chessboard_and_compute_ppm.return_value = MagicMock(
            found=True, ppm=10.0, bottom_left_px=MagicMock(), message=""
        )
        result = handle_looking_for_chessboard_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.CHESSBOARD_FOUND)

    def test_chessboard_not_found_stays_in_looking(self):
        ctx = _make_context()
        ctx.calibration_vision.find_chessboard_and_compute_ppm.return_value = MagicMock(
            found=False, ppm=None, bottom_left_px=None, message="not found"
        )
        result = handle_looking_for_chessboard_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.LOOKING_FOR_CHESSBOARD)


# ══════════════════════════════════════════════════════════════════════════════
# handle_looking_for_aruco_markers_state
# ══════════════════════════════════════════════════════════════════════════════

class TestLookingForArucoMarkersHandler(unittest.TestCase):

    def test_returns_cancelled_when_stop_event_set_before_call(self):
        ctx = _make_context()
        ctx.stop_event.set()
        ctx.vision_service.get_latest_frame.return_value = None
        result = handle_looking_for_aruco_markers_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.CANCELLED)

    def test_returns_cancelled_when_stop_event_set_while_waiting_for_frame(self):
        ctx = _make_context()

        call_count = [0]
        def _frame():
            call_count[0] += 1
            if call_count[0] == 1:
                ctx.stop_event.set()
            return None

        ctx.vision_service.get_latest_frame.side_effect = _frame
        result = handle_looking_for_aruco_markers_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.CANCELLED)

    def test_all_markers_found_returns_all_aruco_found(self):
        ctx = _make_context()
        ctx.calibration_vision.find_required_aruco_markers.return_value = MagicMock(
            found=True, frame=MagicMock()
        )
        selection_plan = MagicMock(
            homography_ids=[0],
            residual_ids=[],
            validation_ids=[],
            execution_ids=[0],
            selected_ids=[0],
            neighbor_ids={},
            report={},
        )
        with patch(
            "src.engine.robot.calibration.robot_calibration.states.looking_for_aruco_markers_handler._collect_averaged_reference_pixels",
            return_value={0: np.array([10.0, 10.0]), 1: np.array([20.0, 20.0]), 2: np.array([30.0, 30.0]), 3: np.array([40.0, 40.0])},
        ), patch(
            "src.engine.robot.calibration.robot_calibration.states.looking_for_aruco_markers_handler.build_partitioned_target_selection_plan",
            return_value=selection_plan,
        ):
            result = handle_looking_for_aruco_markers_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.ALL_ARUCO_FOUND)

    def test_markers_not_found_stays_in_looking(self):
        ctx = _make_context()
        ctx.calibration_vision.find_required_aruco_markers.return_value = MagicMock(
            found=False, frame=MagicMock()
        )
        with patch(
            "src.engine.robot.calibration.robot_calibration.states.looking_for_aruco_markers_handler._collect_averaged_reference_pixels",
            return_value={0: np.array([10.0, 10.0])},
        ):
            result = handle_looking_for_aruco_markers_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.LOOKING_FOR_ARUCO_MARKERS)


# ══════════════════════════════════════════════════════════════════════════════
# handle_align_robot_state
# ══════════════════════════════════════════════════════════════════════════════

class TestAlignRobotHandler(unittest.TestCase):

    def test_returns_cancelled_when_stop_event_set_at_entry(self):
        ctx = _make_context()
        ctx.stop_event.set()
        result = handle_align_robot_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.CANCELLED)
        ctx.calibration_robot_controller.move_to_position.assert_not_called()

    def test_move_success_returns_iterate_alignment(self):
        ctx = _make_context()
        ctx.calibration_robot_controller.move_to_position.return_value = True
        result = handle_align_robot_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.ITERATE_ALIGNMENT)

    def test_move_failure_returns_error(self):
        ctx = _make_context()
        ctx.calibration_robot_controller.move_to_position.return_value = False
        ctx.robot_positions_for_calibration = {}
        result = handle_align_robot_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.ERROR)

    def test_returns_cancelled_when_stop_event_fires_in_post_move_wait(self):
        ctx = _make_context()
        ctx.calibration_robot_controller.move_to_position.return_value = True

        def _fast_wait(self_ev, timeout=None):
            self_ev.set()
            return True

        with patch.object(threading.Event, "wait", _fast_wait):
            result = handle_align_robot_state(ctx)

        self.assertEqual(result, RobotCalibrationStates.CANCELLED)


# ══════════════════════════════════════════════════════════════════════════════
# handle_iterate_alignment_state
# ══════════════════════════════════════════════════════════════════════════════

import numpy as np


class TestIterateAlignmentHandler(unittest.TestCase):

    def _aligned_ctx(self):
        """Context where alignment succeeds on first iteration."""
        ctx = _make_context()
        ctx.iteration_count = 0

        # marker found at image center → zero error → alignment_success = True
        half_w, half_h = 320, 240
        ctx.vision_service.get_camera_width.return_value = half_w * 2
        ctx.vision_service.get_camera_height.return_value = half_h * 2

        marker_corners = MagicMock()
        ctx.calibration_vision.detect_specific_marker.return_value = MagicMock(
            found=True,
            aruco_corners=marker_corners,
            aruco_ids=MagicMock(),
        )
        # marker at image center → offset 0 → error 0mm < threshold
        ctx.calibration_vision.marker_top_left_corners = {0: np.array([half_w, half_h])}
        ctx.calibration_vision.PPM = 100.0
        ctx.alignment_threshold_mm = 100.0   # very loose — always pass
        return ctx

    def _not_aligned_ctx(self):
        """Context where alignment never succeeds (large error)."""
        ctx = _make_context()
        ctx.iteration_count = 0

        half_w, half_h = 320, 240
        ctx.vision_service.get_camera_width.return_value = half_w * 2
        ctx.vision_service.get_camera_height.return_value = half_h * 2

        ctx.calibration_vision.detect_specific_marker.return_value = MagicMock(
            found=True,
            aruco_corners=MagicMock(),
            aruco_ids=MagicMock(),
        )
        # Marker far from center → large error > threshold
        ctx.calibration_vision.marker_top_left_corners = {0: np.array([0, 0])}
        ctx.calibration_vision.PPM = 1.0
        ctx.alignment_threshold_mm = 0.001   # very tight — never pass
        ctx.calibration_robot_controller.move_to_position.return_value = True
        return ctx

    def test_returns_cancelled_when_stop_event_set_before_frame(self):
        ctx = _make_context()
        ctx.stop_event.set()
        ctx.vision_service.get_latest_frame.return_value = None
        result = handle_iterate_alignment_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.CANCELLED)

    def test_returns_cancelled_when_stop_event_set_while_waiting_for_frame(self):
        ctx = _make_context()

        call_count = [0]
        def _frame():
            call_count[0] += 1
            if call_count[0] == 1:
                ctx.stop_event.set()
            return None

        ctx.vision_service.get_latest_frame.side_effect = _frame
        result = handle_iterate_alignment_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.CANCELLED)

    def test_returns_error_on_max_iterations_exceeded(self):
        ctx = _make_context()
        ctx.iteration_count = ctx.max_iterations  # already at max
        result = handle_iterate_alignment_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.ERROR)

    def test_marker_not_found_stays_in_iterate(self):
        ctx = _make_context()
        ctx.calibration_vision.detect_specific_marker.return_value = MagicMock(found=False)
        result = handle_iterate_alignment_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.ITERATE_ALIGNMENT)

    def test_stop_event_in_stability_wait_returns_cancelled(self):
        """Stop event fires during the post-move stability wait (non-aligned path)."""
        ctx = self._not_aligned_ctx()

        def _fast_wait(self_ev, timeout=None):
            self_ev.set()
            return True

        with patch.object(threading.Event, "wait", _fast_wait):
            result = handle_iterate_alignment_state(ctx)

        self.assertEqual(result, RobotCalibrationStates.CANCELLED)

    def test_alignment_success_returns_sample_height(self):
        ctx = self._aligned_ctx()
        result = handle_iterate_alignment_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.SAMPLE_HEIGHT)

    def test_alignment_success_returns_capture_tcp_offset_when_enabled(self):
        ctx = self._aligned_ctx()
        ctx.camera_tcp_offset_config.run_during_robot_calibration = True
        ctx.camera_tcp_offset_config.iterations = 2
        result = handle_iterate_alignment_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.CAPTURE_TCP_OFFSET)

    def test_alignment_success_skips_capture_when_max_markers_already_reached(self):
        ctx = self._aligned_ctx()
        ctx.camera_tcp_offset_config.run_during_robot_calibration = True
        ctx.camera_tcp_offset_config.iterations = 2
        ctx.camera_tcp_offset_config.max_markers_for_tcp_capture = 1
        ctx.camera_tcp_offset_captured_markers = {0}
        result = handle_iterate_alignment_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.SAMPLE_HEIGHT)

    def test_alignment_not_reached_stays_in_iterate(self):
        ctx = self._not_aligned_ctx()
        result = handle_iterate_alignment_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.ITERATE_ALIGNMENT)


# ══════════════════════════════════════════════════════════════════════════════
# handle_done_state
# ══════════════════════════════════════════════════════════════════════════════

class TestDoneHandler(unittest.TestCase):

    def test_advances_to_next_marker(self):
        ctx = _make_context(current_marker_id=0, required_ids={0, 1})
        result = handle_done_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.ALIGN_ROBOT)
        self.assertEqual(ctx.current_marker_id, 1)

    def test_stays_done_when_all_markers_processed(self):
        ctx = _make_context(current_marker_id=1, required_ids={0, 1})
        result = handle_done_state(ctx)
        self.assertEqual(result, RobotCalibrationStates.DONE)


class TestCaptureTcpOffsetHandler(unittest.TestCase):

    @patch("src.engine.robot.calibration.robot_calibration.states.tcp_offset_state.capture_tcp_offset_for_current_marker")
    def test_returns_sample_height_when_capture_succeeds(self, capture_mock):
        ctx = _make_context()
        ctx.camera_tcp_offset_config.run_during_robot_calibration = True
        ctx.camera_tcp_offset_config.iterations = 2
        capture_mock.return_value = True

        result = handle_capture_tcp_offset_state(ctx)

        self.assertEqual(result, RobotCalibrationStates.SAMPLE_HEIGHT)
        capture_mock.assert_called_once_with(ctx)

    @patch("src.engine.robot.calibration.robot_calibration.states.tcp_offset_state.capture_tcp_offset_for_current_marker")
    def test_returns_error_when_capture_fails(self, capture_mock):
        ctx = _make_context()
        ctx.camera_tcp_offset_config.run_during_robot_calibration = True
        ctx.camera_tcp_offset_config.iterations = 2
        capture_mock.return_value = False

        result = handle_capture_tcp_offset_state(ctx)

        self.assertEqual(result, RobotCalibrationStates.SAMPLE_HEIGHT)

    @patch("src.engine.robot.calibration.robot_calibration.states.tcp_offset_state.capture_tcp_offset_for_current_marker")
    def test_skips_capture_when_max_markers_already_captured(self, capture_mock):
        ctx = _make_context()
        ctx.camera_tcp_offset_config.run_during_robot_calibration = True
        ctx.camera_tcp_offset_config.iterations = 2
        ctx.camera_tcp_offset_config.max_markers_for_tcp_capture = 1
        ctx.camera_tcp_offset_captured_markers = {0}

        result = handle_capture_tcp_offset_state(ctx)

        self.assertEqual(result, RobotCalibrationStates.SAMPLE_HEIGHT)
        capture_mock.assert_not_called()


class TestHeightSampleHandler(unittest.TestCase):

    def test_skips_height_measurement_when_disabled(self):
        ctx = _make_context()
        ctx.run_height_measurement = False
        ctx.height_measuring_service = MagicMock()

        result = handle_height_sample_state(ctx)

        self.assertEqual(result, RobotCalibrationStates.DONE)
        ctx.height_measuring_service.measure_at.assert_not_called()

    def test_samples_height_when_enabled(self):
        ctx = _make_context()
        ctx.height_measuring_service = MagicMock()
        ctx.height_measuring_service.measure_at.return_value = 12.34
        ctx.calibration_robot_controller.robot_service.get_current_position.return_value = [1.0, 2.0, 3.0, 0.0, 0.0, 0.0]

        result = handle_height_sample_state(ctx)

        self.assertEqual(result, RobotCalibrationStates.DONE)
        ctx.height_measuring_service.measure_at.assert_called_once_with(1.0, 2.0)
        self.assertEqual(ctx.height_map_samples, [[1.0, 2.0, 12.34]])


if __name__ == "__main__":
    unittest.main()
