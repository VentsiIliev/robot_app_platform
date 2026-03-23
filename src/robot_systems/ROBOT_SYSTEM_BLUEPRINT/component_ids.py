from enum import Enum


class ServiceID(str, Enum):
    # TODO: Keep only robot-system-specific service ids here.
    # Use CommonServiceID for shared infrastructure services such as:
    # - ROBOT
    # - NAVIGATION
    # - VISION
    # - TOOLS
    CUSTOM_DEVICE = "custom_device"


class SettingsID(str, Enum):
    # TODO: Keep only robot-system-specific setting ids here.
    MY_TARGETING = "my_targeting"

    def __str__(self) -> str:
        return self.value


class ProcessID(str, Enum):
    # TODO: Add process ids only if your robot system exposes processes.
    MAIN_PROCESS = "main_process"
