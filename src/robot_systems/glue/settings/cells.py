from src.engine.hardware.weight.config import (
    CalibrationConfig, MeasurementConfig, CellConfig,
    CellsConfig as GlueCellsConfig,
    CellsConfigSerializer,
)
from src.shared_contracts.declarations import DispenseChannelDefinition


def _default_cell(
    cell_id: int,
    url: str,
    motor_address: int = 0,
    glue_type: str = "",
) -> CellConfig:
    return CellConfig(
        id=cell_id,
        type=glue_type,
        url=url,
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


def _default_url(cell_id: int) -> str:
    return f"http://192.168.222.143/weight{int(cell_id) + 1}"


class GlueCellsConfigSerializer(CellsConfigSerializer):
    def __init__(self, default_channels: list[DispenseChannelDefinition] | None = None) -> None:
        self._default_channels = list(default_channels or [])

    @property
    def settings_type(self) -> str:
        return "glue_cells"

    def get_default(self) -> GlueCellsConfig:
        return GlueCellsConfig(
            cells=[
                _default_cell(
                    definition.weight_cell_id,
                    _default_url(definition.weight_cell_id),
                    motor_address=definition.pump_motor_address,
                    glue_type=definition.default_glue_type,
                )
                for definition in self._default_channels
            ]
        )
