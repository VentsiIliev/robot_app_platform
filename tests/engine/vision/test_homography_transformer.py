import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.engine.vision.homography_transformer import HomographyTransformer


class TestHomographyTransformer(unittest.TestCase):
    def test_inverse_transform_round_trips_point(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            matrix_path = Path(tmp_dir) / "H.npy"
            matrix = np.array(
                [
                    [2.0, 0.0, 10.0],
                    [0.0, 3.0, 20.0],
                    [0.0, 0.0, 1.0],
                ]
            )
            np.save(matrix_path, matrix)

            transformer = HomographyTransformer(str(matrix_path))

            rx, ry = transformer.transform(5.0, 7.0)
            ix, iy = transformer.inverse_transform(rx, ry)

            self.assertAlmostEqual(ix, 5.0)
            self.assertAlmostEqual(iy, 7.0)


if __name__ == "__main__":
    unittest.main()
