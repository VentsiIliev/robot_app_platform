from dataclasses import dataclass
from typing import Optional
from ..robot.interfaces.i_tool_changer import IToolChanger

@dataclass
class SlotConfig:
    id: int
    tool_id: int            # was: reservedFor: Gripper  →  now plain int
    occupied: bool = False


class ToolChanger(IToolChanger):

    def __init__(self, slots: list[SlotConfig]):
        self._slots: dict[int, SlotConfig] = {s.id: s for s in slots}

    def get_slot_id_by_tool_id(self, tool_id: int) -> Optional[int]:
        for slot_id, slot in self._slots.items():
            if slot.tool_id == tool_id:
                return slot_id
        return None

    def is_slot_occupied(self, slot_id: int) -> bool:
        return self._slots[slot_id].occupied

    def set_slot_available(self, slot_id: int) -> None:
        self._slots[slot_id].occupied = False

    def set_slot_not_available(self, slot_id: int) -> None:
        self._slots[slot_id].occupied = True

    def get_occupied_slots(self) -> list[int]:
        return [sid for sid, s in self._slots.items() if s.occupied]

    def get_empty_slots(self) -> list[int]:
        return [sid for sid, s in self._slots.items() if not s.occupied]