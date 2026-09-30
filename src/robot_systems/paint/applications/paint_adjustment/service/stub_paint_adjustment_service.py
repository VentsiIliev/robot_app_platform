from .i_paint_adjustment_service import IPaintAdjustmentService, PaintHeadCommandResult, PaintHeadDialConfig, PaintAdjustmentOptions


class StubPaintAdjustmentService(IPaintAdjustmentService):
    def __init__(self) -> None:
        self._position = 121
        self._cycle_state = "idle"

    def get_camera_role(self) -> str:
        return "auxiliary"

    def get_preset_count(self) -> int:
        return 6

    def is_paint_head_available(self) -> bool:
        return True

    def get_dial_config(self) -> PaintHeadDialConfig:
        return PaintHeadDialConfig(45, 38, 6, True)

    def read_current_position(self) -> int:
        return self._position

    def start_single_paint_cycle(self) -> bool:
        if self._cycle_state != "idle":
            return False
        self._cycle_state = "running"
        return True

    def get_paint_cycle_state(self) -> str:
        return self._cycle_state

    def get_adjustment_options(self) -> PaintAdjustmentOptions:
        return PaintAdjustmentOptions(10.0, 30.0, -30.0)

    def start_adjustment_cycle(self, options: PaintAdjustmentOptions) -> bool:
        self._cycle_state = "running"
        return True

    def paint_next_section(self, options: PaintAdjustmentOptions) -> bool:
        return self._cycle_state == "running"

    def finish_adjustment_cycle(self) -> bool:
        self._cycle_state = "stopped"
        return True

    def get_adjustment_status(self) -> tuple[str, float, float]:
        return ("inspect", 10.0, 10.0) if self._cycle_state == "running" else ("idle", 0.0, 0.0)

    def adjust_paint(self, direction: str, degrees: int) -> PaintHeadCommandResult:
        if direction not in {"more", "less"} or isinstance(degrees, bool) or not isinstance(degrees, int) or degrees < 1:
            raise ValueError("Invalid paint adjustment request")
        delta = round(degrees * 94 / 90)
        target = self._position + (delta if direction == "more" else -delta)
        if not 45 <= target <= 235:
            raise ValueError("Paint-head target is outside the calibrated range")
        self._position = target
        return PaintHeadCommandResult(target, 2, wrote=True, relative=True)

    def go_to_setting(self, setting: int) -> PaintHeadCommandResult:
        if isinstance(setting, bool) or not isinstance(setting, int) or not 1 <= setting <= 6:
            raise ValueError("Paint-head setting must be 1..6")
        self._position = 45 + 38 * (6 - setting)
        return PaintHeadCommandResult(self._position, 2, wrote=True, relative=False)
