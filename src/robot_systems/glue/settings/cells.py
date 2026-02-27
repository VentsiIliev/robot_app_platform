from src.engine.hardware.weight.config import (
    CalibrationConfig, MeasurementConfig, CellConfig,
    CellsConfig as GlueCellsConfig,
    CellsConfigSerializer,
)


def _default_cell(cell_id: int, url: str, motor_address: int = 0) -> CellConfig:
    return CellConfig(
        id=cell_id,
        type="Type A",
        url=url,
        capacity=1000.0,
        fetch_timeout_seconds=5.0,
        data_fetch_interval_ms=500,
        calibration=CalibrationConfig(
            zero_offset=0.0,
            scale_factor=1.0,
            temperature_compensation=False,
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


_DEFAULT_CELLS = GlueCellsConfig(
    cells=[
        _default_cell(0, "http://192.168.222.143/weight1", motor_address=0),
        _default_cell(1, "http://192.168.222.143/weight2", motor_address=2),
        _default_cell(2, "http://192.168.222.143/weight3", motor_address=4),
    ]
)


class GlueCellsConfigSerializer(CellsConfigSerializer):

    @property
    def settings_type(self) -> str:
        return "glue_cells"

    def get_default(self) -> GlueCellsConfig:
        return _DEFAULT_CELLS
