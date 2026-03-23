from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.engine.repositories.interfaces import ISettingsSerializer
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.targeting.frame_names import CALIBRATION_FRAME
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.targeting.point_names import CAMERA_POINT, POINT_ALIASES


@dataclass
class MyTargetPoint:
    name: str
    display_name: str = ""
    x_mm: float = 0.0
    y_mm: float = 0.0


@dataclass
class MyTargetFrameDefinition:
    name: str
    source_navigation_group: str = ""
    target_navigation_group: str = ""
    use_height_correction: bool = False


@dataclass
class MyTargetingSettings:
    points: list[MyTargetPoint] = field(default_factory=list)
    frames: list[MyTargetFrameDefinition] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)

    @classmethod
    def defaults(cls) -> "MyTargetingSettings":
        return cls(
            points=[
                # TODO: Define required canonical points here.
                MyTargetPoint(name=CAMERA_POINT, display_name="camera", x_mm=0.0, y_mm=0.0),
            ],
            frames=[
                # TODO: Define default frames here.
                MyTargetFrameDefinition(
                    name=CALIBRATION_FRAME,
                    source_navigation_group="",
                    target_navigation_group="",
                    use_height_correction=True,
                ),
            ],
            aliases=dict(POINT_ALIASES),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MyTargetingSettings":
        # TODO: Parse POINTS / FRAMES / ALIASES from persisted JSON.
        # Keep this shape compatible with RobotSettings targeting editing if possible.
        return cls.defaults()

    def to_dict(self) -> dict[str, Any]:
        # TODO: Serialize back to persisted JSON.
        return {
            "POINTS": [],
            "FRAMES": [],
            "ALIASES": dict(self.aliases),
        }

    def ensure_defaults(self) -> None:
        # TODO: Deduplicate and reinsert required canonical points/frames here.
        pass


class MyTargetingSettingsSerializer(ISettingsSerializer[MyTargetingSettings]):
    @property
    def settings_type(self) -> str:
        return "my_targeting"

    def get_default(self) -> MyTargetingSettings:
        return MyTargetingSettings.defaults()

    def to_dict(self, settings: MyTargetingSettings) -> dict[str, Any]:
        return settings.to_dict()

    def from_dict(self, data: dict[str, Any]) -> MyTargetingSettings:
        return MyTargetingSettings.from_dict(data)
