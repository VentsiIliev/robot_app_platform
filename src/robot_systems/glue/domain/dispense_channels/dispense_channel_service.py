from __future__ import annotations

from src.robot_systems.glue.domain.dispense_channels.i_dispense_channel_service import (
    IDispenseChannelService,
)
from src.robot_systems.glue.processes.glue_dispensing.dispensing_settings import (
    DispensingSegmentSettings,
)
from src.robot_systems.glue.processes.glue_dispensing.glue_pump_controller import (
    GluePumpController,
)
from src.robot_systems.glue.processes.glue_dispensing.i_glue_type_resolver import (
    IGlueTypeResolver,
)


class DispenseChannelService(IDispenseChannelService):
    def __init__(
        self,
        pump_controller: GluePumpController,
        glue_type_resolver: IGlueTypeResolver | None,
    ) -> None:
        self._pump_controller = pump_controller
        self._resolver = glue_type_resolver

    def resolve_motor_address(self, glue_type: str | None) -> int:
        normalized = str(glue_type or "").strip()
        if not normalized or self._resolver is None:
            return -1
        return int(self._resolver.resolve(normalized))

    def start_dispense(
        self,
        glue_type: str | None,
        settings: DispensingSegmentSettings | None = None,
    ) -> tuple[bool, int | None]:
        motor_address = self._resolve_valid_address(glue_type)
        if motor_address is None:
            return False, None
        return bool(self._pump_controller.pump_on(motor_address, settings)), motor_address

    def stop_dispense(
        self,
        glue_type: str | None,
        settings: DispensingSegmentSettings | None = None,
    ) -> tuple[bool, int | None]:
        motor_address = self._resolve_valid_address(glue_type)
        if motor_address is None:
            return False, None
        return bool(self._pump_controller.pump_off(motor_address, settings)), motor_address

    def get_last_exception(self) -> Exception | None:
        return self._pump_controller.get_last_exception()

    def _resolve_valid_address(self, glue_type: str | None) -> int | None:
        motor_address = self.resolve_motor_address(glue_type)
        if motor_address == -1:
            return None
        return motor_address
