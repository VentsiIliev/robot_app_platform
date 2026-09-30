import unittest

import cv2
import numpy as np

from src.engine.vision.frame_orientation import (
    apply_orientation,
    is_transposing,
    normalize_rotation,
)


class TestNormalizeRotation(unittest.TestCase):
    def test_folds_arbitrary_multiples_of_ninety(self) -> None:
        self.assertEqual(normalize_rotation(0), 0)
        self.assertEqual(normalize_rotation(90), 90)
        self.assertEqual(normalize_rotation(450), 90)
        self.assertEqual(normalize_rotation(-90), 270)

    def test_rejects_values_that_are_not_multiples_of_ninety(self) -> None:
        for value in (45, 1, 100):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_rotation(value)

    def test_rejects_bool_and_non_integer(self) -> None:
        for value in (True, False, "90", 90.0, None):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_rotation(value)

    def test_only_quarter_turns_transpose(self) -> None:
        self.assertFalse(is_transposing(0))
        self.assertFalse(is_transposing(180))
        self.assertTrue(is_transposing(90))
        self.assertTrue(is_transposing(270))


class TestApplyOrientation(unittest.TestCase):
    def setUp(self) -> None:
        # Distinct pixel values so every axis permutation is unambiguous.
        self.frame = np.array([[1, 2, 3], [4, 5, 6]], dtype=np.uint8)

    def test_identity_returns_the_input_untouched(self) -> None:
        result = apply_orientation(self.frame)
        self.assertIs(result, self.frame)

    def test_ninety_degrees_rotates_clockwise(self) -> None:
        np.testing.assert_array_equal(
            apply_orientation(self.frame, rotate_degrees=90),
            cv2.rotate(self.frame, cv2.ROTATE_90_CLOCKWISE),
        )

    def test_two_hundred_seventy_degrees_rotates_counter_clockwise(self) -> None:
        np.testing.assert_array_equal(
            apply_orientation(self.frame, rotate_degrees=270),
            cv2.rotate(self.frame, cv2.ROTATE_90_COUNTERCLOCKWISE),
        )

    def test_rotation_is_applied_before_the_mirror(self) -> None:
        expected = cv2.flip(
            cv2.rotate(self.frame, cv2.ROTATE_90_CLOCKWISE), 0
        )
        np.testing.assert_array_equal(
            apply_orientation(self.frame, vertical=True, rotate_degrees=90),
            expected,
        )

    def test_rotation_transposes_the_frame_shape(self) -> None:
        rotated = apply_orientation(self.frame, rotate_degrees=90)
        self.assertEqual(rotated.shape[:2], (3, 2))
        flipped = apply_orientation(self.frame, horizontal=True)
        self.assertEqual(flipped.shape, self.frame.shape)


if __name__ == "__main__":
    unittest.main()
