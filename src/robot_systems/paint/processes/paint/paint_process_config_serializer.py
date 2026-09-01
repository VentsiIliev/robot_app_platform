from dataclasses import asdict, replace
from typing import Any, Dict, Type, TypeVar

from src.engine.repositories.interfaces import ISettingsSerializer
from src.robot_systems.paint.processes.paint.config import (
    MAGAZINE_PICKUP_MODE_FIXED_GROUP_SENSOR_CONTROLLED_FAST_LIN,
    MAGAZINE_PICKUP_MODE_VISION_PLANNED,
    MAGAZINE_PICKUP_MODE_VISION_SENSOR_CONTROLLED_FAST_LIN,
    PAINT_PROCESS_CONFIG,
    PaintDropoffConfig,
    PaintEdgeCleanupConfig,
    PaintInterpolationConfig,
    PaintMagazineLoadConfig,
    PaintNavigationReturnConfig,
    PaintContactStagingConfig,
    PaintProcessConfig,
    PaintSafeTravelConfig,
    PaintToDropoffSafeTravelConfig,
    PickupMotionConfig,
    UnmatchedSecondPassConfig,
    normalize_magazine_pickup_mode,
    normalize_pickup_contact_mode,
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
                "contact_staging",
                "edge_cleanup",
                "dropoff",
                "magazine_load",
                "safe_travel",
                "dropoff_safe_travel",
                "navigation_return",
                "interpolation",
                "unmatched_second_pass",
            }
        })
        pickup_motion = _build_dataclass(
            PickupMotionConfig,
            _section(raw, "pickup_motion"),
            default.pickup_motion,
        )
        values["pickup_motion"] = replace(
            pickup_motion,
            pickup_contact_mode=normalize_pickup_contact_mode(
                pickup_motion.pickup_contact_mode
            ),
        )
        values["contact_staging"] = _build_dataclass(
            PaintContactStagingConfig,
            _section(raw, "contact_staging"),
            default.contact_staging,
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
        magazine_raw = dict(_section(raw, "magazine_load"))
        if "pickup_mode" not in magazine_raw:
            legacy_contact = str(
                _section(raw, "pickup_motion").get("magazine_pickup_contact_mode", "planned")
            ).strip().lower()
            legacy_target = str(magazine_raw.get("pickup_target_mode", "vision")).strip().lower()
            if legacy_contact == "servo_contact" and legacy_target == "fixed_group":
                magazine_raw["pickup_mode"] = MAGAZINE_PICKUP_MODE_FIXED_GROUP_SENSOR_CONTROLLED_FAST_LIN
            elif legacy_contact == "servo_contact":
                magazine_raw["pickup_mode"] = MAGAZINE_PICKUP_MODE_VISION_SENSOR_CONTROLLED_FAST_LIN
            else:
                magazine_raw["pickup_mode"] = MAGAZINE_PICKUP_MODE_VISION_PLANNED
        magazine_load = _build_dataclass(
            PaintMagazineLoadConfig,
            magazine_raw,
            default.magazine_load,
        )
        values["magazine_load"] = replace(
            magazine_load,
            pickup_mode=normalize_magazine_pickup_mode(magazine_load.pickup_mode),
        )
        values["safe_travel"] = _build_dataclass(
            PaintSafeTravelConfig,
            _section(raw, "safe_travel"),
            default.safe_travel,
        )
        values["dropoff_safe_travel"] = _build_dataclass(
            PaintToDropoffSafeTravelConfig,
            _section(raw, "dropoff_safe_travel"),
            default.dropoff_safe_travel,
        )
        values["navigation_return"] = _build_dataclass(
            PaintNavigationReturnConfig,
            _section(raw, "navigation_return"),
            default.navigation_return,
        )
        values["interpolation"] = _build_dataclass(
            PaintInterpolationConfig,
            _section(raw, "interpolation"),
            default.interpolation,
        )
        values["unmatched_second_pass"] = _build_dataclass(
            UnmatchedSecondPassConfig,
            _section(raw, "unmatched_second_pass"),
            default.unmatched_second_pass,
        )
        return PaintProcessConfig(**values)
