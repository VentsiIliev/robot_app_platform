from dataclasses import dataclass, field
from typing import Optional, List
from src.engine.robot.interfaces.i_tool_changer import IToolChanger
from src.engine.robot.interfaces.tool_definition import ToolDefinition


@dataclass
class ToolChangeStep:
    kind: str = "motion"
    label: str = ""
    pose: list[float] = field(default_factory=list)
    motion_type: str = "linear"
    velocity: float = 10.0
    acceleration: float = 10.0
    blend_radius: float = 0.0
    wait_seconds: float = 0.0

    def __post_init__(self) -> None:
        self.kind = str(self.kind or "motion").strip().lower()
        if self.kind not in {"motion", "attach", "detach", "wait", "operator_confirm"}:
            raise ValueError(f"Unsupported tool-change step kind: {self.kind}")
        self.pose = [float(value) for value in self.pose]
        if self.kind == "motion" and len(self.pose) != 6:
            raise ValueError("Motion steps require a six-value pose")

    @classmethod
    def from_dict(cls, data: dict) -> "ToolChangeStep":
        return cls(
            kind=data.get("kind", "motion"),
            label=str(data.get("label", "")),
            pose=list(data.get("pose", []) or []),
            motion_type=str(data.get("motion_type", "linear")),
            velocity=float(data.get("velocity", 10.0)),
            acceleration=float(data.get("acceleration", 10.0)),
            blend_radius=float(data.get("blend_radius", 0.0)),
            wait_seconds=float(data.get("wait_seconds", 0.0)),
        )

    def to_dict(self) -> dict:
        result = {"kind": self.kind, "label": self.label}
        if self.kind == "motion":
            result.update({
                "pose": list(self.pose),
                "motion_type": self.motion_type,
                "velocity": self.velocity,
                "acceleration": self.acceleration,
                "blend_radius": self.blend_radius,
            })
        elif self.kind == "wait":
            result["wait_seconds"] = self.wait_seconds
        return result


@dataclass
class SlotConfig:
    id:       int
    tool_id:  Optional[int]   # None = unassigned
    occupied: bool = False
    label: str = ""
    pickup_sequence: List[ToolChangeStep] = field(default_factory=list)
    dropoff_sequence: List[ToolChangeStep] = field(default_factory=list)


class ToolChanger(IToolChanger):

    def __init__(self, slots: List[SlotConfig], tools: List[ToolDefinition]):
        self._slots: dict[int, SlotConfig]            = {s.id: s for s in slots}
        self._tools: dict[int, ToolDefinition]        = {t.id: t for t in tools}

    def get_slot_id_by_tool_id(self, tool_id: int) -> Optional[int]:
        for slot_id, slot in self._slots.items():
            if slot.tool_id is not None and slot.tool_id == tool_id:
                return slot_id
        return None

    def is_slot_occupied(self, slot_id: int) -> bool:
        return self._slots[slot_id].occupied

    def set_slot_available(self, slot_id: int) -> None:
        self._slots[slot_id].occupied = False

    def set_slot_not_available(self, slot_id: int) -> None:
        self._slots[slot_id].occupied = True

    def get_occupied_slots(self) -> List[int]:
        return [sid for sid, s in self._slots.items() if s.occupied]

    def get_empty_slots(self) -> List[int]:
        return [sid for sid, s in self._slots.items() if not s.occupied]

    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())

    def get_slot(self, slot_id: int) -> SlotConfig | None:
        return self._slots.get(int(slot_id))
