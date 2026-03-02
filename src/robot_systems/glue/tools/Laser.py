"""
Class not in use as moved to depth camera.
"""
from modules.modbusCommunication import ModbusController
from modules.modbusCommunication.ModbusClient import ModbusClient
import platform
from modules.shared.utils import linuxUtils
from modules.SensorPublisher import SENSOR_STATE_ERROR
from modules.modbusCommunication.ModbusClientSingleton import ModbusClientSingleton


class Laser:
    """
    A class to control a laser device via Modbus communication.

    This class allows for controlling a laser by turning it on or off through Modbus commands. It also
    handles platform-dependent configuration for the communication port, automatically detecting
    the appropriate serial port on Linux systems.

    Attributes:
        slave (int): The Modbus slave address for the laser device.
        port (str): The serial port used for communication with the laser device (e.g., COM5 for Windows or dynamically detected on Linux).
        modbusClient (ModbusClient): The instance of the Modbus client used for communication with the laser device.
    """
    def __init__(self):
        """
               Initializes the Laser object by setting up the Modbus slave address, detecting the communication port,
               and initializing the Modbus client.

               The port is detected based on the operating system. If the system is Windows, a predefined port (COM5) is used.
               If the system is Linux, the appropriate port is detected using the `find_ch341_uart_port` method.

               Raises:
                   Exception: If the communication port cannot be detected or the Modbus client cannot be initialized, an exception is raised.
               """
        self.slave = 1
        self._create_modbus_client()
        # self.modbusClient = ModbusClient(self.slave, self.port, 115200, 8, 1, 0.05)

    def _create_modbus_client(self):
        try:
            # Reset singleton instance to force new connection on reconnect
            self.modbusClient = ModbusController.getModbusClient(self.slave)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.state = SENSOR_STATE_ERROR
            # raise Exception(f"Failed to create Modbus client: {e}")

    def turnOn(self):
        """
                Turns on the laser by sending a Modbus write command to the laser device.

                This method writes a value of 1 to register 16, signaling the laser to turn on.

                Raises:
                    Exception: If the Modbus command fails, an exception is raised.
                """
        self.modbusClient.writeRegister(14, 1)

    def turnOff(self):
        """
               Turns off the laser by sending a Modbus write command to the laser device.

               This method writes a value of 0 to register 16, signaling the laser to turn off.

               Raises:
                   Exception: If the Modbus command fails, an exception is raised.
               """
        self.modbusClient.writeRegister(14, 0)

if __name__ == "__main__":
    laser = Laser()
    laser.turnOn()
    # time.sleep(1)
    # laser.turnOff()