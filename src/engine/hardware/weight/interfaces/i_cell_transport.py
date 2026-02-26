from abc import ABC, abstractmethod


class ICellTransport(ABC):
    """
    Responsible for raw communication with a single cell.
    Knows nothing about calibration or business logic.
    """

    @abstractmethod
    def connect(self) -> bool: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def read_weight(self) -> float: ...