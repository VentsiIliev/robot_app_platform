from __future__ import annotations
import logging
from typing import Dict, List, Optional

from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.robot_apps.glue.dashboard.service.i_glue_dashboard_service import IGlueDashboardService
from src.robot_apps.glue.settings.cells import GlueCellsConfig
from src.robot_apps.glue.settings.glue_types import GlueCatalog


class GlueDashboardService(IGlueDashboardService):

    def __init__(self, robot_service: IRobotService, settings_service: ISettingsService):
        self._robot    = robot_service
        self._settings = settings_service
        self._logger   = logging.getLogger(self.__class__.__name__)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._logger.info("start")
        self._robot.enable_robot()

    def stop(self) -> None:
        self._logger.info("stop")
        self._robot.stop_motion()
        self._robot.disable_robot()

    def pause(self) -> None:
        self._logger.info("pause")
        self._robot.stop_motion()

    def clean(self) -> None:
        self._logger.info("clean")

    def reset_errors(self) -> None:
        self._logger.info("reset_errors")

    def set_mode(self, mode: str) -> None:
        self._logger.info("set_mode → %s", mode)

    def change_glue(self, cell_id: int, glue_type: str) -> None:
        self._logger.info("change_glue → cell=%s type='%s'", cell_id, glue_type)
        try:
            cells: GlueCellsConfig = self._settings.get("glue_cells")
            cell = cells.get_cell_by_id(cell_id)
            if cell is None:
                self._logger.warning("change_glue: cell_id=%s not found", cell_id)
                return
            # GlueCellsConfig is frozen — rebuild with updated type
            from dataclasses import replace
            updated_cell = replace(cell, type=glue_type)
            updated_cells = GlueCellsConfig(
                cells=[updated_cell if c.id == cell_id else c for c in cells.cells]
            )
            self._settings.save("glue_cells", updated_cells)
            self._logger.info("change_glue: cell=%s saved with type='%s'", cell_id, glue_type)
        except Exception:
            self._logger.exception("change_glue failed for cell=%s", cell_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_cell_capacity(self, cell_id: int) -> float:
        try:
            cells: GlueCellsConfig = self._settings.get("glue_cells")
            cell = cells.get_cell_by_id(cell_id)
            return cell.capacity if cell else 5000.0
        except Exception:
            return 5000.0

    def get_cell_glue_type(self, cell_id: int) -> Optional[str]:
        try:
            cells: GlueCellsConfig = self._settings.get("glue_cells")
            cell = cells.get_cell_by_id(cell_id)
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
