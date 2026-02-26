import logging
from typing import Dict, Optional

from src.engine.hardware.weight.config import CellsConfig
from src.plugins.base.i_plugin_model import IPluginModel
from src.plugins.glue_cell_settings.model.mapper import GlueCellMapper
from src.plugins.glue_cell_settings.service.i_glue_cell_settings_service import IGlueCellSettingsService


class GlueCellSettingsModel(IPluginModel):

    def __init__(self, service: IGlueCellSettingsService):
        self._service  = service
        self._config:  Optional[CellsConfig] = None
        self._logger   = logging.getLogger(self.__class__.__name__)

    def load(self) -> CellsConfig:
        self._config = self._service.load_cells()
        return self._config

    def save(self, cell_id: int, flat: Dict) -> None:
        if self._config is None:
            self._config = self._service.load_cells()
        original = self._config.get_cell_by_id(cell_id)
        if original is None:
            self._logger.error("save: cell_id=%s not found", cell_id)
            return
        updated_cell  = GlueCellMapper.flat_to_cell(flat, original)
        updated_cells = CellsConfig(
            cells=[updated_cell if c.id == cell_id else c for c in self._config.cells]
        )
        self._service.save_cells(updated_cells)
        self._config  = updated_cells

        # push calibration to hardware after persisting to disk
        self._service.push_calibration(
            cell_id = cell_id,
            offset  = updated_cell.calibration.zero_offset,
            scale   = updated_cell.calibration.scale_factor,
        )
        self._logger.info("Cell %s saved and pushed to hardware", cell_id)

    def tare(self, cell_id: int) -> bool:
        return self._service.tare(cell_id)

    def get_cell_flat(self, cell_id: int) -> Optional[Dict]:
        if self._config is None:
            self._config = self._service.load_cells()
        cell = self._config.get_cell_by_id(cell_id)
        return GlueCellMapper.cell_to_flat(cell) if cell else None

    def get_cell_ids(self):
        if self._config is None:
            self._config = self._service.load_cells()
        return self._config.get_all_cell_ids()
