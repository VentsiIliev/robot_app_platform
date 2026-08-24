from __future__ import annotations

import logging
from typing import Mapping

from src.engine.hardware.dryer.interfaces.i_dryer_controller import IDryerController
from src.engine.hardware.dryer.interfaces.i_dryer_transport import IDryerTransport
from src.engine.hardware.dryer.models.dryer_commands import DryerCommand, dryer_commands
from src.engine.hardware.dryer.models.dryer_status import dryer_statuses
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.dryer.models.dryer_state import DryerState
from src.engine.hardware.dryer.models.dryer_write_data import DryerWriteData
from src.engine.hardware.dryer.models.dryer_modbus_registers import DryerRegisterMap


class DryerController(IDryerController):
    """High-level dryer controller backed by register-block writes."""

    def __init__(
        self,
        transport: IDryerTransport,
        config: DryerConfig | None = None,
        register_map: DryerRegisterMap | None = None,
        commands: Mapping[str, int] | None = None,
        statuses: Mapping[str, int] | None = None,
    ) -> None:
        self._transport = transport
        self._config = config or DryerConfig()
        self._register_map = register_map or DryerRegisterMap()
        self._commands = dryer_commands(commands)
        self._statuses = dryer_statuses(statuses)
        self._register_map.require_contiguous()
        self._logger = logging.getLogger(self.__class__.__name__)

    def initialize(self) -> bool:
        """Synchronize the dryer firmware with the current persisted defaults."""
        return self.write_data(DryerWriteData.from_config(self._config))

    def shutdown(self) -> None:
        self._transport.disconnect()

    def update_config(self, config: DryerConfig) -> None:
        if not isinstance(config, DryerConfig):
            raise TypeError(f"Expected DryerConfig, got {type(config).__name__}")
        self._config = config

    def write_data(self, data: DryerWriteData) -> bool:
        values = data.to_register_values()
        try:
            self._transport.write_registers(self._register_map.status, values)
        except Exception:
            self._logger.exception(
                "Dryer write failed start_register=%d values=%s",
                self._register_map.status,
                values,
            )
            return False
        self._logger.info(
            "Dryer write ok start_register=%d values=%s",
            self._register_map.status,
            values,
        )
        return True

    def get_state(self) -> DryerState:
        try:
            raw_status = self._transport.read_register(self._register_map.status)
        except Exception as exc:
            self._logger.exception(
                "Dryer status read failed register=%d",
                self._register_map.status,
            )
            return DryerState(
                is_healthy=False,
                communication_errors=[str(exc)],
            )
        return DryerState.from_raw_status(int(raw_status), self._statuses)

    def move_servos(self, data: DryerWriteData | None = None) -> bool:
        return self.eject(data)

    def eject(self, data: DryerWriteData | None = None) -> bool:
        return self._write_command(self._commands["eject"], data)

    def open_plate(self, data: DryerWriteData | None = None) -> bool:
        return self._write_command(self._commands["close_plate"], data)

    def close_plage(self, data: DryerWriteData | None = None) -> bool:
        return self._write_command(self._commands["close_plate"], data)

    def close_plate(self, data: DryerWriteData | None = None) -> bool:
        """Compatibility-correct alias for the historical close_plage method."""
        return self.close_plage(data)

    def next_position(self, data: DryerWriteData | None = None) -> bool:
        payload = data or self._default_write_data()
        command = int(self._commands["next_position"])
        self._logger.info(
            "[DRYER] Sending NEXT_POSITION command=%#04x command_register=%d target_position=%d",
            command,
            int(self._register_map.command),
            int(payload.target_position_next_position),
        )
        ok = self._write_command(command, payload)
        self._logger.info(
            "[DRYER] NEXT_POSITION command write completed success=%s command=%#04x",
            ok,
            command,
        )
        return ok

    def execute_command(self, command: int, data: DryerWriteData | None = None) -> bool:
        """Write a command supplied by the robot-system peripheral config."""
        return self._write_command(int(command), data)

    def _write_command(
        self,
        command: DryerCommand | int,
        data: DryerWriteData | None,
    ) -> bool:
        payload = data or self._default_write_data()
        values = {**payload.__dict__, "command": int(command)}
        return self.write_data(DryerWriteData(**values))

    def _default_write_data(self) -> DryerWriteData:
        return DryerWriteData.from_config(self._config)
