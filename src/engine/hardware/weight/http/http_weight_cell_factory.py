from src.engine.core.i_messaging_service import IMessagingService
from src.engine.hardware.weight.http.http_cell_transport import HttpCellTransport
from src.engine.hardware.weight.interfaces.i_cell_calibrator import ICellCalibrator
from src.engine.hardware.weight.interfaces.i_cell_transport import ICellTransport
from src.engine.hardware.weight.weight_cell_service import WeightCellService
from src.robot_systems.glue.settings.cells import CellConfig, GlueCellsConfig


def build_http_weight_cell_service(
    cells_config: GlueCellsConfig,
    messaging:    IMessagingService,
) -> WeightCellService:
    _cache: dict[int, HttpCellTransport] = {}

    def transport_factory(cfg: CellConfig) -> ICellTransport:
        if cfg.id not in _cache:
            _cache[cfg.id] = HttpCellTransport(cfg)
        return _cache[cfg.id]

    def calibrator_factory(cfg: CellConfig) -> ICellCalibrator:
        return transport_factory(cfg)

    return WeightCellService(
        cells_config       = cells_config,
        transport_factory  = transport_factory,
        calibrator_factory = calibrator_factory,
        messaging          = messaging,
    )
