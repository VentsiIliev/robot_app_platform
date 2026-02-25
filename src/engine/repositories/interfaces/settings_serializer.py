from abc import ABC, abstractmethod
from typing import Dict, Any, Generic, TypeVar

T = TypeVar('T')


class ISettingsSerializer(ABC, Generic[T]):

    @abstractmethod
    def to_dict(self, settings: T) -> Dict[str, Any]:
        pass

    @abstractmethod
    def from_dict(self, data: Dict[str, Any]) -> T:
        pass

    @abstractmethod
    def get_default(self) -> T:
        pass

    @property
    @abstractmethod
    def settings_type(self) -> str:
        pass

