import logging

from src.engine.core.message_broker import MessageBroker
from src.shared_contracts.events.robot_events import RobotTopics

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)

from src.engine.robot.drivers.fairino.fairino_robot import FairinoRobot
from src.engine.robot.drivers.fairino.test_robot import TestRobotWrapper
from src.engine.robot.services.robot_service_factory import create_robot_service
from src.engine.robot.tool_changer import ToolChanger, SlotConfig
from src.engine.robot.enums.axis import RobotAxis, Direction

# ---------------------------------------------------------------------------
# 1. Without tool management  (testing / no gripper hardware)
# ---------------------------------------------------------------------------
service = create_robot_service(robot=TestRobotWrapper())

# Motion
service.move_ptp(
    position=[100.0, 0.0, 300.0, 180.0, 0.0, 0.0],
    tool=0, user=0, velocity=30, acceleration=30,
)
service.move_linear(
    position=[100.0, 50.0, 300.0, 180.0, 0.0, 0.0],
    tool=0, user=0, velocity=20, acceleration=20,
)
service.start_jog(axis=RobotAxis.Z, direction=Direction.PLUS, step=5.0)
service.stop_motion()

# Lifecycle
service.enable_robot()
service.disable_robot()

# State
print(service.get_state())
print(service.get_current_velocity())
print(service.get_current_position())

# ---------------------------------------------------------------------------
# 2. With tool management
#    SlotConfig(id, tool_id) — tool_id is a plain int.
#    If you have an app-level Gripper enum pass Gripper.BELT.value etc.
# ---------------------------------------------------------------------------
tool_changer = ToolChanger(slots=[
    SlotConfig(id=10, tool_id=0),
    SlotConfig(id=11, tool_id=1),
    SlotConfig(id=12, tool_id=2),
])

service_with_tools = create_robot_service(
    robot=FairinoRobot(ip="192.168.1.100"),
    settings_service=None,       # replace with real settings service
    tool_changer=tool_changer,
)

# Guard: tools is None when settings_service was not provided
if service_with_tools.tools:
    ok, err = service_with_tools.tools.pickup_gripper(gripper_id=1)
    print(f"Pickup:   ok={ok}  err={err}")

    ok, err = service_with_tools.tools.drop_off_gripper(gripper_id=1)
    print(f"Drop-off: ok={ok}  err={err}")

    print(f"Current gripper: {service_with_tools.tools.current_gripper}")