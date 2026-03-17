from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer

_DEFAULT_MOTORS = [
    {"name": "Glue Pump 1", "address": 0, "error_prefix": 1},
    {"name": "Glue Pump 2", "address": 2, "error_prefix": 2},
    {"name": "Glue Pump 3", "address": 4, "error_prefix": 3},
    {"name": "Glue Pump 4", "address": 6, "error_prefix": 4},
]

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

    @property
    def settings_type(self) -> str:
        return "glue_motor_config"

    def get_default(self) -> GlueMotorConfig:
        return GlueMotorConfig()

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
        raw   = data.get("motors", _DEFAULT_MOTORS)
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

