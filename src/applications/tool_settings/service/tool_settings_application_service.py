import logging
from typing import List, Tuple
from src.engine.repositories.interfaces.i_settings_service import ISettingsService

from src.engine.robot.configuration import ToolChangerSettings
from src.engine.robot.interfaces.tool_definition import ToolDefinition
from src.engine.robot.tool_changer import SlotConfig
from src.engine.common_settings_ids import CommonSettingsID
from .i_tool_settings_service import IToolSettingsService

_logger = logging.getLogger(__name__)


class ToolSettingsApplicationService(IToolSettingsService):

    def __init__(self, settings_service: ISettingsService):
        self._settings = settings_service

    def _load(self) -> ToolChangerSettings:
        return self._settings.get(CommonSettingsID.TOOL_CHANGER_CONFIG)

    def _save(self, tc: ToolChangerSettings) -> None:
        self._settings.save(CommonSettingsID.TOOL_CHANGER_CONFIG, tc)

    def get_tools(self) -> List[ToolDefinition]:
        return self._load().tools

    def add_tool(self, tool_id: int, name: str) -> Tuple[bool, str]:
        tc = self._load()
        if any(t.id == tool_id for t in tc.tools):
            return False, f"Tool ID {tool_id} already exists"
        tc.tools.append(ToolDefinition(tool_id, name))
        self._save(tc)
        return True, "Tool added"

    def update_tool(self, tool_id: int, name: str) -> Tuple[bool, str]:
        tc = self._load()
        for t in tc.tools:
            if t.id == tool_id:
                t.name = name
                self._save(tc)
                return True, "Tool updated"
        return False, f"Tool {tool_id} not found"

    def remove_tool(self, tool_id: int) -> Tuple[bool, str]:
        tc = self._load()
        if any(s.tool_id == tool_id for s in tc.slots):
            return False, f"Tool {tool_id} is assigned to a slot — unassign it first"
        before = len(tc.tools)
        tc.tools = [t for t in tc.tools if t.id != tool_id]
        if len(tc.tools) == before:
            return False, f"Tool {tool_id} not found"
        self._save(tc)
        return True, "Tool removed"

    def get_slots(self) -> List[SlotConfig]:
        return self._load().slots

    def update_slot(self, slot_id: int, tool_id) -> Tuple[bool, str]:
        """tool_id=None unassigns the slot."""
        tc = self._load()
        if tool_id is not None and not any(t.id == tool_id for t in tc.tools):
            return False, f"Tool ID {tool_id} does not exist"
        for s in tc.slots:
            if s.id == slot_id:
                s.tool_id = tool_id
                self._save(tc)
                return True, "Slot updated"
        return False, f"Slot {slot_id} not found"

    def add_slot(self, slot_id: int, tool_id) -> Tuple[bool, str]:
        """tool_id=None creates an unassigned slot."""
        tc = self._load()
        if any(s.id == slot_id for s in tc.slots):
            return False, f"Slot ID {slot_id} already exists"
        if tool_id is not None and not any(t.id == tool_id for t in tc.tools):
            return False, f"Tool ID {tool_id} does not exist"
        tc.slots.append(SlotConfig(id=slot_id, tool_id=tool_id))
        self._save(tc)
        return True, "Slot added"

    def remove_slot(self, slot_id: int) -> Tuple[bool, str]:
        tc = self._load()
        before = len(tc.slots)
        tc.slots = [s for s in tc.slots if s.id != slot_id]
        if len(tc.slots) == before:
            return False, f"Slot {slot_id} not found"
        self._save(tc)
        return True, "Slot removed"
