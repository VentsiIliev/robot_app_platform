from typing import List

from src.robot_systems.glue.applications.glue_settings import IGlueSettingsService
from src.robot_systems.glue.settings_ids import SettingsID
from src.engine.repositories.interfaces.i_settings_service import ISettingsService

from src.robot_systems.glue.settings.glue import GlueSettings
from src.robot_systems.glue.settings.glue_types import Glue, GlueCatalog


class GlueSettingsApplicationService(IGlueSettingsService):

    def __init__(self, settings_service: ISettingsService):
        self._settings = settings_service

    def load_settings(self) -> GlueSettings:
        return self._settings.get(SettingsID.GLUE_SETTINGS)

    def save_settings(self, settings: GlueSettings) -> None:
        self._settings.save(SettingsID.GLUE_SETTINGS, settings)

    def load_glue_types(self) -> List[Glue]:
        catalog: GlueCatalog = self._settings.get(SettingsID.GLUE_CATALOG)
        return list(catalog.glue_types)

    def add_glue_type(self, name: str, description: str) -> Glue:
        catalog: GlueCatalog = self._settings.get(SettingsID.GLUE_CATALOG)
        glue = Glue(name=name, description=description)
        catalog.add(glue)
        self._settings.save(SettingsID.GLUE_CATALOG, catalog)
        return glue

    def update_glue_type(self, id_: str, name: str, description: str) -> Glue:
        catalog: GlueCatalog = self._settings.get(SettingsID.GLUE_CATALOG)
        glue = catalog.get_by_id(id_)
        if glue is None:
            raise KeyError(id_)
        glue.name        = name
        glue.description = description
        self._settings.save(SettingsID.GLUE_CATALOG, catalog)
        return glue

    def remove_glue_type(self, id_: str) -> None:
        catalog: GlueCatalog = self._settings.get(SettingsID.GLUE_CATALOG)
        if not catalog.remove_by_id(id_):
            raise KeyError(id_)
        self._settings.save(SettingsID.GLUE_CATALOG, catalog)