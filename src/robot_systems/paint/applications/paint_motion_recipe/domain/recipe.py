from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


Pose6D = list[float]


@dataclass(frozen=True)
class MotionRecipeStep:
    id: str
    label: str
    action: str
    group_id: str = ""
    pose: Pose6D | None = None
    enabled: bool = True
    note: str = ""

    @staticmethod
    def new(
        *,
        label: str,
        action: str,
        group_id: str = "",
        pose: Pose6D | None = None,
        enabled: bool = True,
        note: str = "",
    ) -> "MotionRecipeStep":
        return MotionRecipeStep(
            id=uuid4().hex,
            label=str(label or "").strip() or str(action or "step"),
            action=str(action or "").strip(),
            group_id=str(group_id or "").strip(),
            pose=_normalize_pose(pose),
            enabled=bool(enabled),
            note=str(note or "").strip(),
        )

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "MotionRecipeStep":
        return MotionRecipeStep(
            id=str(data.get("id") or uuid4().hex),
            label=str(data.get("label") or data.get("action") or "step").strip(),
            action=str(data.get("action") or "").strip(),
            group_id=str(data.get("group_id") or "").strip(),
            pose=_normalize_pose(data.get("pose")),
            enabled=bool(data.get("enabled", True)),
            note=str(data.get("note") or "").strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "action": self.action,
            "group_id": self.group_id,
            "pose": list(self.pose) if self.pose is not None else None,
            "enabled": self.enabled,
            "note": self.note,
        }


@dataclass(frozen=True)
class MotionRecipe:
    name: str = "Paint Development Recipe"
    mock_only: bool = True
    steps: tuple[MotionRecipeStep, ...] = field(default_factory=tuple)

    @staticmethod
    def default() -> "MotionRecipe":
        return MotionRecipe(
            steps=(
                MotionRecipeStep.new(label="Move to Magazine", action="move_group", group_id="Magazine"),
                MotionRecipeStep.new(label="Capture magazine workpiece", action="capture", group_id="Magazine"),
                MotionRecipeStep.new(label="Vacuum pump ON", action="vacuum_on", group_id="Magazine"),
                MotionRecipeStep.new(label="Move to Calibration", action="move_group", group_id="CALIBRATION"),
                MotionRecipeStep.new(label="Capture calibration contour", action="capture", group_id="CALIBRATION"),
                MotionRecipeStep.new(label="Unwind Joint 6", action="unwind"),
                MotionRecipeStep.new(label="Optional cleanup", action="cleanup", enabled=False),
                MotionRecipeStep.new(label="Move to Dropoff", action="move_group", group_id="Dropoff"),
                MotionRecipeStep.new(label="Vacuum pump OFF", action="vacuum_off", group_id="Dropoff"),
            )
        )

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "MotionRecipe":
        steps = tuple(
            MotionRecipeStep.from_dict(item)
            for item in data.get("steps", [])
            if isinstance(item, dict)
        )
        return MotionRecipe(
            name=str(data.get("name") or "Paint Development Recipe").strip(),
            mock_only=bool(data.get("mock_only", True)),
            steps=steps,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mock_only": self.mock_only,
            "steps": [step.to_dict() for step in self.steps],
        }


def _normalize_pose(value) -> Pose6D | None:
    if value is None:
        return None
    try:
        pose = [float(item) for item in list(value)[:6]]
    except (TypeError, ValueError):
        return None
    if len(pose) != 6:
        return None
    return pose
