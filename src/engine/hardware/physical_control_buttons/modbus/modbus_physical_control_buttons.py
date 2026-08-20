from __future__ import annotations

import logging

from src.engine.hardware.communication.i_register_transport import IRegisterTransport
from src.engine.core.i_health_checkable import IHealthCheckable
from src.engine.hardware.physical_control_buttons.interfaces.i_physical_control_buttons import IPhysicalControlButtons
from src.engine.hardware.xinje import XinjeMA8X8YR

_logger = logging.getLogger(__name__)


class ModbusPhysicalControlButtons(IPhysicalControlButtons, IHealthCheckable):
    """Read Xinje digital inputs configured as physical control buttons."""

    def __init__(
        self,
        transport: IRegisterTransport,
        inputs: dict[str, int | str],
        outputs: dict[str, int | str] | None = None,
    ) -> None:
        self._transport = transport
        self._inputs = {name: XinjeMA8X8YR.resolve_input(address) for name, address in inputs.items()}
        self._outputs = {
            name: XinjeMA8X8YR.resolve_output(address)
            for name, address in (outputs or {}).items()
        }
        self._last_operation_ok = False

    def read_states(self) -> dict[str, bool]:
        try:
            states = {name: self._read_input(address) for name, address in self._inputs.items()}
        except Exception:
            self._last_operation_ok = False
            raise
        self._last_operation_ok = True
        return states

    def is_pressed(self, button: str) -> bool:
        try:
            address = self._inputs[button]
        except KeyError as exc:
            raise KeyError(f"Unknown physical control button: {button}") from exc
        try:
            value = self._read_input(address)
        except Exception:
            self._last_operation_ok = False
            raise
        self._last_operation_ok = True
        return value

    def _read_input(self, address: int) -> bool:
        read_input = getattr(self._transport, "read_input", None)
        return bool(read_input(address) if read_input else self._transport.read_register(address))

    def set_button(self, button: str, pressed: bool) -> None:
        try:
            address = self._outputs[button]
        except KeyError as exc:
            raise KeyError(f"No output configured for physical control button: {button}") from exc
        value = 1 if pressed else 0
        _logger.info("Writing physical button output %s address=%d value=%d", button, address, value)
        try:
            self._transport.write_register(address, value)
        except Exception:
            self._last_operation_ok = False
            raise
        self._last_operation_ok = True

    def read_output_states(self) -> dict[str, bool]:
        states = {}
        try:
            for name, address in self._outputs.items():
                value = bool(self._transport.read_register(address))
                _logger.info("Read physical button output %s address=%d value=%s", name, address, value)
                states[name] = value
        except Exception:
            self._last_operation_ok = False
            raise
        self._last_operation_ok = True
        return states

    def is_healthy(self) -> bool:
        return self._last_operation_ok
