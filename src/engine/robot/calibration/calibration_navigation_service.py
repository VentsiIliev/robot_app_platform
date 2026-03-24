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
        before_move: Optional[Callable[[], None]] = None,
    ) -> None:
        self._navigation = navigation
        self._calibration_group = str(calibration_group)
        self._before_move = before_move

    def move_to_calibration_position(self, wait_cancelled=None) -> bool:
        if self._before_move is not None:
            try:
                self._before_move()
            except Exception:
                pass
        return self._navigation.move_to_group(
            self._calibration_group,
            wait_cancelled=wait_cancelled,
        )
