from abc import ABC, abstractmethod
from typing import Mapping


class IPhysicalControlButtons(ABC):
    """Read the state of physical machine control buttons."""

    @abstractmethod
    def read_states(self) -> Mapping[str, bool]: ...

    @abstractmethod
    def is_pressed(self, button: str) -> bool: ...

    @abstractmethod
    def set_button(self, button: str, pressed: bool) -> None: ...

    @abstractmethod
    def read_output_states(self) -> Mapping[str, bool]: ...
