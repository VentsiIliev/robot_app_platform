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

    def get_addresses(self) -> List[int]:
        return [m.address for m in self.motors]

    def get_address_to_error_prefix(self) -> Dict[int, int]:
        return {m.address: m.error_prefix for m in self.motors if m.error_prefix != 0}


# Backwards-compatible alias used by application_wiring
DeviceControlConfig = GlueMotorConfig


class GlueMotorConfigSerializer(ISettingsSerializer[GlueMotorConfig]):

    @property
    def settings_type(self) -> str:
        return "glue_motor_config"

    def get_default(self) -> GlueMotorConfig:
        return GlueMotorConfig()

    def to_dict(self, settings: GlueMotorConfig) -> Dict[str, Any]:
        return {
            "motors": [
                {"name": m.name, "address": m.address, "error_prefix": m.error_prefix}
                for m in settings.motors
            ]
        }

    def from_dict(self, data: Dict[str, Any]) -> GlueMotorConfig:
        raw = data.get("motors", _DEFAULT_MOTORS)
        motors = [
            MotorSpec(
                name=str(m["name"]),
                address=int(m["address"]),
                error_prefix=int(m.get("error_prefix", 0)),
            )
            for m in raw
        ]
        return GlueMotorConfig(motors=motors)


# Backwards-compatible alias
DeviceControlConfigSerializer = GlueMotorConfigSerializer

