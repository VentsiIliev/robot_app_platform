from src.applications.device_control.service.i_device_control_service import IDeviceControlService


class StubDeviceControlService(IDeviceControlService):

    def laser_on(self) -> None:
        print("[DeviceControl] laser_on")

    def laser_off(self) -> None:
        print("[DeviceControl] laser_off")

    def vacuum_pump_on(self) -> bool:
        print("[DeviceControl] vacuum_pump_on")
        return True

    def vacuum_pump_off(self) -> bool:
        print("[DeviceControl] vacuum_pump_off")
        return True

    def motor_on(self) -> bool:
        print("[DeviceControl] motor_on")
        return True

    def motor_off(self) -> bool:
        print("[DeviceControl] motor_off")
        return True

    def generator_on(self) -> bool:
        print("[DeviceControl] generator_on")
        return True

    def generator_off(self) -> bool:
        print("[DeviceControl] generator_off")
        return True

    def is_laser_available(self) -> bool:
        return True

    def is_vacuum_pump_available(self) -> bool:
        return True

    def is_motor_available(self) -> bool:
        return True

    def is_generator_available(self) -> bool:
        return True

