# from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController
#
# class VacuumPumpController(IVacuumPumpController):
#     ON_VALUE = 1
#     OFF_VALUE = 0
#
#     def __init__(self):
#         """
#                Initializes the VacuumPump with default values.
#
#                The digital output pin used to control the pump is set to 3 by default. The offsets for the tooltip
#                are also initialized (xOffset, yOffset, zOffset) to help place the vacuum pump in the correct position
#                relative to the robotic arm or tool.
#
#                Attributes are initialized as:
#                    xOffset = 0
#                    yOffset = 0
#                    zOffset = 105
#                    digitalOutput = 3
#                    vacuumPump = None
#                """
#         self.digitalOutput = 1
#         self.vacuumPump = None
#
#     def turn_on(self) -> bool:
#         result = robot.setDigitalOutput(self.digitalOutput, self.ON_VALUE)  # Open the control box DO
#
#     def turn_off(self) -> bool:
#         result = robot.setDigitalOutput(self.digitalOutput, self.OFF_VALUE)  # Open the control box DO
#         result = robot.setDigitalOutput(2, 1)
#         time.sleep(0.3)
#         result = robot.setDigitalOutput(2, 0)
#         print("PUMP TURNED OFF")
#
