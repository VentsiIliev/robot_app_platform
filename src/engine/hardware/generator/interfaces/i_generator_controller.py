from abc import ABC, abstractmethod
from src.engine.hardware.generator.models.generator_state import GeneratorState


class IGeneratorController(ABC):

    @abstractmethod
    def turn_on(self) -> bool:
        """Turn on the generator."""
        ...

    @abstractmethod
    def turn_off(self) -> bool:
        """Turn off the generator."""
        ...

    @abstractmethod
    def get_state(self) -> GeneratorState:
        """Get the current state of the generator."""
        ...
