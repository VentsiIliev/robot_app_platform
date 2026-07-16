from dataclasses import asdict
from typing import Any, Dict, Type, TypeVar

from src.engine.repositories.interfaces import ISettingsSerializer
from src.robot_systems.paint.processes.paint.config import (
    PAINT_PROCESS_CONFIG,
    PaintDropoffConfig,
    PaintEdgeCleanupConfig,
    PaintNavigationReturnConfig,
    PaintProcessConfig,
    PickupMotionConfig,
)

T = TypeVar("T")


def _section(raw: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = raw.get(key, {})
    return value if isinstance(value, dict) else {}


def _build_dataclass(cls: Type[T], raw: Dict[str, Any], default: T) -> T:
    values = asdict(default)
    values.update({key: value for key, value in raw.items() if key in values})
    return cls(**values)


class PaintProcessConfigSerializer(ISettingsSerializer[PaintProcessConfig]):
    @property
    def settings_type(self) -> str:
        return "paint_process_config"

    def get_default(self) -> PaintProcessConfig:
        return PAINT_PROCESS_CONFIG

    def to_dict(self, settings: PaintProcessConfig) -> Dict[str, Any]:
        return asdict(settings)

    def from_dict(self, data: Dict[str, Any]) -> PaintProcessConfig:
        default = self.get_default()
        values = asdict(default)
        raw = data if isinstance(data, dict) else {}
        values.update({
            key: value
            for key, value in raw.items()
            if key in values and key not in {
                "pickup_motion",
                "edge_cleanup",
                "dropoff",
                "navigation_return",
            }
        })
        values["pickup_motion"] = _build_dataclass(
            PickupMotionConfig,
            _section(raw, "pickup_motion"),
            default.pickup_motion,
        )
        values["edge_cleanup"] = _build_dataclass(
            PaintEdgeCleanupConfig,
            _section(raw, "edge_cleanup"),
            default.edge_cleanup,
        )
        values["dropoff"] = _build_dataclass(
            PaintDropoffConfig,
            _section(raw, "dropoff"),
            default.dropoff,
        )
        values["navigation_return"] = _build_dataclass(
            PaintNavigationReturnConfig,
            _section(raw, "navigation_return"),
            default.navigation_return,
        )
        return PaintProcessConfig(**values)
