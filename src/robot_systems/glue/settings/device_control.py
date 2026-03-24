from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer
from src.shared_contracts.declarations import DispenseChannelDefinition

_DEFAULT_MOTORS = []

_DEFAULT_BOARD = {
    "health_check_trigger_register": 17,
    "motor_error_count_register":    20,
    "motor_error_registers_start":   21,
    "health_check_delay_s":          3.0,
}


@dataclass
class MotorSpec:
    name:         str
    address:      int
    error_prefix: int = 0


@dataclass
class GlueMotorConfig:
    motors: List[MotorSpec] = field(default_factory=lambda: [
        MotorSpec(**m) for m in _DEFAULT_MOTORS
    ])

    # ── Board register map ────────────────────────────────────────────
    health_check_trigger_register: int   = _DEFAULT_BOARD["health_check_trigger_register"]
    motor_error_count_register:    int   = _DEFAULT_BOARD["motor_error_count_register"]
    motor_error_registers_start:   int   = _DEFAULT_BOARD["motor_error_registers_start"]
    health_check_delay_s:          float = _DEFAULT_BOARD["health_check_delay_s"]

    def get_addresses(self) -> List[int]:
        return [m.address for m in self.motors]

    def get_address_to_error_prefix(self) -> Dict[int, int]:
        return {m.address: m.error_prefix for m in self.motors if m.error_prefix != 0}


# Backwards-compatible alias
DeviceControlConfig = GlueMotorConfig


class GlueMotorConfigSerializer(ISettingsSerializer[GlueMotorConfig]):
    def __init__(self, default_channels: list[DispenseChannelDefinition] | None = None) -> None:
        self._default_channels = list(default_channels or [])

    def _default_motors(self) -> List[Dict[str, int | str]]:
        if not self._default_channels:
            return []
        return [
            {
                "name": f"{definition.label or definition.id} Pump",
                "address": int(definition.pump_motor_address),
                "error_prefix": index,
            }
            for index, definition in enumerate(self._default_channels, start=1)
        ]

    @property
    def settings_type(self) -> str:
        return "glue_motor_config"

    def get_default(self) -> GlueMotorConfig:
        return GlueMotorConfig(
            motors=[MotorSpec(**m) for m in self._default_motors()],
        )

    def to_dict(self, settings: GlueMotorConfig) -> Dict[str, Any]:
        return {
            "board": {
                "health_check_trigger_register": settings.health_check_trigger_register,
                "motor_error_count_register":    settings.motor_error_count_register,
                "motor_error_registers_start":   settings.motor_error_registers_start,
                "health_check_delay_s":          settings.health_check_delay_s,
            },
            "motors": [
                {"name": m.name, "address": m.address, "error_prefix": m.error_prefix}
                for m in settings.motors
            ],
        }

    def from_dict(self, data: Dict[str, Any]) -> GlueMotorConfig:
        board = data.get("board", _DEFAULT_BOARD)
        raw = data.get("motors", self._default_motors())
        return GlueMotorConfig(
            motors=[
                MotorSpec(
                    name=str(m["name"]),
                    address=int(m["address"]),
                    error_prefix=int(m.get("error_prefix", 0)),
                )
                for m in raw
            ],
            health_check_trigger_register = int(board.get("health_check_trigger_register", _DEFAULT_BOARD["health_check_trigger_register"])),
            motor_error_count_register    = int(board.get("motor_error_count_register",    _DEFAULT_BOARD["motor_error_count_register"])),
            motor_error_registers_start   = int(board.get("motor_error_registers_start",   _DEFAULT_BOARD["motor_error_registers_start"])),
            health_check_delay_s          = float(board.get("health_check_delay_s",        _DEFAULT_BOARD["health_check_delay_s"])),
        )


# Backwards-compatible alias
DeviceControlConfigSerializer = GlueMotorConfigSerializer
