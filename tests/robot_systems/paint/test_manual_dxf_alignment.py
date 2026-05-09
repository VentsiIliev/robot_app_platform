import unittest

from src.robot_systems.paint.domain.manual_dxf_alignment import (
    apply_manual_similarity_transform_to_raw,
)


class TestManualDxfAlignment(unittest.TestCase):
    def test_apply_manual_similarity_transform_to_raw_updates_main_and_process_contours(self):
        raw = {
            "contour": [
                [[0.0, 0.0]],
                [[10.0, 0.0]],
                [[10.0, 10.0]],
                [[0.0, 10.0]],
            ],
            "pickupPoint": [5.0, 5.0],
            "sprayPattern": {
                "Contour": [
                    {
                        "contour": [
                            [[2.0, 2.0]],
                            [[4.0, 2.0]],
                        ],
                    }
                ],
                "Fill": [],
            },
        }

        transformed = apply_manual_similarity_transform_to_raw(
            raw,
            rotation_deg=0.0,
            scale=1.0,
            translation_x_px=3.0,
            translation_y_px=-2.0,
        )

        self.assertEqual([3.0, -2.0], transformed["contour"][0][0])
        self.assertEqual([13.0, -2.0], transformed["contour"][1][0])
        self.assertEqual([5.0, 0.0], transformed["sprayPattern"]["Contour"][0]["contour"][0][0])
        self.assertEqual([8.0, 3.0], transformed["pickupPoint"])


if __name__ == "__main__":
    unittest.main()
