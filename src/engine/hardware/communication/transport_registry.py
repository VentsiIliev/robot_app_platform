from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.engine.hardware.communication.i_register_transport import IRegisterTransport
from src.engine.hardware.communication.modbus.modbus import ModbusConfig, ModbusDeviceConfig


TransportFactory = Callable[[ModbusDeviceConfig], IRegisterTransport]


@dataclass(frozen=True)
class TransportDescriptor:
    key: str
    label: str
    factory: TransportFactory


class TransportRegistry:
    """Engine-level registry of selectable hardware transport factories."""

    def __init__(self) -> None:
        self._descriptors: dict[str, TransportDescriptor] = {}

    def register(self, descriptor: TransportDescriptor) -> None:
        if descriptor.key in self._descriptors:
            raise ValueError(f"Transport already registered: {descriptor.key}")
        self._descriptors[descriptor.key] = descriptor

    def get(self, key: str) -> TransportDescriptor:
        try:
            return self._descriptors[key]
        except KeyError as exc:
            raise ValueError(f"Unknown transport type: {key}") from exc

    def descriptors(self) -> tuple[TransportDescriptor, ...]:
        return tuple(self._descriptors.values())

    def keys(self) -> tuple[str, ...]:
        return tuple(self._descriptors)

    def build_for_slave(self, config: ModbusConfig, slave_name: str) -> IRegisterTransport:
        slave = config.get_slave(slave_name)
        connection = config.get_connection(slave_name)
        return self.get(slave.transport_type).factory(connection)

    def build_for_slave_id(self, config: ModbusConfig, slave_id: int) -> IRegisterTransport:
        return self.build_for_slave(config, config.find_slave_name(slave_id))


def build_default_transport_registry() -> TransportRegistry:
    from src.engine.hardware.communication.modbus.modbus_register_transport import (
        ModbusRegisterTransport,
    )
    from src.engine.hardware.communication.modbus.xinje_ma_8x8yr_transport import (
        XinjeMA8X8YRTransport,
    )

    registry = TransportRegistry()
    registry.register(TransportDescriptor(
        key="modbus_register",
        label="Standard Modbus Registers",
        factory=lambda c: ModbusRegisterTransport(
            port=c.port, slave_address=c.slave_address, baudrate=c.baudrate,
            bytesize=c.bytesize, stopbits=c.stopbits, parity=c.parity, timeout=c.timeout,
        ),
    ))
    registry.register(TransportDescriptor(
        key="xinje_ma_8x8yr",
        label="Xinje MA-8X8YR",
        factory=lambda c: XinjeMA8X8YRTransport(
            port=c.port, slave_address=c.slave_address, baudrate=c.baudrate,
            bytesize=c.bytesize, stopbits=c.stopbits, parity=c.parity, timeout=c.timeout,
        ),
    ))
    return registry


DEFAULT_TRANSPORT_REGISTRY = build_default_transport_registry()
