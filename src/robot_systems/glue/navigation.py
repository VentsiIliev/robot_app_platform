from typing import Optional
import logging
from src.engine.robot.features.navigation_service import NavigationService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.vision import IVisionService
_logger = logging.getLogger(__name__)

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
        ok = self._move_home_safely()
        if ok:
            self._set_area("pickup")
        return ok

    def move_to_login_position(self) -> bool:
        return self._nav.move_to_group(self._GROUP_LOGIN)

    def move_to_calibration_position(self, z_offset: float = 0.0) -> bool:
        ok = self._move_with_z_offset(self._GROUP_CALIBRATION, z_offset)
        if ok:
            self._set_area("spray")
        return ok

    def move_to(self, group_name: str, z_offset: float = 0.0) -> bool:
        return self._move_with_z_offset(group_name, z_offset) if z_offset else self._nav.move_to_group(group_name)

    def move_linear(self, group_name: str) -> bool:
        return self._nav.move_linear_group(group_name)

    def get_group_names(self) -> list[str]:
        return self._nav.get_group_names()

    def _move_with_z_offset(self, group_name: str, z_offset: float) -> bool:
        if not z_offset:
            return self._nav.move_to_group(group_name)
        try:
            config = self._nav._get_config()  # still needed to read position
            group = self._nav._get_group(config, group_name)
            position = group.parse_position()
            if position is None:
                return False
            position = list(position)
            position[2] += z_offset
            return self._nav.move_to_position(position, group_name)
        except Exception:
            import traceback
            traceback.print_exc()
            return False

    def _move_home_safely(self) -> bool:
        if self._should_route_home_via_calibration():
            if not self._move_with_z_offset(self._GROUP_CALIBRATION, self._capture_z_offset):
                return False
        return self._move_with_z_offset(self._GROUP_HOME, self._capture_z_offset)

    def _should_route_home_via_calibration(self) -> bool:
        if self._robot is None:
            return False
        try:
            current = self._robot.get_current_position()
            if not current or len(current) < 3:
                return False
            current_xyz = current[:3]
            calibration = self._get_group_position(self._GROUP_CALIBRATION)
            home = self._get_group_position(self._GROUP_HOME)
            if calibration is None or home is None:
                return False
            return not self._is_near(current_xyz, home[:3]) and not self._is_near(current_xyz, calibration[:3])
        except Exception:
            _logger.exception("Failed to evaluate safe home routing")
            return False

    def _get_group_position(self, group_name: str):
        config = self._nav._get_config()
        group = self._nav._get_group(config, group_name)
        return group.parse_position()

    @staticmethod
    def _is_near(current_xyz, target_xyz, tolerance_mm: float = 25.0) -> bool:
        try:
            dx = float(current_xyz[0]) - float(target_xyz[0])
            dy = float(current_xyz[1]) - float(target_xyz[1])
            dz = float(current_xyz[2]) - float(target_xyz[2])
            return (dx * dx + dy * dy + dz * dz) ** 0.5 <= tolerance_mm
        except Exception:
            return False


    def _set_area(self, area: str) -> None:
        if self._vision is not None:
            self._vision.set_detection_area(area)
