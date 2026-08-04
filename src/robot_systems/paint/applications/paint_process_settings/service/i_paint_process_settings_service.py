from abc import ABC, abstractmethod

from src.robot_systems.paint.processes.paint.config import PaintProcessConfig


class IPaintProcessSettingsService(ABC):
    @abstractmethod
    def load_settings(self) -> PaintProcessConfig: ...

    @abstractmethod
    def save_settings(self, settings: PaintProcessConfig) -> None: ...

    @abstractmethod
    def is_dropoff_movement_group_configured(self) -> bool: ...

    @abstractmethod
    def dropoff_movement_group_configuration_error(self) -> str: ...

    @abstractmethod
    def get_current_robot_position(self) -> list[float] | None: ...
