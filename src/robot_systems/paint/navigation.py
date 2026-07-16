import logging
from typing import Callable, Optional
from src.engine.robot.features.navigation_service import NavigationService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.vision import IVisionService
from src.engine.work_areas.i_work_area_service import IWorkAreaService
from src.robot_systems.paint.timing import timed_step
from src.robot_systems.paint.processes.paint.config import PaintNavigationReturnConfig

_logger = logging.getLogger(__name__)


class PaintNavigationService:

    _GROUP_HOME        = "HOME"
    _GROUP_LOGIN       = "LOGIN"
    _GROUP_CALIBRATION = "CALIBRATION"

    def __init__(
        self,
        navigation: NavigationService,
        vision: Optional[IVisionService] = None,
        robot_service: Optional[IRobotService] = None,
        work_area_service: Optional[IWorkAreaService] = None,
        observed_area_by_group: Optional[dict[str, str]] = None,
        unwind_vel_percent: float = 100.0,
        unwind_acc_percent: float = 100.0,
        unwind_queue_if_busy: bool = True,
        calibration_move_vel_percent: float | None = None,
        calibration_move_acc_percent: float | None = None,
        paint_process_config_service: object | None = None,
    ):
        self._nav = navigation
        self._vision = vision
        self._robot = robot_service
        self._work_area_service = work_area_service
        self._unwind_vel_percent = float(unwind_vel_percent)
        self._unwind_acc_percent = float(unwind_acc_percent)
        self._unwind_queue_if_busy = bool(unwind_queue_if_busy)
        self._calibration_move_vel_percent = (
            None if calibration_move_vel_percent is None else float(calibration_move_vel_percent)
        )
        self._calibration_move_acc_percent = (
            None if calibration_move_acc_percent is None else float(calibration_move_acc_percent)
        )
        self._paint_process_config_service = paint_process_config_service
        self._observed_area_by_group = {
            str(group_id).strip(): str(area_id).strip()
            for group_id, area_id in (observed_area_by_group or {}).items()
            if str(group_id).strip() and str(area_id).strip()
        }

    def _navigation_return_config(self) -> PaintNavigationReturnConfig:
        service = self._paint_process_config_service
        if service is not None:
            try:
                return service.get_snapshot().navigation_return
            except Exception:
                _logger.debug("[NAV] Failed to read live Paint navigation return settings", exc_info=True)
        return PaintNavigationReturnConfig(
            unwind_vel_percent=self._unwind_vel_percent,
            unwind_acc_percent=self._unwind_acc_percent,
            unwind_queue_if_busy=self._unwind_queue_if_busy,
            calibration_move_vel_percent=(
                30.0 if self._calibration_move_vel_percent is None else self._calibration_move_vel_percent
            ),
            calibration_move_acc_percent=(
                40.0 if self._calibration_move_acc_percent is None else self._calibration_move_acc_percent
            ),
        )

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

    @timed_step(_logger, "move_to_calibration_position")
    def move_to_calibration_position(
        self,
        z_offset: float = 0.0,
        wait_cancelled: Callable[[], bool] | None = None,
        unwind_before_move: bool = True,
    ) -> bool:
        if unwind_before_move and not self._unwind_joint6_before_calibration_return():
            return False
        ok = self._move_with_z_offset(self._GROUP_CALIBRATION, z_offset, wait_cancelled=wait_cancelled)
        if ok:
            self._set_observed_area_for_group(self._GROUP_CALIBRATION)
        return ok

    def move_to(
        self,
        group_name: str,
        z_offset: float = 0.0,
        wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        ok = (
            self._move_with_z_offset(group_name, z_offset, wait_cancelled=wait_cancelled)
            if z_offset else self._nav.move_to_group(group_name, wait_cancelled=wait_cancelled)
        )
        if ok:
            self._set_observed_area_for_group(group_name)
        return ok

    def move_linear(self, group_name: str) -> bool:
        ok = self._nav.move_linear_group(group_name)
        if ok:
            self._set_observed_area_for_group(group_name)
        return ok

    def move_to_group(self, group_name: str, wait_cancelled: Callable[[], bool] | None = None) -> bool:
        ok = self._nav.move_to_group(group_name, wait_cancelled=wait_cancelled)
        if ok:
            self._set_observed_area_for_group(group_name)
        return ok

    def move_linear_group(self, group_name: str) -> bool:
        ok = self._nav.move_linear_group(group_name)
        if ok:
            self._set_observed_area_for_group(group_name)
        return ok

    def move_to_position(
        self,
        position: list,
        group_name: str,
        wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        ok = self._nav.move_to_position(position, group_name, wait_cancelled=wait_cancelled)
        if ok:
            self._set_observed_area_for_group(group_name)
        return ok

    def get_group_names(self) -> list[str]:
        return self._nav.get_group_names()

    def get_group_position(self, group_name: str) -> list[float] | None:
        try:
            group = self._nav._get_group(group_name)
            position = group.parse_position()
            return list(position) if position is not None else None
        except Exception:
            return None

    @timed_step(_logger, "move_with_z_offset", label_arg="group_name")
    def _move_with_z_offset(
        self,
        group_name: str,
        z_offset: float,
        wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool:
        nav_return = self._navigation_return_config()
        move_velocity = nav_return.calibration_move_vel_percent if group_name == self._GROUP_CALIBRATION else None
        move_acceleration = nav_return.calibration_move_acc_percent if group_name == self._GROUP_CALIBRATION else None
        if group_name == self._GROUP_CALIBRATION:
            _logger.info(
                "[NAV] Calibration return move override vel=%s acc=%s",
                move_velocity,
                move_acceleration,
            )
        if not z_offset:
            return self._nav.move_to_group(
                group_name,
                wait_cancelled=wait_cancelled,
                velocity=move_velocity,
                acceleration=move_acceleration,
            )
        try:
            group = self._nav._get_group(group_name)
            position = group.parse_position()
            if position is None:
                return False
            position = list(position)
            position[2] += z_offset
            return self._nav.move_to_position(
                position,
                group_name,
                wait_cancelled=wait_cancelled,
                velocity=move_velocity,
                acceleration=move_acceleration,
            )
        except Exception:
            import traceback
            traceback.print_exc()
            return False


    def _set_area(self, area: str) -> None:
        if self._work_area_service is not None:
            self._work_area_service.set_active_area_id(area)
        elif self._vision is not None:
            self._vision.set_active_work_area(area)

    def _set_observed_area_for_group(self, group_name: str) -> None:
        area_id = self._observed_area_by_group.get(str(group_name or "").strip())
        if area_id:
            self._set_area(area_id)

    @timed_step(_logger, "unwind_joint6_before_calibration_return")
    def _unwind_joint6_before_calibration_return(self) -> bool:
        if self._robot is None:
            _logger.warning("[NAV] Calibration return blocked: robot service unavailable for Joint 6 unwind")
            return False
        nav_return = self._navigation_return_config()
        _logger.info(
            "[NAV] Unwinding Joint 6 before calibration return vel=%.1f acc=%.1f queue_if_busy=%s",
            nav_return.unwind_vel_percent,
            nav_return.unwind_acc_percent,
            self._unwind_queue_if_busy,
        )
        if not self._robot.unwind_joint6(
            blocking=True,
            queue_if_busy=self._unwind_queue_if_busy,
            vel=nav_return.unwind_vel_percent,
            acc=nav_return.unwind_acc_percent,
        ):
            _logger.warning("[NAV] Calibration return blocked: Joint 6 unwind failed")
            return False
        _logger.info("[NAV] Joint 6 unwind completed before calibration return")
        return True
