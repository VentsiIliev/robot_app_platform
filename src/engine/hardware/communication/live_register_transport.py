from __future__ import annotations

from typing import Callable

from src.engine.hardware.communication.i_register_transport import IRegisterTransport


class LiveRegisterTransport(IRegisterTransport):
    """Build a fresh concrete register transport from live settings on each call.

    This is useful when transport configuration is persisted in settings and may
    change at runtime. Instead of snapshotting Modbus parameters at construction
    time, callers provide a factory that reads the current settings and returns
    a concrete `IRegisterTransport` for each operation.
    """

    def __init__(self, build_transport: Callable[[], IRegisterTransport]) -> None:
        self._build_transport = build_transport

    def _fresh(self) -> IRegisterTransport:
        return self._build_transport()

    def write_register(self, address: int, value: int) -> None:
        self._fresh().write_register(address, value)

    def read_register(self, address: int) -> int:
        return self._fresh().read_register(address)

    def write_registers(self, address: int, values: list) -> None:
        self._fresh().write_registers(address, values)

    def read_registers(self, address: int, count: int) -> list:
        return self._fresh().read_registers(address, count)
