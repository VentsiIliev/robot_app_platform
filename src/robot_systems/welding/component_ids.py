from enum import Enum


class ServiceID(str, Enum):
    CUSTOM_DEVICE = "custom_device"


class SettingsID(str, Enum):
    pass


class ProcessID(str, Enum):
    MAIN_PROCESS = "main_process"
    ROBOT_CALIBRATION = "robot_calibration"

