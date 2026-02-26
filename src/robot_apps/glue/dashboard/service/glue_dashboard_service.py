from __future__ import annotations
import logging
from dataclasses import replace
from typing import Dict, List, Optional

from src.engine.core.i_messaging_service import IMessagingService
from src.engine.hardware.weight.interfaces.i_weight_cell_service import IWeightCellService
from src.engine.process.base_process import BaseProcess
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.robot_apps.glue.dashboard.service.i_glue_dashboard_service import IGlueDashboardService
from src.robot_apps.glue.settings.cells import GlueCellsConfig
from src.robot_apps.glue.settings.glue_types import GlueCatalog


class GlueDashboardService(BaseProcess, IGlueDashboardService):

    def __init__(
        self,
        process_id:       str,
        robot_service:    IRobotService,
        settings_service: ISettingsService,
        messaging:        IMessagingService,
        weight_service:   Optional[IWeightCellService] = None,
    ):
        BaseProcess.__init__(self, process_id, messaging)
        self._robot    = robot_service
        self._settings = settings_service
        self._weight   = weight_service

    # ── BaseProcess hooks ─────────────────────────────────────────────

    def _on_start(self) -> None:
        self._robot.enable_robot()

    def _on_stop(self) -> None:
        self._robot.stop_motion()
        self._robot.disable_robot()

    def _on_pause(self) -> None:
        self._robot.stop_motion()

    def _on_resume(self) -> None:
        self._robot.enable_robot()

    def _on_reset_errors(self) -> None:
        pass

    # ── IGlueDashboardService ─────────────────────────────────────────

    def clean(self) -> None:
        self._logger.info("clean")

    def set_mode(self, mode: str) -> None:
        self._logger.info("set_mode → %s", mode)

    def change_glue(self, cell_id: int, glue_type: str) -> None:
        self._logger.info("change_glue → cell=%s type='%s'", cell_id, glue_type)
        try:
            cells_config: GlueCellsConfig = self._settings.get("glue_cells")
            cell = cells_config.get_cell_by_id(cell_id)
            if cell is None:
                self._logger.warning("change_glue: cell_id=%s not found", cell_id)
                return
            updated_cell  = replace(cell, type=glue_type)
            updated_cells = GlueCellsConfig(
                cells=[updated_cell if c.id == cell_id else c for c in cells_config.cells]
            )
            self._settings.save("glue_cells", updated_cells)
        except Exception:
            self._logger.exception("change_glue failed for cell=%s", cell_id)

    def get_cell_capacity(self, cell_id: int) -> float:
        try:
            cells_config: GlueCellsConfig = self._settings.get("glue_cells")
            cell = cells_config.get_cell_by_id(cell_id)
            return cell.capacity if cell is not None else 0.0
        except Exception:
            self._logger.exception("get_cell_capacity failed for cell_id=%s", cell_id)
            return 0.0

    def get_cell_glue_type(self, cell_id: int) -> Optional[str]:
        try:
            cells_config: GlueCellsConfig = self._settings.get("glue_cells")
            cell = cells_config.get_cell_by_id(cell_id)
            return cell.type if cell else None
        except Exception:
            return None

    def get_all_glue_types(self) -> List[str]:
        try:
            catalog: GlueCatalog = self._settings.get("glue_catalog")
            return catalog.get_all_names()
        except Exception:
            return []

    def get_initial_cell_state(self, cell_id: int) -> Optional[Dict]:
        return None

    def get_cells_count(self) -> int:
        try:
            cells_config: GlueCellsConfig = self._settings.get("glue_cells")
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
