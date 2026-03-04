from abc import ABC, abstractmethod
from typing import Optional, List
from src.engine.robot.interfaces.tool_definition import ToolDefinition


class IToolChanger(ABC):

    @abstractmethod
    def get_slot_id_by_tool_id(self, tool_id: int) -> Optional[int]: ...

    @abstractmethod
    def is_slot_occupied(self, slot_id: int) -> bool: ...

    @abstractmethod
    def set_slot_available(self, slot_id: int) -> None: ...

    @abstractmethod
    def set_slot_not_available(self, slot_id: int) -> None: ...

    @abstractmethod
    def list_tools(self) -> List[ToolDefinition]: ...
