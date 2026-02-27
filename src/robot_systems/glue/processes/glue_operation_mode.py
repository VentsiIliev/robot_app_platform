from enum import Enum


class GlueOperationMode(Enum):
    SPRAY_ONLY    = "spray_only"
    PICK_AND_SPRAY = "pick_and_spray"

    @staticmethod
    def from_label(label: str) -> "GlueOperationMode":
        _MAP = {
            "Spray Only":    GlueOperationMode.SPRAY_ONLY,
            "Pick And Spray": GlueOperationMode.PICK_AND_SPRAY,
        }
        return _MAP.get(label)