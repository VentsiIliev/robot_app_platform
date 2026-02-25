from abc import ABC, abstractmethod
from typing import Optional, Generic, TypeVar

T = TypeVar('T')


class ISettingsRepository(ABC, Generic[T]):

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path

    @abstractmethod
    def load(self) -> T:
        pass

    @abstractmethod
    def save(self, settings: T) -> None:
        pass

    @abstractmethod
    def exists(self) -> bool:
        pass


class SettingsRepositoryError(Exception):
    pass


class SettingsLoadError(SettingsRepositoryError):
    pass


class SettingsSaveError(SettingsRepositoryError):
    pass