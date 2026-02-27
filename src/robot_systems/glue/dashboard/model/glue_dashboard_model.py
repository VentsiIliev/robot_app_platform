from __future__ import annotations
import logging
from typing import Dict, List, Optional

from src.plugins.base.i_plugin_model import IPluginModel
from src.robot_systems.glue.dashboard.config import GlueDashboardConfig
from src.robot_systems.glue.dashboard.service.i_glue_dashboard_service import IGlueDashboardService


class GlueDashboardModel(IPluginModel):

    def __init__(self, service: IGlueDashboardService, config: GlueDashboardConfig = None):
        self._service = service
        self._config  = config or GlueDashboardConfig()
        self._logger  = logging.getLogger(self.__class__.__name__)

    # ── IPluginModel contract ─────────────────────────────────────────────

    def load(self) -> GlueDashboardConfig:
        """Return the dashboard config — initial state is pulled per-cell by the controller."""
        return self._config

    def save(self, *args, **kwargs) -> None:
        """Not applicable — dashboard state is not persisted."""
        pass

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def config(self) -> GlueDashboardConfig:
        return self._config

    def get_cell_capacity(self, cell_id: int) -> float:         return self._service.get_cell_capacity(cell_id)
    def get_cell_glue_type(self, cell_id: int) -> Optional[str]: return self._service.get_cell_glue_type(cell_id)
    def get_all_glue_types(self) -> List[str]:                   return self._service.get_all_glue_types()
    def get_initial_cell_state(self, cell_id: int) -> Optional[Dict]: return self._service.get_initial_cell_state(cell_id)
    def get_cells_count(self) -> int: return self._service.get_cells_count()
    def get_cell_connection_state(self, cell_id: int) -> str:
        return self._service.get_cell_connection_state(cell_id)

    def start(self)                                   -> None: self._service.start()
    def stop(self)                                    -> None: self._service.stop()
    def pause(self)                                   -> None: self._service.pause()
    def clean(self)                                   -> None: self._service.clean()
    def reset_errors(self)                            -> None: self._service.reset_errors()
    def set_mode(self, mode: str)                     -> None: self._service.set_mode(mode)
    def change_glue(self, cell_id: int, glue_type: str) -> None: self._service.change_glue(cell_id, glue_type)

