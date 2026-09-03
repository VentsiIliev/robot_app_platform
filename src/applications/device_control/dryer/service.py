from abc import ABC, abstractmethod

from src.engine.hardware.dryer.models.dryer_config import DryerConfig


class IDryerControlService(ABC):
    @abstractmethod
    def load_config(self) -> DryerConfig: ...

    @abstractmethod
    def save_config(self, config: DryerConfig) -> None: ...
