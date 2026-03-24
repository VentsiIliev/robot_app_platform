from enum import Enum


class CommonServiceID(str, Enum):
    ROBOT = "robot"
    NAVIGATION = "navigation"
    WORK_AREAS = "work_areas"
    VISION = "vision"
    TOOLS = "tools"

    def __str__(self) -> str:
        return self.value
