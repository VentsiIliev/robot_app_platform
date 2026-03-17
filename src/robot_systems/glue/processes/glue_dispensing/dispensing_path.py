from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypeAlias

from src.robot_systems.glue.processes.glue_dispensing.dispensing_settings import (
    DispensingSegmentSettings,
)

DispensingPoint: TypeAlias = list[float]
DispensingPathPoints: TypeAlias = list[DispensingPoint]
DispensingSettings: TypeAlias = DispensingSegmentSettings


@dataclass(slots=True)
class DispensingPathEntry:
    points: DispensingPathPoints
    settings: DispensingSettings
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw_entry) -> "DispensingPathEntry":
        if isinstance(raw_entry, cls):
            return raw_entry

        if not isinstance(raw_entry, tuple):
            raise TypeError(f"Unsupported dispensing path entry: {type(raw_entry)!r}")

        if len(raw_entry) == 2:
            points, settings = raw_entry
            metadata = {}
        elif len(raw_entry) == 3:
            points, settings, pattern_type = raw_entry
            metadata = {"pattern_type": pattern_type}
        else:
            raise ValueError(f"Unsupported dispensing path tuple length: {len(raw_entry)}")

        return cls(
            points=list(points),
            settings=DispensingSegmentSettings.from_raw(settings),
            metadata=metadata,
        )

    def is_empty(self) -> bool:
        return len(self.points) == 0

    def sliced_from(self, point_index: int) -> DispensingPathPoints:
        return self.points[point_index:]


def normalize_dispensing_paths(raw_paths: list[Any]) -> list[DispensingPathEntry]:
    return [DispensingPathEntry.from_raw(entry) for entry in raw_paths]
