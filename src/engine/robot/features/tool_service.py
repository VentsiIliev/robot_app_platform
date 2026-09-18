from typing import Optional, Tuple, List

from ..interfaces.i_motion_service import IMotionService
from ..interfaces.i_tool_service import IToolService
from ..tool_manager import ToolManager
from ..interfaces.tool_definition import ToolDefinition


class RobotToolService(IToolService):

    def __init__(self, motion_service: IMotionService, robot_config, movement_groups, tool_changer):
        self._manager = ToolManager(
            motion_service=motion_service,
            tool_changer=tool_changer,
            robot_config=robot_config,
            movement_groups=movement_groups,
        )

    @property
    def current_gripper(self) -> Optional[int]:
        return self._manager.current_gripper

    @property
    def current_tool(self) -> Optional[int]:
        return self._manager.current_tool

    def pickup_gripper(self, gripper_id: int) -> Tuple[bool, Optional[str]]:
        return self._manager.pickup_gripper(gripper_id)

    def drop_off_gripper(self, gripper_id: int) -> Tuple[bool, Optional[str]]:
        return self._manager.drop_off_gripper(gripper_id)

    def pickup_tool(self, tool_id: int) -> Tuple[bool, Optional[str]]:
        return self._manager.pickup_tool(tool_id)

    def drop_off_tool(self, tool_id: int) -> Tuple[bool, Optional[str]]:
        return self._manager.drop_off_tool(tool_id)

    def get_tools(self) -> List[ToolDefinition]:
        return self._manager.get_tools()
