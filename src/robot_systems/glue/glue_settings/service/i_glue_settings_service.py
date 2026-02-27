from abc import ABC, abstractmethod
from typing import List

from src.robot_systems.glue.settings.glue import GlueSettings
from src.robot_systems.glue.settings.glue_types import Glue


class IGlueSettingsService(ABC):

    @abstractmethod
    def load_settings(self) -> GlueSettings: ...

    @abstractmethod
    def save_settings(self, settings: GlueSettings) -> None: ...

    @abstractmethod
    def load_glue_types(self) -> List[Glue]: ...

    @abstractmethod
    def add_glue_type(self, name: str, description: str) -> Glue: ...

    @abstractmethod
    def update_glue_type(self, id_: str, name: str, description: str) -> Glue: ...

    @abstractmethod
    def remove_glue_type(self, id_: str) -> None: ...