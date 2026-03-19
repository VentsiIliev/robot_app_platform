import logging
import os
import time
from typing import Optional, Protocol, Sequence

from src.applications.calibration.service.i_calibration_service import ICalibrationService
from src.engine.core.i_coordinate_transformer import ICoordinateTransformer
from src.engine.vision.i_vision_service import IVisionService

_logger = logging.getLogger(__name__)

_DEFAULT_VELOCITY     = 30
_DEFAULT_ACCELERATION = 10


class _IProcessController(Protocol):
    def calibrate(self) -> None: ...
    def stop_calibration(self) -> None: ...


class _IRobotService(Protocol):
    def get_current_position(self) -> list: ...
    def move_ptp(self, position, tool, user, velocity, acceleration, wait_to_reach=False) -> bool: ...
    def stop_motion(self) -> bool: ...


class _IHeightService(Protocol):
    def is_calibrated(self) -> bool: ...
    def measure_at(self, x: float, y: float, *, already_at_xy: bool = False) -> Optional[float]: ...
    def save_height_map(
        self,
        samples: list[list[float]],
        marker_ids: Optional[list[int]] = None,
        point_labels: Optional[list[str]] = None,
        grid_rows: int = 0,
        grid_cols: int = 0,
        planned_points: Optional[list[list[float]]] = None,
        planned_point_labels: Optional[list[str]] = None,
        unavailable_point_labels: Optional[list[str]] = None,
    ) -> None: ...
    def get_depth_map_data(self): ...


class _IRobotConfig(Protocol):
    robot_tool: int
    robot_user: int


class _ICalibConfig(Protocol):
    required_ids: list
    z_target: int
    velocity: int
    acceleration: int


class _ICameraTcpOffsetCalibrator(Protocol):
    def calibrate(self) -> tuple[bool, str]: ...

    def stop(self) -> None: ...


class _IMarkerHeightMappingService(Protocol):
    def measure_marker_heights(self) -> tuple[bool, str]: ...
    def generate_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> list[tuple[float, float]]: ...
    def measure_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> tuple[bool, str]: ...
    def verify_height_model(self) -> tuple[bool, str]: ...
    def stop(self) -> None: ...
    def is_ready(self) -> bool: ...


