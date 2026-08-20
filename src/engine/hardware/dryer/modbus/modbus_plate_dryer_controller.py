from __future__ import annotations

import logging

from src.engine.hardware.communication.i_register_transport import IRegisterTransport
from src.engine.hardware.dryer.interfaces.i_dryer_controller import IDryerController
from src.engine.hardware.dryer.models.dryer_state import DryerState
from src.engine.hardware.dryer.models.dryer_write_data import DryerWriteData

_logger = logging.getLogger(__name__)


class ModbusPlateDryerController(IDryerController):
    """Minimal standard-Modbus dryer controller.

    Only the plate command register is implemented. The remaining dryer
    operations are deliberately logged as no-ops until their protocol is
    defined.
    """

    def __init__(
        self,
        transport: IRegisterTransport,
        plate_register: int = 2,
        open_value: int = 2,
        close_value: int = 0,
    ) -> None:
        self._transport = transport
        self._plate_register = int(plate_register)
        self._open_value = int(open_value)
        self._close_value = int(close_value)

    def write_data(self, data: DryerWriteData) -> bool:
        _logger.info("Dryer write_data is a no-op: %s", data)
        return True

    def get_state(self) -> DryerState:
        _logger.info("Dryer get_state is a no-op")
        return DryerState()

    def move_servos(self, data: DryerWriteData | None = None) -> bool:
        _logger.info("Dryer move_servos is a no-op")
        return True

    def next_position(self, data: DryerWriteData | None = None) -> bool:
        _logger.info("Dryer next_position is a no-op")
        return True

    def open_plate(self, data: DryerWriteData | None = None) -> bool:
        return self._write_plate(self._open_value, "open")

    def close_plage(self, data: DryerWriteData | None = None) -> bool:
        return self._write_plate(self._close_value, "close")

    def close_plate(self, data: DryerWriteData | None = None) -> bool:
        return self.close_plage(data)

    def _write_plate(self, value: int, action: str) -> bool:
        _logger.debug(
            "Dryer plate write requested action=%s register=%d value=%d transport=%s",
            action,
            self._plate_register,
            value,
            type(self._transport).__name__,
        )
        try:
            # The dryer accepts the one-register FC16 command used by the
            # direct minimalmodbus diagnostic script.
            self._transport.write_registers(self._plate_register, [value])
        except Exception:
            _logger.exception(
                "Dryer plate %s failed register=%d value=%d",
                action,
                self._plate_register,
                value,
            )
            return False
        _logger.info(
            "Dryer plate %s register=%d value=%d",
            action,
            self._plate_register,
            value,
        )
        _logger.debug(
            "Dryer plate write completed action=%s register=%d value=%d",
            action,
            self._plate_register,
            value,
        )
        return True

    def close(self) -> None:
        self._transport.disconnect()
