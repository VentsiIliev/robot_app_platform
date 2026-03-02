from modules.shared.tools.glue_monitor_system.services.legacy_fetcher import GlueDataFetcher
from modules.shared.tools.glue_monitor_system.core.meter import GlueMeter


class GlueCell:
    """
    Represents a glue cell in the dispensing application.

    Attributes:
        id (int): The unique identifier for the glue cell.
        glueType (str): The type of glue used in the cell (e.g., "Type A", "Custom Glue X").
        glueMeter (GlueMeter): The glue meter associated with the cell for measuring glue weight.
        capacity (int): The maximum capacity of the glue cell.
        motor_address (int): The Modbus address of the motor that drives this cell's pump.

    Methods:
        setId(id): Sets the unique identifier for the glue cell.
        setGlueType(glueType): Sets the type of glue used in the cell.
        setGlueMeter(glueMeter): Sets the glue meter for the cell.
        setCapacity(capacity): Sets the maximum capacity of the glue cell.
        setMotorAddress(motor_address): Sets the motor address for the cell.
        getMotorAddress(): Gets the motor address of the cell.
        getGlueInfo(): Retrieves the current glue weight and percentage of capacity used.
    """

    def __init__(self, id, glueType: str, glueMeter, capacity, motor_address: int = 0):
        """
        Initializes a GlueCell instance.

        Args:
            id (int): The unique identifier for the glue cell.
            glueType (str): The type of glue (e.g., "Type A", "Custom Glue X").
            glueMeter (GlueMeter): The glue meter associated with the cell.
            capacity (int): The maximum capacity of the glue cell.
            motor_address (int): The Modbus address of the motor that drives this cell's pump.

        Raises:
            TypeError: If glueMeter is not an instance of GlueMeter.
            ValueError: If capacity is less than or equal to 0.
        """
        self.logTag = "GlueCell"
        self.setId(id)
        self.setGlueType(glueType)
        self.setGlueMeter(glueMeter)
        self.setCapacity(capacity)
        self.setMotorAddress(motor_address)

    def setId(self, id):
        """
        Sets the unique identifier for the glue cell.

        Args:
            id (int): The unique identifier for the glue cell.
        """
        self.id = id

    def setGlueType(self, glueType: str):
        """
        Sets the type of glue used in the cell.

        Args:
            glueType (str): The type of glue (e.g., "Type A", "Custom Glue X").
        """
        # Still use migration function for backward compatibility (handles enum if passed)
        self.glueType =glueType

    def setGlueMeter(self, glueMeter):
        """
        Sets the glue meter for the cell.

        Args:
            glueMeter (GlueMeter): The glue meter associated with the cell.

        Raises:
            TypeError: If glueMeter is not an instance of GlueMeter.
        """

        if not isinstance(glueMeter, GlueMeter):
            raise TypeError(f"[DEBUG] [{self.logTag}] glueMeter must be an instance of GlueMeter class, got {type(glueMeter)}")
        self.glueMeter = glueMeter

    def setCapacity(self, capacity):
        """
        Sets the maximum capacity of the glue cell.

        Args:
            capacity (int): The maximum capacity of the glue cell.

        Raises:
            ValueError: If capacity is less than or equal to 0.
        """
        if capacity <= 0:
            raise ValueError(f"DEbug] [{self.logTag}] capacity must be greater than 0, got {capacity}")
        self.capacity = capacity

    def setMotorAddress(self, motor_address: int):
        """
        Sets the motor address for the cell.

        Args:
            motor_address (int): The Modbus address of the motor that drives this cell's pump.
        """
        self.motor_address = motor_address

    def getMotorAddress(self) -> int:
        """
        Gets the motor address of the cell.

        Returns:
            int: The Modbus address of the motor that drives this cell's pump.
        """
        return self.motor_address

    def getGlueInfo(self):
        """
        Retrieves the current glue weight and percentage of capacity used.

        Returns:
            list: A list containing the current glue weight and percentage of capacity used.
        """
        weight = self.glueMeter.fetchData()
        if weight < 0:
            weight = 0
        percent = int((weight / self.capacity) * 100)
        return [weight, percent]

    def __str__(self):
        """
        Returns a string representation of the GlueCell instance.

        Returns:
            str: A string representation of the GlueCell instance.
        """
        return f"GlueCell(id={self.id}, glueType={self.glueType}, glueMeter={self.glueMeter}, capacity={self.capacity}, motor_address={self.motor_address})"


"""     EXAMPLE USAGE   """
if __name__ == "__main__":
    # try:
    #     print("Meter 1: ",GlueCellsManagerSingleton.get_instance().pollGlueDataById(1))
    #     # print("Meter 2: ",GlueCellsManagerSingleton.get_instance().pollGlueDataById(2))
    #     # print("Meter 3: ",GlueCellsManagerSingleton.get_instance().pollGlueDataById(3))
    # except Exception as e:
    #     print(f"Error: {e}")

    fetcher= GlueDataFetcher()
    fetcher.start()
    import time
    while True:
        time.sleep(1)  # Add a delay to allow the fetcher thread to run
        print("running")

