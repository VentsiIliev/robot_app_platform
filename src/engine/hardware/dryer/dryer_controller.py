from __future__ import annotations

import logging

from src.engine.hardware.dryer.interfaces.i_dryer_controller import IDryerController
from src.engine.hardware.dryer.interfaces.i_dryer_transport import IDryerTransport
from src.engine.hardware.dryer.models.dryer_commands import DryerCommand
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.dryer.models.dryer_state import DryerState
from src.engine.hardware.dryer.models.dryer_write_data import DryerWriteData


class DryerController(IDryerController):
    """High-level dryer controller backed by register-block writes."""

    def __init__(
        self,
        transport: IDryerTransport,
        config: DryerConfig | None = None,
    ) -> None:
        self._transport = transport
        self._config = config or DryerConfig()
        self._config.require_contiguous_write_block()
        self._logger = logging.getLogger(self.__class__.__name__)

    def write_data(self, data: DryerWriteData) -> bool:
        values = data.to_register_values()
        try:
            self._transport.write_registers(self._config.block_start_register, values)
        except Exception:
            self._logger.exception(
                "Dryer write failed start_register=%d values=%s",
                self._config.block_start_register,
                values,
            )
            return False
        self._logger.info(
            "Dryer write ok start_register=%d values=%s",
            self._config.block_start_register,
            values,
        )
        return True

    def get_state(self) -> DryerState:
        try:
            raw_status = self._transport.read_register(self._config.status_register)
        except Exception as exc:
            self._logger.exception(
                "Dryer status read failed register=%d",
                self._config.status_register,
            )
            return DryerState(
                is_healthy=False,
                communication_errors=[str(exc)],
            )
        return DryerState.from_raw_status(int(raw_status))

    def move_servos(self, data: DryerWriteData | None = None) -> bool:
        return self._write_command(DryerCommand.MOVE_SERVOS, data)

    def open_plate(self, data: DryerWriteData | None = None) -> bool:
        return self._write_command(DryerCommand.OPEN_PLATE, data)

    def next_position(self, data: DryerWriteData | None = None) -> bool:
        return self._write_command(DryerCommand.NEXT_POSITION, data)

    def _write_command(
        self,
        command: DryerCommand,
        data: DryerWriteData | None,
    ) -> bool:
        payload = data or self._default_write_data()
        return self.write_data(
            DryerWriteData(
                status=payload.status,
                command=int(payload.command) | int(command),
                delay_move_up=payload.delay_move_up,
                delay_move_down=payload.delay_move_down,
                delay_move_in=payload.delay_move_in,
                delay_move_out=payload.delay_move_out,
                speed_of_plates=payload.speed_of_plates,
            )
        )

    def _default_write_data(self) -> DryerWriteData:
        return DryerWriteData(
            delay_move_up=self._config.default_delay_move_up,
            delay_move_down=self._config.default_delay_move_down,
            delay_move_in=self._config.default_delay_move_in,
            delay_move_out=self._config.default_delay_move_out,
            speed_of_plates=self._config.default_speed_of_plates,
        )
