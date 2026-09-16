import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from src.engine.robot.calibration.intrinsic_capture.runner import (
    capture_charuco_sweep_dataset,
)
from src.engine.robot.calibration.intrinsic_capture.types import ImageInfo


class _PoseDrivenCharucoDetector:
    pose = None

    def __init__(self, **_kwargs):
        pass

    def detect(self, _frame):
        x, y = self.pose[0], self.pose[1]
        center_x = 320.0 - 2.0 * x
        center_y = 240.0 + 3.0 * y
        corners = np.array(
            [
                [center_x - 50.0, center_y - 40.0],
                [center_x, center_y - 40.0],
                [center_x + 50.0, center_y - 40.0],
                [center_x - 50.0, center_y + 40.0],
                [center_x, center_y + 40.0],
                [center_x + 50.0, center_y + 40.0],
            ],
            dtype=np.float32,
        ).reshape(-1, 1, 2)
        return SimpleNamespace(
            charuco_ids=np.arange(6),
            charuco_corners=corners,
            marker_ids=np.arange(6),
            mode="test",
        )


class IntrinsicCaptureRunnerTests(unittest.TestCase):
    def test_charuco_maps_image_grid_before_capture_and_respects_sweep_bounds(self):
        pose = [0.0, 0.0, 100.0, 180.0, 0.0, 0.0]
        _PoseDrivenCharucoDetector.pose = pose
        absolute_targets = []
        saved_tags = []

        def move_relative(**delta):
            pose[0] += delta.get("dx", 0.0)
            pose[1] += delta.get("dy", 0.0)
            return True

        def move_absolute(target):
            absolute_targets.append(list(target))
            pose[:] = target
            return True

        with patch(
            "src.engine.vision.implementation.VisionSystem.features.calibration.charuco.AutoCharucoBoardDetector",
            _PoseDrivenCharucoDetector,
        ):
            samples = capture_charuco_sweep_dataset(
                get_pose_fn=lambda: list(pose),
                move_relative_fn=move_relative,
                move_absolute_fn=move_absolute,
                grab_frame_fn=lambda: np.zeros((480, 640, 3), dtype=np.uint8),
                save_frame_fn=lambda _frame, tag: saved_tags.append(tag) or f"{tag}.png",
                image_info=ImageInfo(width=640, height=480),
                pattern_size=(19, 12),
                square_size_mm=15.0,
                marker_size_mm=11.0,
                aruco_dict_id=0,
                grid_rows=1,
                grid_cols=2,
                sweep_x_mm=50.0,
                sweep_y_mm=50.0,
                tilt_deg=0.0,
                z_delta_mm=0.0,
                min_corners=6,
                stabilization_delay_s=0.0,
                stop_event=threading.Event(),
                progress_cb=lambda _message: None,
                rz_deg=0.0,
                margin_px=60.0,
                probe_dx_mm=20.0,
                probe_dy_mm=20.0,
            )

        capture_targets = [target for target in absolute_targets if target[0] != 0.0]
        self.assertEqual(2, len(samples))
        self.assertEqual(["r0_c0_neutral", "r0_c1_neutral"], saved_tags)
        self.assertEqual(50.0, capture_targets[0][0])
        self.assertEqual(-50.0, capture_targets[1][0])


if __name__ == "__main__":
    unittest.main()
