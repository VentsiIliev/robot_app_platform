from enum import Enum


class SettingsID(str, Enum):
    ROBOT_CONFIG      = "robot_config"
    ROBOT_CALIBRATION = "robot_calibration"
    GLUE_SETTINGS     = "glue_settings"
    GLUE_CELLS        = "glue_cells"
    GLUE_CATALOG      = "glue_catalog"
    MODBUS_CONFIG     = "modbus_config"
    VISION_CAMERA_SETTINGS = "vision_camera_settings"
    TOOL_CHANGER_CONFIG = "tool_changer_config"

    def __str__(self) -> str:
        return self.value

    def __format__(self, spec: str) -> str:
        return self.value.__format__(spec)