from enum import Enum


class SettingsID(str, Enum):
    GLUE_SETTINGS     = "glue_settings"
    GLUE_TARGETING    = "glue_targeting"
    GLUE_CELLS        = "glue_cells"
    GLUE_CATALOG      = "glue_catalog"
    GLUE_MOTOR_CONFIG            = "glue_motor_config"

    def __str__(self) -> str:
        return self.value

    def __format__(self, spec: str) -> str:
        return self.value.__format__(spec)
