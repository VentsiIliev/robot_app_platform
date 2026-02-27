from typing import List

from src.robot_apps.glue.glue_settings.service.i_glue_settings_service import IGlueSettingsService
from src.robot_apps.glue.settings.glue import GlueSettings
from src.robot_apps.glue.settings.glue_types import Glue


class StubGlueSettingsService(IGlueSettingsService):

    def __init__(self):
        self._settings = GlueSettings()
        self._types: List[Glue] = [
            Glue(name="Type A", description="Standard type A"),
            Glue(name="Type B", description="Standard type B"),
        ]

    def load_settings(self) -> GlueSettings:
        return self._settings

    def save_settings(self, settings: GlueSettings) -> None:
        self._settings = settings
        print(f"[StubGlueSettingsService] save_settings → {settings}")

    def load_glue_types(self) -> List[Glue]:
        return list(self._types)

    def add_glue_type(self, name: str, description: str) -> Glue:
        glue = Glue(name=name, description=description)
        self._types.append(glue)
        print(f"[StubGlueSettingsService] add_glue_type → {name!r}")
        return glue

    def update_glue_type(self, id_: str, name: str, description: str) -> Glue:
        for g in self._types:
            if g.id == id_:
                g.name        = name
                g.description = description
                print(f"[StubGlueSettingsService] update_glue_type → {name!r}")
                return g
        raise KeyError(id_)

    def remove_glue_type(self, id_: str) -> None:
        self._types[:] = [g for g in self._types if g.id != id_]
        print(f"[StubGlueSettingsService] remove_glue_type → {id_}")