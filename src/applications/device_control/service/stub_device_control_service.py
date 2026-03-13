from typing import Dict, List

from src.applications.device_control.service.i_device_control_service import (
    IDeviceControlService, MotorEntry,
)

_STUB_MOTORS = [
    MotorEntry(name="Stub Motor 1", address=0),
    MotorEntry(name="Stub Motor 2", address=2),
]


class StubDeviceControlService(IDeviceControlService):

    def get_motors(self) -> List[MotorEntry]:
        return list(_STUB_MOTORS)

    def get_motor_health_snapshot(self) -> Dict[int, bool]:
        return {m.address: True for m in _STUB_MOTORS}

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

    def motor_on(self, address: int) -> bool:
        print(f"[DeviceControl] motor_on  address={address}")
        return True

    def motor_off(self, address: int) -> bool:
        print(f"[DeviceControl] motor_off address={address}")
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
