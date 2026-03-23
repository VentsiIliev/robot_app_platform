from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.engine.repositories.interfaces import ISettingsSerializer
from src.robot_systems.glue.targeting.frame_names import CALIBRATION_FRAME, PICKUP_FRAME
from src.robot_systems.glue.targeting.point_names import CAMERA_POINT, GRIPPER_POINT, POINT_ALIASES, TOOL_POINT


@dataclass
class GlueTargetPoint:
    name: str
    display_name: str = ""
    x_mm: float = 0.0
    y_mm: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlueTargetPoint":
        return cls(
            name=str(data.get("name", "")).strip().lower(),
            display_name=str(data.get("display_name", "")).strip(),
            x_mm=float(data.get("x_mm", 0.0)),
            y_mm=float(data.get("y_mm", 0.0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
        }


@dataclass
class GlueTargetFrameDefinition:
    name: str
    source_navigation_group: str = ""
    target_navigation_group: str = ""
    use_height_correction: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlueTargetFrameDefinition":
        return cls(
            name=str(data.get("name", "")).strip().lower(),
            source_navigation_group=str(data.get("source_navigation_group", "")).strip(),
            target_navigation_group=str(data.get("target_navigation_group", "")).strip(),
            use_height_correction=bool(data.get("use_height_correction", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "source_navigation_group": self.source_navigation_group,
            "target_navigation_group": self.target_navigation_group,
            "use_height_correction": self.use_height_correction,
        }


@dataclass
class GlueTargetingSettings:
    points: List[GlueTargetPoint] = field(default_factory=list)
    frames: List[GlueTargetFrameDefinition] = field(default_factory=list)
    aliases: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def defaults(cls) -> "GlueTargetingSettings":
        return cls(
            points=[
                GlueTargetPoint(name=CAMERA_POINT, display_name="camera", x_mm=0.0, y_mm=0.0),
                GlueTargetPoint(name=TOOL_POINT, display_name="tool", x_mm=0.0, y_mm=0.0),
                GlueTargetPoint(name=GRIPPER_POINT, display_name="gripper", x_mm=0.0, y_mm=0.0),
            ],
            frames=[
                GlueTargetFrameDefinition(
                    name=CALIBRATION_FRAME,
                    source_navigation_group="",
                    target_navigation_group="",
                    use_height_correction=True,
                ),
                GlueTargetFrameDefinition(
                    name=PICKUP_FRAME,
                    source_navigation_group="CALIBRATION",
                    target_navigation_group="HOME",
                    use_height_correction=False,
                ),
            ],
            aliases=dict(POINT_ALIASES),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlueTargetingSettings":
        points_data = data.get("POINTS")
        frames_data = data.get("FRAMES")
        aliases_data = data.get("ALIASES")
        defaults = cls.defaults()

        if isinstance(points_data, list):
            points = [GlueTargetPoint.from_dict(item) for item in points_data if isinstance(item, dict)]
        else:
            points = [
                GlueTargetPoint(name=CAMERA_POINT, display_name="camera", x_mm=float(data.get("CAMERA_CENTER_X", 0.0)), y_mm=float(data.get("CAMERA_CENTER_Y", 0.0))),
                GlueTargetPoint(name=TOOL_POINT, display_name="tool", x_mm=float(data.get("TOOL_POINT_X", 0.0)), y_mm=float(data.get("TOOL_POINT_Y", 0.0))),
                GlueTargetPoint(name=GRIPPER_POINT, display_name="gripper", x_mm=float(data.get("GRIPPER_POINT_X", 0.0)), y_mm=float(data.get("GRIPPER_POINT_Y", 0.0))),
            ]

        if isinstance(frames_data, list):
            frames = [GlueTargetFrameDefinition.from_dict(item) for item in frames_data if isinstance(item, dict)]
        else:
            frames = defaults.frames

        aliases: Dict[str, str] = dict(defaults.aliases)
        if isinstance(aliases_data, dict):
            aliases.update({
                str(alias).strip().lower(): str(target).strip().lower()
                for alias, target in aliases_data.items()
                if str(alias).strip()
            })

        settings = cls(points=points, frames=frames, aliases=aliases)
        settings.ensure_defaults()
        return settings

    def to_dict(self) -> Dict[str, Any]:
        cloned = GlueTargetingSettings(
            points=list(self.points),
            frames=list(self.frames),
            aliases=dict(self.aliases),
        )
        cloned.ensure_defaults()
        return {
            "POINTS": [point.to_dict() for point in cloned.points],
            "FRAMES": [frame.to_dict() for frame in cloned.frames],
            "ALIASES": dict(sorted(cloned.aliases.items())),
        }

    def ensure_defaults(self) -> None:
        self.points = _dedupe_points(self.points)
        self.frames = _dedupe_frames(self.frames)
        self.aliases = {
            str(alias).strip().lower(): str(target).strip().lower()
            for alias, target in self.aliases.items()
            if str(alias).strip()
        }
        for alias, target in POINT_ALIASES.items():
            self.aliases.setdefault(alias, target)
        if not any(point.name == CAMERA_POINT for point in self.points):
            self.points.insert(0, GlueTargetPoint(name=CAMERA_POINT, display_name="camera", x_mm=0.0, y_mm=0.0))
        for default_point in self.defaults().points:
            if not any(point.name == default_point.name for point in self.points):
                self.points.append(default_point)
        for default_frame in self.defaults().frames:
            if not any(frame.name == default_frame.name for frame in self.frames):
                self.frames.append(default_frame)


def _dedupe_points(points: List[GlueTargetPoint]) -> List[GlueTargetPoint]:
    result: List[GlueTargetPoint] = []
    seen: set[str] = set()
    for point in points:
        name = str(point.name).strip().lower()
        if not name or name in seen:
            continue
        result.append(
            GlueTargetPoint(
                name=name,
                display_name=str(point.display_name).strip() or name,
                x_mm=float(point.x_mm),
                y_mm=float(point.y_mm),
            )
        )
        seen.add(name)
    return result


def _dedupe_frames(frames: List[GlueTargetFrameDefinition]) -> List[GlueTargetFrameDefinition]:
    result: List[GlueTargetFrameDefinition] = []
    seen: set[str] = set()
    for frame in frames:
        name = str(frame.name).strip().lower()
        if not name or name in seen:
            continue
        result.append(
            GlueTargetFrameDefinition(
                name=name,
                source_navigation_group=str(frame.source_navigation_group).strip(),
                target_navigation_group=str(frame.target_navigation_group).strip(),
                use_height_correction=bool(frame.use_height_correction),
            )
        )
        seen.add(name)
    return result


class GlueTargetingSettingsSerializer(ISettingsSerializer[GlueTargetingSettings]):
    @property
    def settings_type(self) -> str:
        return "glue_targeting"

    def get_default(self) -> GlueTargetingSettings:
        return GlueTargetingSettings.defaults()

    def to_dict(self, settings: GlueTargetingSettings) -> Dict[str, Any]:
        return settings.to_dict()

    def from_dict(self, data: Dict[str, Any]) -> GlueTargetingSettings:
        return GlueTargetingSettings.from_dict(data)
