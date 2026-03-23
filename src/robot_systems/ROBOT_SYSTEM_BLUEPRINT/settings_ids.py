from enum import Enum


class SettingsID(str, Enum):
    # TODO: Keep only robot-system-specific setting ids here.
    MY_TARGETING = "my_targeting"

    def __str__(self) -> str:
        return self.value
