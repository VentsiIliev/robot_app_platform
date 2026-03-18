import unittest

from src.robot_systems.glue.processes.pick_and_place.execution import CalibrationToPickupPlaneMapper


class TestCalibrationToPickupPlaneMapper(unittest.TestCase):

    def test_maps_calibration_origin_to_pickup_origin(self):
        mapper = CalibrationToPickupPlaneMapper.from_positions(
            calibration_position=[-20.097, 331.717, 819.378, 179.915, 0.011, 0.001],
            pickup_position=[-232.343, -93.902, 819.846, 180.0, 0.0, 90.0],
        )

        x, y = mapper.map_point(-20.097, 331.717)

        self.assertAlmostEqual(x, -232.343, places=3)
        self.assertAlmostEqual(y, -93.902, places=3)

    def test_rotates_and_translates_calibration_plane_point_into_pickup_plane(self):
        mapper = CalibrationToPickupPlaneMapper.from_positions(
            calibration_position=[-20.097, 331.717, 819.378, 179.915, 0.011, 0.001],
            pickup_position=[-232.343, -93.902, 819.846, 180.0, 0.0, 90.0],
        )

        x, y = mapper.map_point(-10.097, 331.717)

        self.assertAlmostEqual(x, -232.343, places=3)
        self.assertAlmostEqual(y, -83.902, places=3)
