import os
import tempfile
import unittest

import cv2
import numpy as np

from src.tools.vision_dxf_exporter.calibration_transform import CameraPlaneCalibrationTransformer


class TestCameraPlaneCalibrationTransformer(unittest.TestCase):
    def test_transform_maps_projected_chessboard_point_back_to_mm(self):
        camera_matrix = np.asarray(
            [
                [800.0, 0.0, 320.0],
                [0.0, 800.0, 240.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        dist_coeffs = np.zeros((5, 1), dtype=np.float64)
        rvec = np.zeros((3, 1), dtype=np.float64)
        tvec = np.asarray([[0.0], [0.0], [1000.0]], dtype=np.float64)
        world = np.asarray([[[50.0, 25.0, 0.0]]], dtype=np.float64)
        image_points, _ = cv2.projectPoints(world, rvec, tvec, camera_matrix, dist_coeffs)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "calibration_data.npz")
            np.savez(
                path,
                camera_matrix=camera_matrix,
                dist_coeffs=dist_coeffs,
                rvecs=np.asarray([rvec]),
                tvecs=np.asarray([tvec]),
            )

            transformer = CameraPlaneCalibrationTransformer(path)
            x_mm, y_mm = transformer.transform(float(image_points[0, 0, 0]), float(image_points[0, 0, 1]))

        self.assertAlmostEqual(x_mm, 50.0, places=6)
        self.assertAlmostEqual(y_mm, 25.0, places=6)


if __name__ == "__main__":
    unittest.main()
