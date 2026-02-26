import logging
from typing import List, Optional

from src.plugins.base.i_plugin_model import IPluginModel
from src.robot_apps.glue.glue_settings.model.mapper import GlueSettingsMapper
from src.robot_apps.glue.glue_settings.service.i_glue_settings_service import IGlueSettingsService
from src.robot_apps.glue.settings.glue import GlueSettings
from src.robot_apps.glue.settings.glue_types import Glue


class GlueSettingsModel(IPluginModel):

    def __init__(self, service: IGlueSettingsService):
        self._service  = service
        self._settings: Optional[GlueSettings] = None
        self._logger   = logging.getLogger(self.__class__.__name__)

    def load(self) -> GlueSettings:
        self._settings = self._service.load_settings()
        self._logger.debug("Glue settings loaded")
        return self._settings

    def save(self, flat: dict, **kwargs) -> None:
        base    = self._settings if self._settings is not None else GlueSettings()
        updated = GlueSettingsMapper.from_flat_dict(flat, base)
        self._service.save_settings(updated)
        self._settings = updated
        self._logger.info("Glue settings saved")

    def load_glue_types(self) -> List[Glue]:
        return self._service.load_glue_types()

    def add_glue_type(self, name: str, description: str) -> Glue:
        return self._service.add_glue_type(name, description)

    def update_glue_type(self, id_: str, name: str, description: str) -> Glue:
        return self._service.update_glue_type(id_, name, description)

    def remove_glue_type(self, id_: str) -> None:
        self._service.remove_glue_type(id_)