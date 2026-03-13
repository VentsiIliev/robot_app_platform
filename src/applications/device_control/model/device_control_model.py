import logging
from typing import Dict, List

from src.applications.base.i_application_model import IApplicationModel
from src.applications.device_control.service.i_device_control_service import (
    IDeviceControlService, MotorEntry,
)


class DeviceControlModel(IApplicationModel):

    def __init__(self, service: IDeviceControlService) -> None:
        self._service = service
        self._logger  = logging.getLogger(self.__class__.__name__)

    def load(self) -> None:
        pass

    def save(self, *args, **kwargs) -> None:
        pass

    # ── Queries ───────────────────────────────────────────────────────

    def get_motors(self) -> List[MotorEntry]:
        return self._service.get_motors()

    def get_motor_health_snapshot(self) -> Dict[int, bool]:
        return self._service.get_motor_health_snapshot()

    def is_laser_available(self) -> bool:
        return self._service.is_laser_available()

    def is_vacuum_pump_available(self) -> bool:
        return self._service.is_vacuum_pump_available()

    def is_motor_available(self) -> bool:
        return self._service.is_motor_available()

    def is_generator_available(self) -> bool:
        return self._service.is_generator_available()

    # ── Commands ──────────────────────────────────────────────────────

    def laser_on(self) -> None:
        self._service.laser_on()

    def laser_off(self) -> None:
        self._service.laser_off()

    def vacuum_pump_on(self) -> bool:
        return self._service.vacuum_pump_on()

    def vacuum_pump_off(self) -> bool:
        return self._service.vacuum_pump_off()

    def motor_on(self, address: int) -> bool:
        return self._service.motor_on(address)

    def motor_off(self, address: int) -> bool:
        return self._service.motor_off(address)

    def generator_on(self) -> bool:
        return self._service.generator_on()

    def generator_off(self) -> bool:
        return self._service.generator_off()
