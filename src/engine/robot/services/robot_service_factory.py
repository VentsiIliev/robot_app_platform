from typing import Optional

from src.engine.core.i_messaging_service import IMessagingService
from src.engine.robot.features.tool_service import RobotToolService
from src.engine.robot.interfaces.i_robot import IRobot
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.robot.interfaces.i_tool_service import IToolService
from src.engine.robot.safety.safety_checker import SafetyChecker
from src.engine.robot.services.motion_service import MotionService
from src.engine.robot.services.robot_service import RobotService
from src.engine.robot.services.robot_state_manager import RobotStateManager
from src.engine.robot.services.robot_state_publisher import RobotStatePublisher


def create_robot_service(
    robot: IRobot,
    messaging_service: IMessagingService,          # ← required, no default
    settings_service=None,
    tool_changer=None,
) -> IRobotService:
    safety    = SafetyChecker(settings_service)
    motion    = MotionService(robot, safety)
    publisher = RobotStatePublisher(messaging_service)   # ← no fallback
    state     = RobotStateManager(robot, publisher=publisher)
    state.start_monitoring()

    tool_service: Optional[IToolService] = None
    if tool_changer is not None and settings_service is not None:
        tool_service = RobotToolService(
            motion_service=motion,
            robot_config=settings_service.get_robot_config(),
            tool_changer=tool_changer,
        )

    return RobotService(motion=motion, robot=robot, state_provider=state, tool_service=tool_service)
