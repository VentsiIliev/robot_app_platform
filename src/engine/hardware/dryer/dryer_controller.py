from __future__ import annotations

import logging
import time
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
        next_position_timeout_s: float = 10.0,
        status_poll_interval_s: float = 0.1,
        command_settle_s: float = 0.03,
    ) -> None:
        self._transport = transport
        self._config = config or DryerConfig()
        self._register_map = register_map or DryerRegisterMap()
        self._commands = dryer_commands(commands)
        self._statuses = dryer_statuses(statuses)
        self._next_position_timeout_s = max(0.0, float(next_position_timeout_s))
        self._status_poll_interval_s = max(0.0, float(status_poll_interval_s))
        self._command_settle_s = max(0.0, float(command_settle_s))
        self._register_map.require_contiguous()
        self._logger = logging.getLogger(self.__class__.__name__)

    def initialize(self) -> bool:
        """Write persisted defaults, then command the dryer to its next position."""
        if not self.write_data(DryerWriteData.from_config(self._config)):
            return False
        if not self.next_position():
            return False
        return self._wait_until_next_position_done()

    def _wait_until_next_position_done(self) -> bool:
        """Wait for NEXT_POS_DONE before reporting initialization success."""
        deadline = time.monotonic() + self._next_position_timeout_s
        while True:
            state = self.get_state()
            self._logger.info(
                "[DRYER] Initialization status raw=%#06x healthy=%s ready=%s next_pos_done=%s",
                int(state.raw_status),
                state.is_healthy,
                state.is_ready,
                state.next_position_done,
            )
            if state.is_healthy and state.next_position_done:
                self._logger.info("[DRYER] Initialization completed: next position confirmed")
                return True
            if time.monotonic() >= deadline:
                self._logger.error(
                    "[DRYER] Initialization failed: next position was not confirmed within %.1f s",
                    self._next_position_timeout_s,
                )
                return False
            time.sleep(self._status_poll_interval_s)

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
        raw_status = int(raw_status)
        state = DryerState.from_raw_status(raw_status, self._statuses)
        self._logger.debug(
            "Dryer status read register=%d raw=%d (%#06x) "
            "healthy=%s ready=%s ejecting=%s eject_done=%s "
            "next_position_moving=%s next_position_done=%s",
            int(self._register_map.status),
            raw_status,
            raw_status,
            state.is_healthy,
            state.is_ready,
            state.ejecting,
            state.eject_done,
            state.next_position_moving,
            state.next_position_done,
        )
        return state

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
            "[DRYER] Sending NEXT_POSITION command=%#04x command_register=%d",
            command,
            int(self._register_map.command),
        )
        try:
            self._transport.write_registers(self._register_map.command, [command])
            ok = True
        except Exception:
            self._logger.exception(
                "[DRYER] NEXT_POSITION FC16 single-register write failed command_register=%d command=%#04x",
                int(self._register_map.command),
                command,
            )
            ok = False
        if ok:
            time.sleep(self._command_settle_s)
        self._logger.info(
            "[DRYER] NEXT_POSITION FC16 write completed success=%s command_register=%d command=%#04x",
            ok,
            int(self._register_map.command),
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
        ok = self.write_data(DryerWriteData(**values))
        if ok:
            time.sleep(self._command_settle_s)
        return ok

    def _default_write_data(self) -> DryerWriteData:
        return DryerWriteData.from_config(self._config)
