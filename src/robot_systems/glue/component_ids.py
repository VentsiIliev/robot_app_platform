from enum import Enum


class ServiceID(str, Enum):
    WEIGHT = "weight"
    MOTOR = "motor"
    HEIGHT_MEASURING = "height_measuring"
    VACUUM_PUMP = "vacuum_pump"


class SettingsID(str, Enum):
    GLUE_SETTINGS = "glue_settings"
    GLUE_CELLS = "glue_cells"
    DISPENSE_CHANNELS = "dispense_channels"
    GLUE_CATALOG = "glue_catalog"
    GLUE_MOTOR_CONFIG = "glue_motor_config"

    def __str__(self) -> str:
        return self.value

    def __format__(self, spec: str) -> str:
        return self.value.__format__(spec)


class ProcessID(str, Enum):
    GLUE = "glue"
    PICK_AND_PLACE = "pick_and_place"
    CLEAN = "clean"
    ROBOT_CALIBRATION = "robot_calibration"
    COORDINATOR = "coordinator"
