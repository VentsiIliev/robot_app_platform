import math
import unittest

from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_execute_pickup_release_handler import (
    calculate_workpiece_dropoff_pose,
)


class TestMagazinePickupReleasePose(unittest.TestCase):
    def test_applies_calibration_to_plate_rotation_to_workpiece_rz(self) -> None:
        result = calculate_workpiece_dropoff_pose(
            calibration_pose=[10.0, 20.0, 30.0, 180.0, 0.0, 0.0],
            plate_dropoff_pose=[100.0, 200.0, 40.0, 179.0, 1.0, 90.0],
            workpiece_rz_at_calibration_deg=25.0,
        )

        self.assertEqual(result, [100.0, 200.0, 40.0, 179.0, 1.0, 115.0])

    def test_unwraps_result_near_taught_plate_orientation(self) -> None:
        result = calculate_workpiece_dropoff_pose(
            calibration_pose=[0.0, 0.0, 0.0, 180.0, 0.0, 170.0],
            plate_dropoff_pose=[1.0, 2.0, 3.0, 180.0, 0.0, -170.0],
            workpiece_rz_at_calibration_deg=175.0,
        )

        self.assertAlmostEqual(result[5], -165.0)

    def test_does_not_modify_input_pose(self) -> None:
        plate_pose = [100.0, 200.0, 40.0, 179.0, 1.0, 90.0]

        calculate_workpiece_dropoff_pose(
            calibration_pose=[10.0, 20.0, 30.0, 180.0, 0.0, 0.0],
            plate_dropoff_pose=plate_pose,
            workpiece_rz_at_calibration_deg=25.0,
        )

        self.assertEqual(plate_pose, [100.0, 200.0, 40.0, 179.0, 1.0, 90.0])

    def test_rejects_non_finite_orientation(self) -> None:
        with self.assertRaisesRegex(ValueError, "Workpiece calibration RZ must be finite"):
            calculate_workpiece_dropoff_pose(
                calibration_pose=[0.0] * 6,
                plate_dropoff_pose=[0.0] * 6,
                workpiece_rz_at_calibration_deg=math.nan,
            )


if __name__ == "__main__":
    unittest.main()
