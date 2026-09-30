from src.applications.base.i_application_model import IApplicationModel
from ..service.i_paint_adjustment_service import (
    IPaintAdjustmentService, PaintHeadCommandResult, PaintHeadDialConfig, PaintAdjustmentOptions,
)


class PaintAdjustmentModel(IApplicationModel):
    def __init__(self, service: IPaintAdjustmentService) -> None:
        self._service = service

    def load(self) -> str:
        return self._service.get_camera_role()

    def is_paint_head_available(self) -> bool:
        return self._service.is_paint_head_available()

    def get_preset_count(self) -> int:
        return self._service.get_preset_count()

    def get_dial_config(self) -> PaintHeadDialConfig:
        return self._service.get_dial_config()

    def read_current_position(self) -> int | None:
        return self._service.read_current_position()

    def start_single_paint_cycle(self) -> bool:
        return self._service.start_single_paint_cycle()

    def get_paint_cycle_state(self) -> str:
        return self._service.get_paint_cycle_state()

    def get_adjustment_options(self) -> PaintAdjustmentOptions:
        return self._service.get_adjustment_options()

    def start_adjustment_cycle(self, options: PaintAdjustmentOptions) -> bool:
        return self._service.start_adjustment_cycle(options)

    def paint_next_section(self, options: PaintAdjustmentOptions) -> bool:
        return self._service.paint_next_section(options)

    def finish_adjustment_cycle(self) -> bool:
        return self._service.finish_adjustment_cycle()

    def get_adjustment_status(self) -> tuple[str, float, float]:
        return self._service.get_adjustment_status()

    def adjust_paint(self, direction: str, degrees: int) -> int:
        if direction not in {"more", "less"}:
            raise ValueError("Invalid paint adjustment direction")
        if isinstance(degrees, bool) or not isinstance(degrees, int) or degrees < 1:
            raise ValueError("Paint adjustment degrees must be an integer >= 1")
        return self._service.adjust_paint(direction, degrees)

    def adjust_paint_by_register_units(self, direction: str, units: int) -> PaintHeadCommandResult:
        return self._service.adjust_paint_by_register_units(direction, units)

    def go_to_setting(self, setting: int) -> PaintHeadCommandResult:
        if isinstance(setting, bool) or not isinstance(setting, int) or setting < 1:
            raise ValueError("Paint-head setting must be a positive integer")
        return self._service.go_to_setting(setting)

    def go_to_position(self, position: int) -> PaintHeadCommandResult:
        return self._service.go_to_position(position)

    def save(self, *args, **kwargs) -> None:
        """There is no persisted preview state."""
