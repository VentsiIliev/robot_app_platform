from __future__ import annotations
import logging
from dataclasses import replace
from typing import Dict, List, Optional

from src.robot_systems.glue.settings_ids import SettingsID
from src.engine.hardware.weight.interfaces.i_weight_cell_service import IWeightCellService
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.robot_systems.glue.dashboard.service.i_glue_dashboard_service import IGlueDashboardService
from src.robot_systems.glue.processes.glue_operation_mode import GlueOperationMode
from src.robot_systems.glue.processes.glue_operation_coordinator import GlueOperationCoordinator
from src.robot_systems.glue.settings.cells import GlueCellsConfig
from src.robot_systems.glue.settings.glue_types import GlueCatalog


class GlueDashboardService(IGlueDashboardService):

    def __init__(
        self,
        runner:           GlueOperationCoordinator,
        settings_service: ISettingsService,
        weight_service:   Optional[IWeightCellService] = None,
    ):
        self._runner   = runner
        self._settings = settings_service
        self._weight   = weight_service
        self._logger   = logging.getLogger(self.__class__.__name__)

    # ── Commands — delegated to GlueOperationCoordinator ─────────────

    def start(self)        -> None: self._runner.start()
    def stop(self)         -> None: self._runner.stop()
    def pause(self)        -> None: self._runner.pause()
    def resume(self)       -> None: self._runner.resume()
    def reset_errors(self) -> None: self._runner.reset_errors()

    def clean(self) -> None:
        self._logger.info("clean")
        self._runner.clean()

    def set_mode(self, mode: str) -> None:
        operation_mode = GlueOperationMode.from_label(mode)
        self._logger.info("set_mode → %s", operation_mode.value)
        self._runner.set_mode(operation_mode)

    def change_glue(self, cell_id: int, glue_type: str) -> None:
        self._logger.info("change_glue → cell=%s type='%s'", cell_id, glue_type)
        try:
            cells_config: GlueCellsConfig = self._settings.get(SettingsID.GLUE_CELLS)
            cell = cells_config.get_cell_by_id(cell_id)
            if cell is None:
                self._logger.warning("change_glue: cell_id=%s not found", cell_id)
                return
            updated_cell  = replace(cell, type=glue_type)
            updated_cells = GlueCellsConfig(
                cells=[updated_cell if c.id == cell_id else c for c in cells_config.cells]
            )
            self._settings.save(SettingsID.GLUE_CELLS, updated_cells)
        except Exception:
            self._logger.exception("change_glue failed for cell=%s", cell_id)

    # ── Queries ───────────────────────────────────────────────────────

    def get_cell_capacity(self, cell_id: int) -> float:
        try:
            cells_config: GlueCellsConfig = self._settings.get(SettingsID.GLUE_CELLS)
            cell = cells_config.get_cell_by_id(cell_id)
            return cell.capacity if cell is not None else 0.0
        except Exception:
            self._logger.exception("get_cell_capacity failed for cell_id=%s", cell_id)
            return 0.0

    def get_cell_glue_type(self, cell_id: int) -> Optional[str]:
        try:
            cells_config: GlueCellsConfig = self._settings.get(SettingsID.GLUE_CELLS)
            cell = cells_config.get_cell_by_id(cell_id)
            return cell.type if cell else None
        except Exception:
            return None

    def get_all_glue_types(self) -> List[str]:
        try:
            catalog: GlueCatalog = self._settings.get(SettingsID.GLUE_CATALOG)
            return catalog.get_all_names()
        except Exception:
            return []

    def get_initial_cell_state(self, cell_id: int) -> Optional[Dict]:
        return None

    def get_cells_count(self) -> int:
        try:
            cells_config: GlueCellsConfig = self._settings.get(SettingsID.GLUE_CELLS)
            return cells_config.cell_count
        except Exception:
            self._logger.error("get_cells_count failed, returning 0")
            return 0

    def get_cell_connection_state(self, cell_id: int) -> str:
        if self._weight is None:
            return "disconnected"
        try:
            return self._weight.get_cell_state(cell_id).value
        except Exception:
            return "disconnected"
