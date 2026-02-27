import logging
from typing import List, Optional

from src.engine.hardware.weight.config import CellsConfig
from src.engine.hardware.weight.interfaces.i_weight_cell_service import IWeightCellService
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.applications.glue_cell_settings.service.i_glue_cell_settings_service import IGlueCellSettingsService


class GlueCellSettingsService(IGlueCellSettingsService):

    def __init__(
        self,
        settings_service: ISettingsService,
        weight_service:   Optional[IWeightCellService] = None,
    ):
        self._settings = settings_service
        self._weight   = weight_service
        self._logger   = logging.getLogger(self.__class__.__name__)

    def load_cells(self) -> CellsConfig:
        return self._settings.get("glue_cells")

    def save_cells(self, config: CellsConfig) -> None:
        self._settings.save("glue_cells", config)
        self._logger.info("Saved %d cell configs", config.cell_count)

    def tare(self, cell_id: int) -> bool:
        if self._weight is None:
            self._logger.warning("tare: no weight service available")
            return False
        result = self._weight.tare(cell_id)
        self._logger.info("Tare cell %s → %s", cell_id, result)
        return result

    def push_calibration(self, cell_id: int, offset: float, scale: float) -> bool:
        if self._weight is None:
            self._logger.warning("push_calibration: no weight service available")
            return False
        result = self._weight.update_config(cell_id, offset, scale)
        self._logger.info(
            "push_calibration cell=%s offset=%.6f scale=%.6f → %s",
            cell_id, offset, scale, "ok" if result else "failed",
        )
        return result

    def get_cell_ids(self) -> List[int]:
        try:
            return self.load_cells().get_all_cell_ids()
        except Exception:
            return []
