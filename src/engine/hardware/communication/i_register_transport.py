from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List


class IRegisterTransport(ABC):
    """
    Protocol-agnostic register I/O for any register-mapped device
    (motor controller, generator relay, solenoid board, etc.).

    Only read_register() is abstract — the minimum any implementation must provide.

    write_register  → defaults to write_registers([value])
    write_registers → defaults to looping write_register
    read_registers  → defaults to looping read_register

    Implementations override whichever is most efficient for their transport
    (Modbus overrides all four; a simple GPIO driver might only override
    read_register and write_register).

    connect/disconnect — no-ops by default; override for persistent connections.
    """

    @abstractmethod
    def read_register(self, address: int) -> int:
        """Read a single register. Raises on failure."""

    def read_registers(self, address: int, count: int) -> List[int]:
        """Read count registers. Default: loop. Override for batch efficiency."""
        return [self.read_register(address + i) for i in range(count)]

    def write_register(self, address: int, value: int) -> None:
        """Write one register. Default: delegates to write_registers."""
        self.write_registers(address, [value])

    def write_registers(self, address: int, values: List[int]) -> None:
        """Write consecutive registers. Default: loop. Override for batch efficiency."""
        for i, v in enumerate(values):
            self.write_register(address + i, v)

    def connect(self) -> None:
        """Open a persistent connection. No-op by default."""

    def disconnect(self) -> None:
        """Close the persistent connection. No-op by default."""