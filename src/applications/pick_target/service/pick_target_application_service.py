import logging
from typing import List, Optional, Tuple

import numpy as np

from src.applications.pick_target.service.i_pick_target_service import IPickTargetService
from src.engine.core.i_coordinate_transformer import ICoordinateTransformer
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.vision.i_vision_service import IVisionService
from src.engine.vision.implementation.VisionSystem.core.models.contour import Contour
from src.robot_systems.glue.target_point_transformer import TargetPointTransformer
from src.robot_systems.glue.processes.pick_and_place.execution import CalibrationToPickupPlaneMapper

_logger = logging.getLogger(__name__)

_Z = 300.0
_CALIB_RZ = 0.0


class PickTargetApplicationService(IPickTargetService):

    def __init__(
        self,
        vision_service:  Optional[IVisionService],
        robot_service:   Optional[IRobotService],
        transformer:     Optional[ICoordinateTransformer],
        robot_config=None,
        navigation=None,
    ):
        self._vision        = vision_service
        self._robot         = robot_service
        self._transformer   = transformer
        self._robot_config  = robot_config
        self._navigation    = navigation
        self._use_tcp       = False
        self._use_pickup_plane = False
        self._pickup_plane_rz = 90.0
        self._pickup_mapper = self._build_pickup_mapper()
        self._point_transformer = (
            TargetPointTransformer(
                base_transformer=self._transformer,
                calibration_to_pickup_mapper=self._pickup_mapper.map_point if self._pickup_mapper is not None else None,
                camera_to_tcp_x_offset=float(getattr(self._robot_config, "camera_to_tcp_x_offset", 0.0)) if self._robot_config is not None else 0.0,
                camera_to_tcp_y_offset=float(getattr(self._robot_config, "camera_to_tcp_y_offset", 0.0)) if self._robot_config is not None else 0.0,
                camera_to_tool_x_offset=float(getattr(self._robot_config, "camera_to_tool_x_offset", 0.0)) if self._robot_config is not None else 0.0,
                camera_to_tool_y_offset=float(getattr(self._robot_config, "camera_to_tool_y_offset", 0.0)) if self._robot_config is not None else 0.0,
            )
            if self._transformer is not None else None
        )

    def set_use_tcp(self, enabled: bool) -> None:
        self._use_tcp = enabled

    def set_use_pickup_plane(self, enabled: bool) -> None:
        self._use_pickup_plane = enabled

    def set_pickup_plane_rz(self, rz: float) -> None:
        self._pickup_plane_rz = float(rz)

    def _tool(self) -> int:
        return self._robot_config.robot_tool if self._robot_config else 0

    def _user(self) -> int:
        return self._robot_config.robot_user if self._robot_config else 0

    def _build_pickup_mapper(self) -> Optional[CalibrationToPickupPlaneMapper]:
        if self._navigation is None:
            return None
        try:
            calibration_position = self._navigation.get_group_position("CALIBRATION")
            pickup_position = self._navigation.get_group_position("HOME")
            if calibration_position is None or pickup_position is None:
                return None
            return CalibrationToPickupPlaneMapper.from_positions(
                calibration_position=calibration_position,
                pickup_position=pickup_position,
            )
        except Exception:
            _logger.exception("Failed to initialize calibration-to-pickup mapper")
            return None

    def _transform_point(self, px: float, py: float) -> Tuple[float, float]:
        if self._point_transformer is None:
            raise RuntimeError("Coordinate transformer is not available")
        plane = "pickup" if self._use_pickup_plane else "calibration"
        if self._use_tcp:
            result = self._point_transformer.transform_to_tool(px, py, plane=plane)
        else:
            result = self._point_transformer.transform_to_camera_center(
                px,
                py,
                plane=plane,
                current_rz=self._pickup_plane_rz if self._use_pickup_plane else None,
            )
        return result.final_xy

    def _target_orientation(self) -> Tuple[float, float, float]:
        return 180.0, 0.0, (self._pickup_plane_rz if self._use_pickup_plane else _CALIB_RZ)

    def capture(self) -> Tuple[Optional[np.ndarray], List[Tuple[float, float]], List[Tuple[float, float]]]:
        if self._vision is None:
            _logger.warning("Vision service not available")
            return None, [], []

        frame = self._vision.get_latest_frame()
        raw_contours = self._vision.get_latest_contours()

        pixel_centroids: List[Tuple[float, float]] = []
        robot_centroids: List[Tuple[float, float]] = []

        for raw in raw_contours:
            try:
                cnt = Contour(raw)
                px, py = cnt.getCentroid()
                pixel_centroids.append((px, py))
                if self._transformer is not None:
                    rx, ry = self._transform_point(px, py)
                    robot_centroids.append((rx, ry))
            except Exception:
                _logger.exception("Failed to process contour centroid")

        return frame, pixel_centroids, robot_centroids

    def move_to(self, robot_x: float, robot_y: float) -> bool:
        if self._robot is None:
            _logger.warning("Robot service not available — cannot move")
            return False
        try:
            rx, ry, rz = self._target_orientation()
            return self._robot.move_ptp(
                [robot_x, robot_y, _Z, rx, ry, rz],
                tool=self._tool(),
                user=self._user(),
                velocity=20,
                acceleration=10,
                wait_to_reach=True,
            )
        except Exception:
            _logger.exception("move_to(%.1f, %.1f) failed", robot_x, robot_y)
            return False

    def move_to_calibration_position(self) -> bool:
        if self._navigation is None:
            _logger.warning("Navigation service not available")
            return False
        try:
            if self._use_pickup_plane:
                return self._navigation.move_home()
            z_offset = self._vision.get_capture_pos_offset() if self._vision is not None else 0.0
            return self._navigation.move_to_calibration_position(z_offset=z_offset)
        except Exception:
            _logger.exception("move_to_calibration_position failed")
            return False

    def capture_contour_trajectory(self) -> List[np.ndarray]:
        if self._vision is None:
            return []
        raw_contours = self._vision.get_latest_contours()
        result = []
        for raw in raw_contours:
            try:
                cnt = Contour(raw)
                pts_px = cnt.get()                           # (N, 2) float32 pixel coords
                robot_pts: List[Tuple[float, float]] = []
                for px, py in pts_px:
                    rx, ry = self._transform_point(float(px), float(py))
                    robot_pts.append((rx, ry))
                if robot_pts:
                    result.append(np.array(robot_pts, dtype=np.float32))
            except Exception:
                _logger.exception("Failed to transform contour for trajectory")
        return result

    def execute_contour_trajectory(
        self,
        contour_robot_pts: List[np.ndarray],
        z: float,
        vel: float,
        acc: float,
    ) -> Tuple[bool, str]:
        if self._robot is None:
            return False, "Robot service unavailable"
        exec_fn = getattr(self._robot, 'execute_trajectory', None)
        if exec_fn is None:
            return False, "execute_trajectory not supported by this robot driver"
        if not contour_robot_pts:
            return False, "No contour waypoints to execute"
        try:
            rx, ry, rz = self._target_orientation()
            total_pts = 0
            for pts in contour_robot_pts:
                path = [[float(x), float(y), float(z)] for x, y in pts]
                if not path:
                    continue
                result_code = exec_fn(path, rx=rx, ry=ry, rz=rz, vel=vel, acc=acc, blocking=True)
                if result_code not in (0, True, None):
                    return False, f"Trajectory failed with code {result_code}"
                total_pts += len(path)
            return True, f"Trajectory complete — {len(contour_robot_pts)} contour(s), {total_pts} waypoints"
        except Exception:
            _logger.exception("execute_contour_trajectory failed")
            return False, "Trajectory error — see log"
