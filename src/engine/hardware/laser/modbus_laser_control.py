from __future__ import annotations

from src.engine.hardware.communication.i_register_transport import IRegisterTransport
from src.engine.core.i_health_checkable import IHealthCheckable
from src.engine.hardware.laser.i_laser_control import ILaserControl
from src.engine.hardware.xinje import XinjeMA8X8YR


class ModbusLaserControl(ILaserControl, IHealthCheckable):
    """Laser control through a register/coil transport."""

    def __init__(
        self,
        transport: IRegisterTransport,
        register: int | str = "Y5",
        on_value: int = 1,
        off_value: int = 0,
    ) -> None:
        self._transport = transport
        self._register = XinjeMA8X8YR.resolve_output(register)
        self._on_value = int(on_value)
        self._off_value = int(off_value)
        self._last_operation_ok = False

    def turn_on(self) -> None:
        self._write(self._on_value)

    def turn_off(self) -> None:
        self._write(self._off_value)

    def read_state(self) -> bool:
        try:
            value = self._transport.read_register(self._register)
        except Exception:
            self._last_operation_ok = False
            raise
        self._last_operation_ok = True
        return int(value) == self._on_value

    def is_healthy(self) -> bool:
        return self._last_operation_ok

    def _write(self, value: int) -> None:
        try:
            self._transport.write_register(self._register, value)
        except Exception:
            self._last_operation_ok = False
            raise
        self._last_operation_ok = True
