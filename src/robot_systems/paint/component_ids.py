from enum import Enum


class ServiceID(str, Enum):
    CUSTOM_DEVICE = "custom_device"
    VACUUM_PUMP = "vacuum_pump"
    FAN = "fan"
    PHYSICAL_CONTROL_BUTTONS = "physical_control_buttons"
    DRYER = "dryer"


class SettingsID(str, Enum):
    PAINT_PROCESS_CONFIG = "paint_process_config"
    DRYER_CONFIG = "dryer_config"
    PERIPHERALS = "peripherals"


class ProcessID(str, Enum):
    MAIN_PROCESS = "main_process"
    ROBOT_CALIBRATION = "robot_calibration"
