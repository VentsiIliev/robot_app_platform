from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List


class IMotorTransport(ABC):
    """
    Low-level register I/O — protocol-agnostic (Modbus RTU, CAN, simulated, etc.).
    All methods rise on failure — callers are responsible for exception handling.

    Optional connect/disconnect allows persistent connections for hot-path
    operations (e.g. repeated speed adjustments). The default implementation is no-op.
    """

    @abstractmethod
    def write_registers(self, address: int, values: List[int]) -> None:
        """Write values to consecutive registers starting at address."""

    @abstractmethod
    def read_register(self, address: int) -> int:
        """Read a single register value."""

    @abstractmethod
    def read_registers(self, address: int, count: int) -> List[int]:
        """Read count consecutive registers starting at address."""

    def connect(self) -> None:
        """Optional: open a persistent connection for repeated operations."""

    def disconnect(self) -> None:
        """Optional: close the persistent connection."""