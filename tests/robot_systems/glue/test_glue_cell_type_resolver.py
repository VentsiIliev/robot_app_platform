import unittest

from src.engine.hardware.weight.config import CellConfig, CellsConfig, CalibrationConfig, MeasurementConfig
from src.robot_systems.glue.service_builders import GlueCellTypeResolver


def _cell(cell_id: int, glue_type: str, motor_address: int):
    return CellConfig(
        id=cell_id,
        type=glue_type,
        url=f"http://cell{cell_id}",
        capacity=1000.0,
        fetch_timeout_seconds=5.0,
        data_fetch_interval_ms=500,
        calibration=CalibrationConfig(
            zero_offset=0.0,
            scale_factor=1.0,
        ),
        measurement=MeasurementConfig(
            sampling_rate=10,
            filter_cutoff=1.0,
            averaging_samples=5,
            min_weight_threshold=0.0,
            max_weight_threshold=1000.0,
        ),
        motor_address=motor_address,
    )


class TestGlueCellTypeResolver(unittest.TestCase):
    def test_resolve_accepts_motor_address_zero(self):
        resolver = GlueCellTypeResolver(
            CellsConfig(cells=[_cell(0, "Type A", 0)])
        )

        self.assertEqual(resolver.resolve("Type A"), 0)

    def test_resolve_returns_matching_nonzero_motor_address(self):
        resolver = GlueCellTypeResolver(
            CellsConfig(cells=[_cell(1, "Type B", 4)])
        )

        self.assertEqual(resolver.resolve("Type B"), 4)

    def test_resolve_returns_minus_one_when_type_missing(self):
        resolver = GlueCellTypeResolver(
            CellsConfig(cells=[_cell(0, "Type A", 0)])
        )

        self.assertEqual(resolver.resolve("Type C"), -1)


if __name__ == "__main__":
    unittest.main()
