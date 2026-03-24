from enum import Enum


class CommonSettingsID(str, Enum):
    ROBOT_CONFIG = "robot_config"
    MOVEMENT_GROUPS = "movement_groups"
    ROBOT_CALIBRATION = "robot_calibration"
    MODBUS_CONFIG = "modbus_config"
    VISION_CAMERA_SETTINGS = "vision_camera_settings"
    TARGETING = "targeting"
    WORK_AREA_SETTINGS = "work_area_settings"
    TOOL_CHANGER_CONFIG = "tool_changer_config"
    HEIGHT_MEASURING_SETTINGS = "height_measuring_settings"
    HEIGHT_MEASURING_CALIBRATION = "height_measuring_calibration"
    DEPTH_MAP_DATA = "depth_map_data"

    def __str__(self) -> str:
        return self.value

    def __format__(self, spec: str) -> str:
        return self.value.__format__(spec)
