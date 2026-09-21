import unittest

from src.robot_systems.paint.processes.paint.motion import poses_close, shift_path_rotation


class TestShiftPathRotation(unittest.TestCase):
    def test_returns_a_copy_when_shift_is_zero(self):
        source = [[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]]

        shifted = shift_path_rotation(source, rotation_index=5, shift_degrees=0.0)

        self.assertEqual(source, shifted)
        self.assertIsNot(source, shifted)
        self.assertIsNot(source[0], shifted[0])

    def test_shifts_only_existing_rotation_components(self):
        source = [[1.0, 2.0], [1.0, 2.0, 3.0]]

        shifted = shift_path_rotation(source, rotation_index=2, shift_degrees=10.0)

        self.assertEqual([[1.0, 2.0], [1.0, 2.0, 13.0]], shifted)
        self.assertEqual([[1.0, 2.0], [1.0, 2.0, 3.0]], source)


class TestPosesClose(unittest.TestCase):
    def test_rejects_missing_or_incomplete_poses(self):
        self.assertFalse(poses_close(None, [0.0] * 6))
        self.assertFalse(poses_close([0.0] * 5, [0.0] * 6))

    def test_uses_tolerance_for_linear_axes(self):
        reference = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]

        self.assertTrue(poses_close(reference, [10.0005, 20.0, 30.0, 40.0, 50.0, 60.0]))
        self.assertFalse(poses_close(reference, [10.002, 20.0, 30.0, 40.0, 50.0, 60.0]))

    def test_treats_wrapped_rz_as_equivalent(self):
        self.assertTrue(
            poses_close(
                [10.0, 20.0, 30.0, 40.0, 50.0, 0.0],
                [10.0, 20.0, 30.0, 40.0, 50.0, 360.0],
            )
        )


if __name__ == "__main__":
    unittest.main()
