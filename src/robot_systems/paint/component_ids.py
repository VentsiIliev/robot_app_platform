from enum import Enum


class ServiceID(str, Enum):
    CUSTOM_DEVICE = "custom_device"
    VACUUM_PUMP = "vacuum_pump"


class SettingsID(str, Enum):
    PAINT_PROCESS_CONFIG = "paint_process_config"
    DRYER_CONFIG = "dryer_config"


class ProcessID(str, Enum):
    MAIN_PROCESS = "main_process"
    ROBOT_CALIBRATION = "robot_calibration"
