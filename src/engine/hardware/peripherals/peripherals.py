from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer


@dataclass(frozen=True)
class PeripheralBinding:
    """Logical device mapping to one configured Modbus slave."""

    slave_id: int
    enabled: bool = True
    inputs: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    commands: dict[str, int] = field(default_factory=dict)
    statuses: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PeripheralBinding":
        return cls(
            slave_id=int(data["slave_id"]),
            enabled=bool(data.get("enabled", True)),
            inputs={str(key): str(value) for key, value in data.get("inputs", {}).items()},
            outputs={str(key): str(value) for key, value in data.get("outputs", {}).items()},
            commands={str(key): int(value) for key, value in data.get("commands", {}).items()},
            statuses={str(key): int(value) for key, value in data.get("statuses", {}).items()},
        )

    def to_dict(self) -> dict[str, Any]:
        result = {
            "enabled": self.enabled,
            "slave_id": self.slave_id,
            "inputs": dict(self.inputs),
            "outputs": dict(self.outputs),
            "commands": dict(self.commands),
            "statuses": dict(self.statuses),
        }
        return result


@dataclass(frozen=True)
class PeripheralConfig:
    """Logical Paint peripheral bindings, independent of transport protocol."""

    peripherals: dict[str, PeripheralBinding] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PeripheralConfig":
        return cls(
            peripherals={
                str(name): PeripheralBinding.from_dict(binding)
                for name, binding in data.items()
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {name: binding.to_dict() for name, binding in self.peripherals.items()}

    def get(self, name: str) -> PeripheralBinding | None:
        binding = self.peripherals.get(name)
        if binding is None or not binding.enabled:
            return None
        return binding


class PeripheralConfigSerializer(ISettingsSerializer[PeripheralConfig]):
    @property
    def settings_type(self) -> str:
        return "peripheral_config"

    def get_default(self) -> PeripheralConfig:
        return PeripheralConfig()

    def to_dict(self, settings: PeripheralConfig) -> dict[str, Any]:
        return settings.to_dict()

    def from_dict(self, data: dict[str, Any]) -> PeripheralConfig:
        return PeripheralConfig.from_dict(data)
