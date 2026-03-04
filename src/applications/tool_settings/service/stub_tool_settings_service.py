import logging
from typing import List, Tuple
from src.engine.robot.interfaces.tool_definition import ToolDefinition
from src.engine.robot.tool_changer import SlotConfig
from .i_tool_settings_service import IToolSettingsService

_logger = logging.getLogger(__name__)


class StubToolSettingsService(IToolSettingsService):

    def __init__(self):
        self._tools = [ToolDefinition(1, "Single Gripper"), ToolDefinition(4, "Double Gripper")]
        self._slots = [SlotConfig(id=10, tool_id=1), SlotConfig(id=11, tool_id=4)]

    def get_tools(self) -> List[ToolDefinition]:
        return list(self._tools)

    def add_tool(self, tool_id: int, name: str) -> Tuple[bool, str]:
        _logger.info("Stub: add_tool id=%s name=%s", tool_id, name)
        self._tools.append(ToolDefinition(tool_id, name))
        return True, "Tool added"

    def update_tool(self, tool_id: int, name: str) -> Tuple[bool, str]:
        _logger.info("Stub: update_tool id=%s name=%s", tool_id, name)
        for t in self._tools:
            if t.id == tool_id:
                t.name = name
                return True, "Tool updated"
        return False, f"Tool {tool_id} not found"

    def remove_tool(self, tool_id: int) -> Tuple[bool, str]:
        _logger.info("Stub: remove_tool id=%s", tool_id)
        before = len(self._tools)
        self._tools = [t for t in self._tools if t.id != tool_id]
        return (True, "Removed") if len(self._tools) < before else (False, "Not found")

    def get_slots(self) -> List[SlotConfig]:
        return list(self._slots)

    def update_slot(self, slot_id: int, tool_id: int) -> Tuple[bool, str]:
        _logger.info("Stub: update_slot slot=%s tool=%s", slot_id, tool_id)
        for s in self._slots:
            if s.id == slot_id:
                s.tool_id = tool_id
                return True, "Slot updated"
        return False, f"Slot {slot_id} not found"

    def add_slot(self, slot_id: int, tool_id: int) -> Tuple[bool, str]:
        _logger.info("Stub: add_slot slot=%s tool=%s", slot_id, tool_id)
        self._slots.append(SlotConfig(id=slot_id, tool_id=tool_id))
        return True, "Slot added"

    def remove_slot(self, slot_id: int) -> Tuple[bool, str]:
        _logger.info("Stub: remove_slot slot=%s", slot_id)
        before = len(self._slots)
        self._slots = [s for s in self._slots if s.id != slot_id]
        return (True, "Removed") if len(self._slots) < before else (False, "Not found")