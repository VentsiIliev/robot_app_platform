from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from .settings_repository import ISettingsRepository


class ISettingsService(ABC):

    @abstractmethod
    def get(self, name: Enum) -> Any:
        ...

    @abstractmethod
    def get_repo(self, name: Enum) -> ISettingsRepository:
        ...

    @abstractmethod
    def reload(self, name: Enum) -> Any:
        ...

    @abstractmethod
    def save(self, name: Enum, settings: Any) -> None:
        ...