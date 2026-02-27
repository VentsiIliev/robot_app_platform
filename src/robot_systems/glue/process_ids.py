from enum import Enum


class ProcessID(str, Enum):
    GLUE            = "glue"
    PICK_AND_PLACE  = "pick_and_place"
    CLEAN           = "clean"