import threading
import unittest
from unittest.mock import MagicMock

from src.engine.robot.calibration.robot_calibration.RobotCalibrationContext import (
    RobotCalibrationContext,
)
from src.engine.robot.calibration.robot_calibration.live_feed import (
    show_live_feed,
)
from src.engine.robot.calibration.robot_calibration.model_fitting import (
    build_calibration_dataset,
)
from src.engine.robot.calibration.robot_calibration.overlay import (
    draw_live_overlay,
)
from src.engine.robot.calibration.robot_calibration.overlay_renderer import (
    NoOpCalibrationRenderer,
)
from src.engine.robot.calibration.robot_calibration.states.error_handling import (
    build_error_notification,
    fail_calibration,
)
from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import (
    RobotCalibrationStates,
)


class TestCalibrationModelFitting(unittest.TestCase):

    def test_build_calibration_dataset_uses_partitioned_groups(self):
        ctx = RobotCalibrationContext()
        ctx.target_plan.homography_marker_ids = [1, 2]
        ctx.target_plan.residual_marker_ids = [3]
        ctx.target_plan.validation_marker_ids = [4]
        ctx.artifacts.robot_positions_for_calibration = {
            1: (1.0, 1.0, 0.0, 0.0, 0.0, 0.0),
            2: (2.0, 2.0, 0.0, 0.0, 0.0, 0.0),
            3: (3.0, 3.0, 0.0, 0.0, 0.0, 0.0),
            4: (4.0, 4.0, 0.0, 0.0, 0.0, 0.0),
        }
        ctx.artifacts.camera_points_for_homography = {
            1: (10.0, 10.0),
            2: (20.0, 20.0),
            3: (30.0, 30.0),
            4: (40.0, 40.0),
            99: (99.0, 99.0),
        }

        dataset = build_calibration_dataset(ctx)

        self.assertEqual(dataset.homography_training_ids, [1, 2])
        self.assertEqual(dataset.residual_training_ids, [3])
        self.assertEqual(dataset.validation_ids, [4])
        self.assertEqual(dataset.dropped_camera_ids, [99])
        self.assertEqual(ctx.artifacts.camera_points_for_homography, {
            1: (10.0, 10.0),
            2: (20.0, 20.0),
            3: (30.0, 30.0),
            4: (40.0, 40.0),
        })


class TestCalibrationErrorHandling(unittest.TestCase):

    def test_fail_calibration_sets_error_and_returns_error_state(self):
        ctx = RobotCalibrationContext()

        result = fail_calibration(ctx, "broken")

        self.assertEqual(result, RobotCalibrationStates.ERROR)
        self.assertEqual(ctx.calibration_error_message, "broken")

    def test_build_error_notification_uses_grouped_state(self):
        ctx = RobotCalibrationContext()
        ctx.target_plan.target_marker_ids = [10, 20, 30]
        ctx.progress.current_marker_id = 1
        ctx.progress.iteration_count = 4
        ctx.progress.max_iterations = 50
        ctx.artifacts.robot_positions_for_calibration = {
            10: (1, 2, 3, 4, 5, 6),
        }
        ctx.calibration_error_message = "bad align"

        payload = build_error_notification(ctx)

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["message"], "bad align")
        self.assertEqual(payload["details"]["current_marker"], 1)
        self.assertEqual(payload["details"]["total_markers"], 3)
        self.assertEqual(payload["details"]["successful_markers"], 1)


class TestCalibrationVisualizationSeams(unittest.TestCase):

    def test_draw_live_overlay_uses_injected_renderer(self):
        ctx = RobotCalibrationContext()
        ctx.live_visualization = True
        ctx.target_plan.target_marker_ids = [1]
        ctx.progress.current_marker_id = 0
        ctx.progress.iteration_count = 2
        ctx.progress.max_iterations = 5
        ctx.progress.alignment_threshold_mm = 0.5
        ctx.calibration_renderer = MagicMock()
        frame = object()
        ctx.calibration_renderer.render_live_overlay.return_value = "rendered"

        rendered = draw_live_overlay(ctx, frame, current_error_mm=0.2)

        self.assertEqual(rendered, "rendered")
        ctx.calibration_renderer.render_live_overlay.assert_called_once()

    def test_show_live_feed_can_publish_without_visualization(self):
        ctx = RobotCalibrationContext()
        ctx.live_visualization = False
        ctx.broker = MagicMock()
        ctx.CALIBRATION_IMAGE_TOPIC = "topic"
        frame = MagicMock()

        result = show_live_feed(ctx, frame, broadcast_image=True)

        self.assertFalse(result)
        ctx.broker.publish.assert_called_once_with("topic", frame)

    def test_show_live_feed_returns_without_queueing_when_visualization_disabled(self):
        ctx = RobotCalibrationContext()
        ctx.live_visualization = False
        ctx.broker = None
        ctx.CALIBRATION_IMAGE_TOPIC = None
        ctx.calibration_renderer = NoOpCalibrationRenderer()

        result = show_live_feed(ctx, MagicMock(), broadcast_image=False)

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
