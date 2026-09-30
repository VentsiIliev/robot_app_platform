from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.engine.repositories.interfaces import ISettingsSerializer
from src.engine.robot.targeting import RemoteTcpSettings, TargetFrameSettings


@dataclass
class TargetingSettings:
    points: list[RemoteTcpSettings] = field(default_factory=list)
    frames: list[TargetFrameSettings] = field(default_factory=list)
    point_mode: str = "global"
    area_points: dict[str, list[RemoteTcpSettings]] = field(default_factory=dict)

    @classmethod
    def defaults(cls) -> "TargetingSettings":
        return cls()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TargetingSettings":
        points_data = data.get("POINTS")
        frames_data = data.get("FRAMES")
        points = [
            RemoteTcpSettings.from_dict(item)
            for item in points_data
            if isinstance(item, dict)
        ] if isinstance(points_data, list) else []
        frames = [
            TargetFrameSettings.from_dict(item)
            for item in frames_data
            if isinstance(item, dict)
        ] if isinstance(frames_data, list) else []
        area_points = {
            str(area).strip(): [RemoteTcpSettings.from_dict(item) for item in items if isinstance(item, dict)]
            for area, items in (data.get("AREA_POINTS", {}) or {}).items()
            if str(area).strip() and isinstance(items, list)
        }
        settings = cls(
            points=points, frames=frames,
            point_mode=data.get("POINT_MODE", "global"),
            area_points=area_points,
        )
        settings.ensure_defaults()
        return settings

    def to_dict(self) -> dict[str, Any]:
        cloned = TargetingSettings(
            points=list(self.points), frames=list(self.frames),
            point_mode=self.point_mode, area_points=self.area_points,
        )
        cloned.ensure_defaults()
        return {
            "POINTS": [point.to_dict() for point in cloned.points],
            "FRAMES": [frame.to_dict() for frame in cloned.frames],
            "POINT_MODE": cloned.point_mode,
            "AREA_POINTS": {
                area: [point.to_dict() for point in points]
                for area, points in cloned.area_points.items()
            },
        }

    def ensure_defaults(self) -> None:
        self.points = _dedupe_points(self.points)
        self.frames = _dedupe_frames(self.frames)
        self.point_mode = "per_area" if self.point_mode == "per_area" else "global"
        self.area_points = {
            str(area).strip(): _dedupe_points(points)
            for area, points in self.area_points.items() if str(area).strip()
        }

    def points_for_area(self, area_id: str) -> list[RemoteTcpSettings]:
        if self.point_mode != "per_area":
            return self.points
        return self.area_points.get(str(area_id or "").strip(), self.points)


def _dedupe_points(points: list[RemoteTcpSettings]) -> list[RemoteTcpSettings]:
    result: list[RemoteTcpSettings] = []
    seen: set[str] = set()
    for point in points:
        name = str(point.name).strip().lower()
        if not name or name in seen:
            continue
        result.append(
            RemoteTcpSettings(
                name=name,
                display_name=str(point.display_name).strip() or name,
                x_mm=float(point.x_mm),
                y_mm=float(point.y_mm),
            )
        )
        seen.add(name)
    return result


def _dedupe_frames(frames: list[TargetFrameSettings]) -> list[TargetFrameSettings]:
    result: list[TargetFrameSettings] = []
    seen: set[str] = set()
    for frame in frames:
        name = str(frame.name).strip().lower()
        if not name or name in seen:
            continue
        result.append(
            TargetFrameSettings(
                name=name,
                source_navigation_group=str(frame.source_navigation_group).strip(),
                target_navigation_group=str(frame.target_navigation_group).strip(),
                use_height_correction=bool(frame.use_height_correction),
                work_area_id=str(frame.work_area_id).strip(),
            )
        )
        seen.add(name)
    return result


class TargetingSettingsSerializer(ISettingsSerializer[TargetingSettings]):
    @property
    def settings_type(self) -> str:
        return "targeting"

    def get_default(self) -> TargetingSettings:
        return TargetingSettings.defaults()

    def to_dict(self, settings: TargetingSettings) -> dict[str, Any]:
        return settings.to_dict()

    def from_dict(self, data: dict[str, Any]) -> TargetingSettings:
        return TargetingSettings.from_dict(data)
