from enum import Enum


class GlueWorkpieceField(Enum):
    """
       Enum representing standardized keys for workpieces fields.

       Used for consistency in shared communication and internal data structures.
       """
    WORKPIECE_ID = "workpieceId"
    NAME = "name"
    DESCRIPTION = "description"
    TOOL_ID = "toolId"
    GRIPPER_ID = "gripperId"
    GLUE_TYPE = "glueType"
    PROGRAM = "program"
    MATERIAL = "material"
    CONTOUR = "contour"
    OFFSET = "offset"
    HEIGHT = "height"
    SPRAY_PATTERN = "sprayPattern"
    CONTOUR_AREA = "contourArea"
    NOZZLES = "nozzles"
    GLUE_QTY = "glue_qty"
    SPRAY_WIDTH = "spray_width"
    PICKUP_POINT = "pickup_point"

    def getAsLabel(self):
        """
               Returns a user-friendly label version of the enum name.
               Example: CONTOUR_AREA → "Contour area"
               """
        return self.name.capitalize().replace("_", " ")

    def lower(self):
        """
               Returns the enum value in lowercase.
               Useful for JSON key consistency.
               """
        return self.value.lower()