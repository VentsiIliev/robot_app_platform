from abc import ABC, abstractmethod

from src.robot_systems.paint.processes.paint.config import PaintProcessConfig


class IPaintProcessSettingsService(ABC):
    @abstractmethod
    def load_settings(self) -> PaintProcessConfig: ...

    @abstractmethod
    def save_settings(self, settings: PaintProcessConfig) -> None: ...
