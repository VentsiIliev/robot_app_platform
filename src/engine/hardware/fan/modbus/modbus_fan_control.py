from __future__ import annotations

from src.engine.hardware.communication.i_register_transport import IRegisterTransport
from src.engine.hardware.fan.interfaces.i_fan_control import IFanControl
from src.engine.hardware.xinje import XinjeMA8X8YR


class ModbusFanControl(IFanControl):
    """Binary fan control through a configured register/coil transport."""

    def __init__(
        self,
        transport: IRegisterTransport,
        register: int | str = "Y0",
        on_value: int = 1,
        off_value: int = 0,
    ) -> None:
        self._transport = transport
        self._register = XinjeMA8X8YR.resolve_output(register)
        self._on_value = int(on_value)
        self._off_value = int(off_value)

    def turn_on(self) -> None:
        self._transport.write_register(self._register, self._on_value)

    def turn_off(self) -> None:
        self._transport.write_register(self._register, self._off_value)
