import hashlib
import unittest

from src.applications.workpiece_library.workpiece_thumbnail import (
    generate_thumbnail_bytes,
)
from src.robot_systems.glue.domain.workpieces.workpiece_thumbnail import (
    generate_thumbnail_bytes as legacy_generate_thumbnail_bytes,
)


_RAW_WORKPIECE = {
    "contour": {
        "contour": [
            [0, 0],
            [100, 0],
            [100, 50],
            [0, 50],
        ]
    },
    "sprayPattern": {
        "Contour": [
            {"contour": [[10, 10], [90, 10]]},
        ],
        "Fill": [
            {
                "contour": [
                    [20, 20],
                    [80, 20],
                    [80, 40],
                    [20, 40],
                ]
            },
        ],
    },
}


class TestWorkpieceThumbnail(unittest.TestCase):
    def test_rendering_matches_pre_extraction_golden_png(self):
        thumbnail = generate_thumbnail_bytes(_RAW_WORKPIECE, size=128)

        self.assertIsNotNone(thumbnail)
        self.assertEqual(len(thumbnail), 1335)
        self.assertEqual(
            hashlib.sha256(thumbnail).hexdigest(),
            "9797ee9f388296b45d6f2f980ef491ced02fde8656e993085c11df93aa899c10",
        )

    def test_legacy_glue_import_reexports_shared_renderer(self):
        self.assertIs(legacy_generate_thumbnail_bytes, generate_thumbnail_bytes)

    def test_returns_none_when_fewer_than_two_points_are_available(self):
        self.assertIsNone(generate_thumbnail_bytes({"contour": [[1, 2]]}))


if __name__ == "__main__":
    unittest.main()
