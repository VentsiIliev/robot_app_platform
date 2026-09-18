from abc import ABC, abstractmethod
from typing import Optional, Tuple, List
from src.engine.robot.interfaces.tool_definition import ToolDefinition


class IToolService(ABC):

    @property
    def current_tool(self) -> Optional[int]:
        """Generic name for the attached tool; current_gripper remains compatible."""
        return self.current_gripper

    @property
    @abstractmethod
    def current_gripper(self) -> Optional[int]: ...

    @abstractmethod
    def pickup_gripper(self, gripper_id: int) -> Tuple[bool, Optional[str]]: ...

    @abstractmethod
    def drop_off_gripper(self, gripper_id: int) -> Tuple[bool, Optional[str]]: ...

    @abstractmethod
    def get_tools(self) -> List[ToolDefinition]: ...

    def pickup_tool(self, tool_id: int) -> Tuple[bool, Optional[str]]:
        return self.pickup_gripper(tool_id)

    def drop_off_tool(self, tool_id: int) -> Tuple[bool, Optional[str]]:
        return self.drop_off_gripper(tool_id)
