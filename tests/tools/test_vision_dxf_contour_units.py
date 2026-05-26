import unittest

import numpy as np

from src.tools.vision_dxf_exporter.contour_units import contours_to_calibrated_mm
from src.tools.vision_dxf_exporter.app import _scale_contours_from_mm


class _Transformer:
    def is_available(self):
        return True

    def transform(self, x, y):
        return x * 0.5 + 10.0, y * 0.25 - 5.0


class _UnavailableTransformer:
    def is_available(self):
        return False


class TestVisionDxfContourUnits(unittest.TestCase):
    def test_contours_to_calibrated_mm_maps_each_point(self):
        contour = np.asarray([[[0.0, 0.0]], [[20.0, 0.0]], [[20.0, 40.0]]], dtype=np.float32)

        result = contours_to_calibrated_mm([contour], _Transformer())

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].shape, (3, 1, 2))
        self.assertEqual(result[0].tolist(), [[[10.0, -5.0]], [[20.0, -5.0]], [[20.0, 5.0]]])

    def test_contours_to_calibrated_mm_requires_available_transformer(self):
        with self.assertRaises(RuntimeError):
            contours_to_calibrated_mm([np.zeros((3, 1, 2))], _UnavailableTransformer())

    def test_scale_contours_from_mm_converts_selected_export_units(self):
        contour = np.asarray([[[25.4, 0.0]], [[50.8, 25.4]]], dtype=np.float32)

        result = _scale_contours_from_mm([contour], "in")

        np.testing.assert_allclose(result[0], np.asarray([[[1.0, 0.0]], [[2.0, 1.0]]]))


if __name__ == "__main__":
    unittest.main()