class CalibrationApplicationService(ICalibrationService):

    def __init__(self, vision_service: IVisionService, process_controller: _IProcessController,
                 robot_service: _IRobotService = None, height_service: _IHeightService = None,
                 robot_config: _IRobotConfig = None, calib_config: _ICalibConfig = None,
                 transformer: ICoordinateTransformer = None,
                 camera_tcp_offset_calibrator: Optional[_ICameraTcpOffsetCalibrator] = None,
                 marker_height_mapping_service: Optional[_IMarkerHeightMappingService] = None,
                 use_marker_centre: bool = False):
        self._vision_service      = vision_service
        self._process_controller  = process_controller
        self._robot_service       = robot_service
        self._height_service      = height_service
        self._robot_config        = robot_config
        self._calib_config        = calib_config
        self._transformer         = transformer
        self._camera_tcp_offset_calibrator = camera_tcp_offset_calibrator
        self._marker_height_mapping_service = marker_height_mapping_service
        self._use_marker_centre   = use_marker_centre
        self._stop_test           = False

    # ── Helpers ───────────────────────────────────────────────────────

    def _robot_tool(self) -> int:
        return self._robot_config.robot_tool if self._robot_config else 0

    def _robot_user(self) -> int:
        return self._robot_config.robot_user if self._robot_config else 0

    def _required_ids(self) -> set | None:
        if self._calib_config is None:
            return None
        return set(self._calib_config.required_ids)

    def _movement_velocity(self) -> int:
        if self._calib_config is None:
            return _DEFAULT_VELOCITY
        return self._calib_config.velocity

    def _movement_acceleration(self) -> int:
        if self._calib_config is None:
            return _DEFAULT_ACCELERATION
        return self._calib_config.acceleration

    # ── ICalibrationService ───────────────────────────────────────────

    def capture_calibration_image(self) -> tuple[bool, str]:
        return self._vision_service.capture_calibration_image()

    def calibrate_camera(self) -> tuple[bool, str]:
        return self._vision_service.calibrate_camera()

    def calibrate_robot(self) -> tuple[bool, str]:
        self._process_controller.calibrate()
        return True, "Robot calibration started"

    def calibrate_camera_and_robot(self) -> tuple[bool, str]:
        ok, msg = self.calibrate_camera()
        if not ok:
            return False, f"Camera calibration failed: {msg}"
        self._process_controller.calibrate()
        return True, "Camera calibrated — robot calibration started"

    def calibrate_camera_tcp_offset(self) -> tuple[bool, str]:
        if not self.is_calibrated():
            return False, "System not calibrated — run robot calibration first"
        if self._camera_tcp_offset_calibrator is None:
            return False, "Camera TCP offset calibration is not configured"
        return self._camera_tcp_offset_calibrator.calibrate()

    def stop_calibration(self) -> None:
        self._process_controller.stop_calibration()
        if self._camera_tcp_offset_calibrator is not None:
            self._camera_tcp_offset_calibrator.stop()
        if self._marker_height_mapping_service is not None:
            self._marker_height_mapping_service.stop()

    def is_calibrated(self) -> bool:
        if self._vision_service is None:
            return False
        robot_matrix = self._vision_service.camera_to_robot_matrix_path
        storage_dir = os.path.dirname(robot_matrix)
        camera_matrix = os.path.join(storage_dir, "camera_calibration.npz")
        return os.path.isfile(robot_matrix) and os.path.isfile(camera_matrix)

    def test_calibration(self) -> tuple[bool, str]:
        self._stop_test = False

        if self._vision_service is None:
            return False, "Vision service unavailable"
        if self._robot_service is None:
            return False, "Robot service unavailable"

        frame = self._vision_service.get_latest_frame()
        if frame is None:
            return False, "No camera frame available"

        corners, ids, _ = self._vision_service.detect_aruco_markers(frame)
        if ids is None or len(ids) == 0:
            return False, "No ArUco markers detected in current frame"

        if self._transformer is not None:
            self._transformer.reload()

        if self._transformer is None or not self._transformer.is_available():
            return False, "System not calibrated — run calibration first"

        current_pos = self._robot_service.get_current_position()
        if not current_pos or len(current_pos) < 6:
            return False, "Failed to get current robot position"

        rx, ry, rz = current_pos[3], current_pos[4], current_pos[5]
        required = self._required_ids()
        tool     = self._robot_tool()
        user     = self._robot_user()
        velocity = self._movement_velocity()
        accel    = self._movement_acceleration()
        z_target = self._calib_config.z_target if self._calib_config else 300

        _logger.info(
            "test_calibration: tool=%d user=%d vel=%d acc=%d z=%d required=%s",
            tool, user, velocity, accel, z_target, required,
        )

        # Sort detections by marker ID (smallest → largest)
        sorted_pairs = sorted(zip(ids.flatten(), corners), key=lambda p: int(p[0]))

        moved = 0
        for marker_id, marker_corners in sorted_pairs:
            if self._stop_test:
                return True, f"Test stopped — moved to {moved}/{len(ids)} marker(s)"

            if required is not None and int(marker_id) not in required:
                _logger.debug("Skipping marker %d — not in required_ids", marker_id)
                continue

            # Use marker centre (mean of 4 corners) or top-left corner (index 0)
            # depending on how the homography was computed.
            if self._use_marker_centre:
                px, py = marker_corners[0].mean(axis=0)
            else:
                px, py = marker_corners[0][0]
            x_mm, y_mm = self._transformer.transform(float(px), float(py))

            _logger.info("Moving to marker %d: (%.2f, %.2f) mm", marker_id, x_mm, y_mm)
            ok = self._robot_service.move_ptp(
                position=[x_mm, y_mm, z_target, rx, ry, rz],
                tool=tool,
                user=user,
                velocity=velocity,
                acceleration=accel,
                wait_to_reach=True,
            )
            if not ok:
                return False, f"Move to marker {marker_id} failed"
            moved += 1
            time.sleep(1)

        return True, f"Test complete — moved to {moved} marker(s)"

    def stop_test_calibration(self) -> None:
        self._stop_test = True

    def measure_marker_heights(self) -> tuple[bool, str]:
        if not self.is_calibrated():
            return False, "System not calibrated — run robot calibration first"
        if self._marker_height_mapping_service is None:
            return False, "Marker height mapping is not configured"
        return self._marker_height_mapping_service.measure_marker_heights()

    def generate_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> list[tuple[float, float]]:
        if self._marker_height_mapping_service is None:
            return []
        return self._marker_height_mapping_service.generate_area_grid(corners_norm, rows, cols)

    def measure_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> tuple[bool, str]:
        if not self.is_calibrated():
            return False, "System not calibrated — run robot calibration first"
        if self._marker_height_mapping_service is None:
            return False, "Area grid height mapping is not configured"
        return self._marker_height_mapping_service.measure_area_grid(corners_norm, rows, cols)

    def stop_marker_height_measurement(self) -> None:
        if self._marker_height_mapping_service is not None:
            self._marker_height_mapping_service.stop()

    def can_measure_marker_heights(self) -> bool:
        if not self.is_calibrated():
            return False
        if self._marker_height_mapping_service is None:
            return False
        return self._marker_height_mapping_service.is_ready()

    def verify_height_model(self) -> tuple[bool, str]:
        if self._marker_height_mapping_service is None:
            return False, "Marker height mapping is not configured"
        return self._marker_height_mapping_service.verify_height_model()

    def has_saved_height_model(self) -> bool:
        data = self.get_height_calibration_data()
        return bool(data is not None and data.has_data())

    def get_height_calibration_data(self):
        if self._height_service is None:
            return None
        return self._height_service.get_depth_map_data()

    def restore_pending_safety_walls(self) -> bool:
        if self._marker_height_mapping_service is None:
            return False
        restore = getattr(self._marker_height_mapping_service, "restore_pending_safety_walls", None)
        if restore is None:
            return False
        return bool(restore())
