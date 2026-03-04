
from abc import ABC, abstractmethod
from typing import List, Tuple
from src.engine.robot.interfaces.tool_definition import ToolDefinition
from src.engine.robot.tool_changer import SlotConfig


class IToolSettingsService(ABC):

    @abstractmethod
    def get_tools(self) -> List[ToolDefinition]: ...

    @abstractmethod
    def add_tool(self, tool_id: int, name: str) -> Tuple[bool, str]: ...

    @abstractmethod
    def update_tool(self, tool_id: int, name: str) -> Tuple[bool, str]: ...

    @abstractmethod
    def remove_tool(self, tool_id: int) -> Tuple[bool, str]: ...

    @abstractmethod
    def get_slots(self) -> List[SlotConfig]: ...

    @abstractmethod
    def update_slot(self, slot_id: int, tool_id: int) -> Tuple[bool, str]: ...

    @abstractmethod
    def add_slot(self, slot_id: int, tool_id: int) -> Tuple[bool, str]: ...

    @abstractmethod
    def remove_slot(self, slot_id: int) -> Tuple[bool, str]: ...
