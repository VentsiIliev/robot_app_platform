import logging
from typing import TYPE_CHECKING

from src.engine.robot.height_measuring.i_height_correction_service import IHeightCorrectionService
from src.engine.robot.height_measuring.area_grid_height_model import AreaGridHeightModel

if TYPE_CHECKING:
    from src.engine.robot.height_measuring.i_height_measuring_service import IHeightMeasuringService

_logger = logging.getLogger(__name__)


class HeightCorrectionService(IHeightCorrectionService):
    def __init__(self, height_service: "IHeightMeasuringService"):
        self._height_service = height_service
        self._model: AreaGridHeightModel | None = None

    def reload(self) -> None:
        self._model = None

    def predict_z(self, x: float, y: float) -> float | None:
        if self._model is None:
            data = self._height_service.get_depth_map_data()
            if data is None:
                return None
            model = AreaGridHeightModel.from_depth_map(data)
            if not model.is_supported():
                return None
            self._model = model
        z, mode = self._model.interpolate_height(float(x), float(y))
        if z is not None:
            _logger.debug("Height correction at (%.1f, %.1f): z=%.3f [%s]", x, y, z, mode)
        return z
