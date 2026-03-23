import logging
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:
    from src.engine.robot.height_measuring.i_height_correction_service import IHeightCorrectionService

import numpy as np

from src.applications.pick_target.service.i_pick_target_service import IPickTargetService
from src.engine.core.i_coordinate_transformer import ICoordinateTransformer
from src.engine.robot.height_measuring.i_height_measuring_service import IHeightMeasuringService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.vision.i_capture_snapshot_service import ICaptureSnapshotService
from src.engine.vision.i_vision_service import IVisionService
from src.engine.vision.implementation.VisionSystem.core.models.contour import Contour
from src.robot_systems.glue.targeting import VisionPoseRequest, PointRegistry, TargetFrame, VisionTargetResolver
from src.engine.robot.plane_pose_mapper import PlanePoseMapper

_logger = logging.getLogger(__name__)

_Z = 300.0
_CALIB_RZ = 0.0


class PickTargetApplicationService(IPickTargetService):

    def __init__(
        self,
        vision_service:  Optional[IVisionService],
        capture_snapshot_service: Optional[ICaptureSnapshotService],
        robot_service:   Optional[IRobotService],
        transformer:     Optional[ICoordinateTransformer],
        robot_config=None,
        navigation=None,
        height_correction: Optional["IHeightCorrectionService"] = None,
        height_measuring: Optional[IHeightMeasuringService] = None,
    ):
        self._vision        = vision_service
        self._capture_snapshot_service = capture_snapshot_service
        self._robot         = robot_service
        self._transformer   = transformer
        self._robot_config  = robot_config
        self._navigation    = navigation
        self._height_measuring  = height_measuring
        self._target        = "camera_center"
        self._use_pickup_plane = False
        self._pickup_plane_rz = 90.0
        self._pickup_mapper = self._build_pickup_mapper()

        registry = PointRegistry(robot_config)
        tcp_x = float(getattr(self._robot_config, "camera_to_tcp_x_offset", 0.0)) if self._robot_config is not None else 0.0
        tcp_y = float(getattr(self._robot_config, "camera_to_tcp_y_offset", 0.0)) if self._robot_config is not None else 0.0
        self._resolver = (
            VisionTargetResolver(
                base_transformer=self._transformer,
                registry=registry,
                camera_to_tcp_x_offset=tcp_x,
                camera_to_tcp_y_offset=tcp_y,
                frames={
                    TargetFrame.CALIBRATION: TargetFrame(
                        TargetFrame.CALIBRATION,
                        height_correction=height_correction,
                    ),
                    TargetFrame.PICKUP: TargetFrame(
                        TargetFrame.PICKUP,
                        mapper=self._pickup_mapper,
                    ),
                },
            )
            if self._transformer is not None else None
        )

    def set_target(self, target: str) -> None:
        target = str(target).strip().lower()
        if target == "camera":
            target = "camera_center"
        if target not in {"camera_center", "tool", "gripper"}:
            raise ValueError(f"Unsupported target '{target}'")
        self._target = target

    def set_use_pickup_plane(self, enabled: bool) -> None:
        self._use_pickup_plane = enabled

    def set_pickup_plane_rz(self, rz: float) -> None:
        self._pickup_plane_rz = float(rz)

    def _tool(self) -> int:
        return self._robot_config.robot_tool if self._robot_config else 0

    def _user(self) -> int:
        return self._robot_config.robot_user if self._robot_config else 0

    def _build_pickup_mapper(self) -> Optional[PlanePoseMapper]:
        if self._navigation is None:
            return None
        try:
            calibration_position = self._navigation.get_group_position("CALIBRATION")
            pickup_position = self._navigation.get_group_position("HOME")
            if calibration_position is None or pickup_position is None:
                return None
            return PlanePoseMapper.from_positions(
                source_position=calibration_position,
                target_position=pickup_position,
            )
        except Exception:
            _logger.exception("Failed to initialize calibration-to-target-pose mapper")
            return None

    @property
    def _active_frame(self) -> str:
        return TargetFrame.PICKUP if self._use_pickup_plane else TargetFrame.CALIBRATION

    def get_jog_reference_rz(self) -> float:
        if self._active_frame == TargetFrame.PICKUP and self._pickup_mapper is not None:
            return float(self._pickup_mapper.target_pose.rz)
        return 0.0

    def _pose_target(self, px: float, py: float, z_mm: float = 0.0) -> VisionPoseRequest:
        return VisionPoseRequest(
            x_pixels=px,
            y_pixels=py,
            z_mm=z_mm,
            rz_degrees=self._pickup_plane_rz,
            rx_degrees=180.0,
            ry_degrees=0.0,
        )

    def _transform_point(self, px: float, py: float) -> Tuple[float, float]:
        if self._resolver is None:
            raise RuntimeError("Coordinate transformer is not available")
        return self._resolver.resolve_named(
            self._pose_target(px, py), self._target, frame=self._active_frame
        ).final_xy

    def capture(self) -> Tuple[Optional[np.ndarray], List[Tuple[float, float]], List[Tuple[float, float, float, float, float, float]]]:
        if self._capture_snapshot_service is None:
            _logger.warning("Capture snapshot service not available")
            return None, [], []

        snapshot = self._capture_snapshot_service.capture_snapshot(source="pick_target.capture")
        frame = snapshot.frame
        raw_contours = snapshot.contours

        from src.applications.pick_target.service.i_pick_target_service import RobotPose
        pixel_centroids: List[Tuple[float, float]] = []
        robot_targets:   List[RobotPose] = []

        for raw in raw_contours:
            try:
                cnt = Contour(raw)
                px, py = cnt.getCentroid()
                pixel_centroids.append((px, py))
                if self._resolver is not None:
                    result = self._resolver.resolve_named(
                        self._pose_target(px, py, z_mm=_Z), self._target, frame=self._active_frame,
                    )
                    robot_targets.append(result.robot_pose())
            except Exception:
                _logger.exception("Failed to process contour centroid")

        return frame, pixel_centroids, robot_targets

    def move_to(self, x: float, y: float, z: float, rx: float, ry: float, rz: float) -> bool:
        if self._robot is None:
            _logger.warning("Robot service not available — cannot move")
            return False
        try:
            return self._robot.move_ptp(
                [x, y, z, rx, ry, rz],
                tool=self._tool(),
                user=self._user(),
                velocity=20,
                acceleration=10,
                wait_to_reach=True,
            )
        except Exception:
            _logger.exception("move_to(%.1f, %.1f, %.1f) failed", x, y, z)
            return False

    def move_to_base(self, robot_x: float, robot_y: float, rx: float, ry: float, rz: float) -> bool:
        if self._robot is None:
            _logger.warning("Robot service not available — cannot move")
            return False
        try:
            return self._robot.move_ptp(
                [robot_x, robot_y, _Z, rx, ry, rz],
                tool=self._tool(),
                user=self._user(),
                velocity=20,
                acceleration=10,
                wait_to_reach=True,
            )
        except Exception:
            _logger.exception("move_to_base(%.1f, %.1f) failed", robot_x, robot_y)
            return False

    def move_to_with_live_height(self, robot_x: float, robot_y: float, rx: float, ry: float, rz: float) -> bool:
        if self._robot is None:
            _logger.warning("Robot service not available — cannot move")
            return False
        if not self.move_to_base(robot_x, robot_y, rx, ry, rz):
            return False
        if self._height_measuring is None:
            _logger.warning("Height measuring service not available — staying at base Z")
            return True
        try:
            self._height_measuring.begin_measurement_session()
            measured_z = self._height_measuring.measure_at(robot_x, robot_y)
            self._height_measuring.end_measurement_session()
        except Exception:
            _logger.exception("Live height measurement failed at (%.1f, %.1f)", robot_x, robot_y)
            return True  # base move succeeded
        if measured_z is None:
            _logger.warning("Height measurement returned None at (%.1f, %.1f) — staying at base Z", robot_x, robot_y)
            return True
        adjusted_z = _Z + measured_z
        _logger.debug(
            "Live height correction at (%.1f, %.1f): base=%.1f measured=%.3f adjusted=%.3f",
            robot_x, robot_y, _Z, measured_z, adjusted_z,
        )
        try:
            return self._robot.move_ptp(
                [robot_x, robot_y, adjusted_z, rx, ry, rz],
                tool=self._tool(),
                user=self._user(),
                velocity=20,
                acceleration=10,
                wait_to_reach=True,
            )
        except Exception:
            _logger.exception("move_to_with_live_height Z-adjust failed at (%.1f, %.1f)", robot_x, robot_y)
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
        if self._capture_snapshot_service is None:
            return []
        raw_contours = self._capture_snapshot_service.capture_snapshot(
            source="pick_target.capture_contour_trajectory"
        ).contours
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
            rx, ry, rz = 180.0, 0.0, self._pickup_plane_rz
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
