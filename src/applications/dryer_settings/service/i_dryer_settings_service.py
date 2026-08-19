from abc import ABC, abstractmethod

from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.dryer.models.dryer_state import DryerState
from src.engine.hardware.dryer.models.dryer_write_data import DryerWriteData


class IDryerSettingsService(ABC):
    @abstractmethod
    def load_config(self) -> DryerConfig: ...

    @abstractmethod
    def save_config(self, config: DryerConfig) -> None: ...

    @abstractmethod
    def get_state(self, config: DryerConfig) -> DryerState: ...

    @abstractmethod
    def move_servos(self, config: DryerConfig, data: DryerWriteData) -> bool: ...

    @abstractmethod
    def open_plate(self, config: DryerConfig, data: DryerWriteData) -> bool: ...

    @abstractmethod
    def next_position(self, config: DryerConfig, data: DryerWriteData) -> bool: ...
