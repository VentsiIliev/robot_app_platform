from abc import ABC, abstractmethod
from typing import Optional, Tuple, List
from src.engine.robot.interfaces.tool_definition import ToolDefinition


class IToolService(ABC):

    @property
    @abstractmethod
    def current_gripper(self) -> Optional[int]: ...

    @abstractmethod
    def pickup_gripper(self, gripper_id: int) -> Tuple[bool, Optional[str]]: ...

    @abstractmethod
    def drop_off_gripper(self, gripper_id: int) -> Tuple[bool, Optional[str]]: ...

    @abstractmethod
    def get_tools(self) -> List[ToolDefinition]: ...
