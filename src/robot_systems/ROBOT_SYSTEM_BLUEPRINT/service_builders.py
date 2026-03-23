from __future__ import annotations

from src.engine.robot.calibration.service_builders import build_robot_system_calibration_service
from src.engine.robot.height_measuring.service_builders import build_robot_system_height_measuring_services
from src.robot_systems.default_service_builders import (
    build_navigation_service,
    build_robot_service,
    build_tool_service,
    build_vision_service,
)


# Shared defaults you can reuse directly in `services = [...]`:
# - build_robot_service
# - build_navigation_service
# - build_tool_service
# - build_vision_service
#
# Shared provider-based builders you normally call from `MyRobotSystem.on_start()`:
# - build_robot_system_calibration_service(robot_system)
# - build_robot_system_height_measuring_services(robot_system)
#
# TODO: Add only robot-system-specific builders here.
# Examples:
# - build_weight_service(ctx)
# - build_motor_service(ctx)
# - build_generator_service(ctx)
