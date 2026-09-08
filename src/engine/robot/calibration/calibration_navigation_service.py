from __future__ import annotations

from typing import Callable, Optional

from src.engine.robot.features.navigation_service import NavigationService


class CalibrationNavigationService:
    """Generic calibration move helper built on the standard NavigationService.

    This adapter standardizes the calibration entry move around a named
    navigation group, which defaults to ``"CALIBRATION"``.

    Robot-system-specific side effects should be injected explicitly via
    ``before_move``. For example, the glue system uses that hook to switch the
    active work area to ``"spray"`` before moving, instead of hiding that
    behavior inside a robot-system navigation facade.
    """

    def __init__(
        self,
        navigation: NavigationService,
        *,
        calibration_group: str = "CALIBRATION",
        calibration_group_getter: Optional[Callable[[], str]] = None,
        before_move: Optional[Callable[[], None]] = None,
        after_move: Optional[Callable[[], None]] = None,
    ) -> None:
        self._navigation = navigation
        self._calibration_group = str(calibration_group)
        self._calibration_group_getter = calibration_group_getter
        self._before_move = before_move
        self._after_move = after_move

    def move_to_calibration_position(self, wait_cancelled=None) -> bool:
        calibration_group = (
            str(self._calibration_group_getter())
            if self._calibration_group_getter is not None
            else self._calibration_group
        )
        if self._before_move is not None:
            self._before_move()
        ok = self._navigation.move_to_group(
            calibration_group,
            wait_cancelled=wait_cancelled,
        )
        if ok and self._after_move is not None:
            self._after_move()
        return ok
