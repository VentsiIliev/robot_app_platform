import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.engine.robot.calibration.robot_calibration.online_navigation import predict_robot_xy


class OnlineNavigationTests(unittest.TestCase):
    def test_predicts_from_four_spread_training_samples(self):
        camera = {1: (0.0, 0.0), 2: (640.0, 0.0), 3: (0.0, 480.0), 4: (640.0, 480.0), 5: (320.0, 240.0)}
        robot = {
            marker_id: (pixel[0] * 0.5 + 10.0, pixel[1] * -0.25 + 20.0, 100.0)
            for marker_id, pixel in camera.items()
            if marker_id != 5
        }
        context = SimpleNamespace(
            artifacts=SimpleNamespace(
                camera_points_for_homography=camera,
                robot_positions_for_calibration=robot,
            ),
            target_plan=SimpleNamespace(homography_marker_ids=[1, 2, 3, 4]),
            vision_service=MagicMock(),
        )
        context.vision_service.get_camera_width.return_value = 640
        context.vision_service.get_camera_height.return_value = 480

        prediction = predict_robot_xy(context, 5)

        self.assertIsNotNone(prediction)
        self.assertAlmostEqual(170.0, prediction.robot_xy[0], places=3)
        self.assertAlmostEqual(-40.0, prediction.robot_xy[1], places=3)

    def test_requires_four_training_samples(self):
        context = SimpleNamespace(
            artifacts=SimpleNamespace(
                camera_points_for_homography={1: (0.0, 0.0)},
                robot_positions_for_calibration={1: (0.0, 0.0, 100.0)},
            ),
            target_plan=SimpleNamespace(homography_marker_ids=[1]),
            vision_service=MagicMock(),
        )
        self.assertIsNone(predict_robot_xy(context, 1))


if __name__ == "__main__":
    unittest.main()
