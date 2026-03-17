from typing import Callable, Optional
from src.engine.robot.features.navigation_service import NavigationService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.vision import IVisionService

class GlueNavigationService:

    _GROUP_HOME        = "HOME"
    _GROUP_LOGIN       = "LOGIN"
    _GROUP_CALIBRATION = "CALIBRATION"

    def __init__(
        self,
        navigation: NavigationService,
        vision: Optional[IVisionService] = None,
        robot_service: Optional[IRobotService] = None,
    ):
        self._nav = navigation
        self._vision = vision
        self._robot = robot_service

    @property
    def _capture_z_offset(self) -> float:
        if self._vision is not None:
            return self._vision.get_capture_pos_offset()
        return 0.0

    def move_home(self) -> bool:
        ok = self._move_with_z_offset(self._GROUP_HOME, self._capture_z_offset)
        if ok:
            self._set_area("pickup")
        return ok

    def move_to_login_position(self) -> bool:
        return self._nav.move_to_group(self._GROUP_LOGIN)

    def move_to_calibration_position(
        self,
        z_offset: float = 0.0,
        wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        ok = self._move_with_z_offset(self._GROUP_CALIBRATION, z_offset, wait_cancelled=wait_cancelled)
        if ok:
            self._set_area("spray")
        return ok

    def move_to(
        self,
        group_name: str,
        z_offset: float = 0.0,
        wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        return (
            self._move_with_z_offset(group_name, z_offset, wait_cancelled=wait_cancelled)
            if z_offset else self._nav.move_to_group(group_name, wait_cancelled=wait_cancelled)
        )

    def move_linear(self, group_name: str) -> bool:
        return self._nav.move_linear_group(group_name)

    def get_group_names(self) -> list[str]:
        return self._nav.get_group_names()

    def _move_with_z_offset(
        self,
        group_name: str,
        z_offset: float,
        wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        if not z_offset:
            return self._nav.move_to_group(group_name, wait_cancelled=wait_cancelled)
        try:
            config = self._nav._get_config()  # still needed to read position
            group = self._nav._get_group(config, group_name)
            position = group.parse_position()
            if position is None:
                return False
            position = list(position)
            position[2] += z_offset
            return self._nav.move_to_position(position, group_name, wait_cancelled=wait_cancelled)
        except Exception:
            import traceback
            traceback.print_exc()
            return False


    def _set_area(self, area: str) -> None:
        if self._vision is not None:
            self._vision.set_detection_area(area)
