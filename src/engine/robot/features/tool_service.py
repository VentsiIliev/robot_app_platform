from typing import Optional, Tuple

from ..interfaces.i_motion_service import IMotionService
from ..interfaces.i_tool_service import IToolService
from ..tool_manager import ToolManager


class RobotToolService(IToolService):

    def __init__(self, motion_service: IMotionService, robot_config, tool_changer):
        self._manager = ToolManager(
            motion_service=motion_service,
            tool_changer=tool_changer,
            robot_config=robot_config,
        )

    @property
    def current_gripper(self) -> Optional[int]:
        return self._manager.current_gripper

    def pickup_gripper(self, gripper_id: int) -> Tuple[bool, Optional[str]]:
        return self._manager.pickup_gripper(gripper_id)

    def drop_off_gripper(self, gripper_id: int) -> Tuple[bool, Optional[str]]:
        return self._manager.drop_off_gripper(gripper_id)
