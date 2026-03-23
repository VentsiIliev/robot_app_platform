from enum import Enum


class ServiceID(str, Enum):
    # TODO: Keep only the service IDs your robot system actually needs.
    ROBOT = "robot"
    NAVIGATION = "navigation"
    VISION = "vision"
    TOOLS = "tools"
