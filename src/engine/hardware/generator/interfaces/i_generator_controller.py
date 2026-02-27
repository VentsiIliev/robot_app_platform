from abc import ABC, abstractmethod
from src.engine.hardware.generator.models.generator_state import GeneratorState


class IGeneratorController(ABC):

    @abstractmethod
    def turn_on(self) -> bool: ...

    @abstractmethod
    def turn_off(self) -> bool: ...

    @abstractmethod
    def get_state(self) -> GeneratorState: ...