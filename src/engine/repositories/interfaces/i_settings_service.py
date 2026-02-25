from abc import ABC, abstractmethod
from typing import Any

from .settings_repository import ISettingsRepository


class ISettingsService(ABC):

    @abstractmethod
    def get(self, name: str) -> Any:
        ...

    @abstractmethod
    def get_repo(self, name: str) -> ISettingsRepository:
        ...

    @abstractmethod
    def reload(self, name: str) -> Any:
        ...

    @abstractmethod
    def save(self, name: str, settings: Any) -> None:
        ...