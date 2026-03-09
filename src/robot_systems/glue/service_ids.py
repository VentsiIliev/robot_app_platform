from enum import Enum


class ServiceID(str, Enum):
    ROBOT      = "robot"
    NAVIGATION = "navigation"
    VISION     = "vision"
    TOOLS      = "tools"
    WEIGHT     = "weight"
    MOTOR      = "motor"
    HEIGHT_MEASURING = "height_measuring"
