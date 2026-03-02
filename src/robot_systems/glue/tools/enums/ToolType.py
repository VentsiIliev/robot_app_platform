class ToolType(Enum):
    """
    Enum representing different types of robot tools.

    Attributes:
        Gripper (str): Represents a gripper tool used for grasping objects.
        Welder (str): Represents a welding tool used for joining materials.
        Screwdriver (str): Represents a screwdriver tool used for fastening screws.
        Cutter (str): Represents a cutting tool used for slicing materials.
    """

    Gripper = "Gripper"
    VacuumPump = "Vacuum Pump"
    Laser = "Laser"


    def __str__(self):
        """Return the string value of the enum."""
        return self.value