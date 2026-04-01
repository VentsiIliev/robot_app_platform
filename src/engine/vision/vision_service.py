import logging

import numpy as np
import logging
from src.engine.core.i_health_checkable import IHealthCheckable
from src.engine.vision.i_vision_service import IVisionService
from src.engine.vision.i_exposure_control import IExposureControl
from src.engine.work_areas.i_work_area_service import IWorkAreaService

_logger = logging.getLogger(__name__)


class VisionService(IVisionService, IHealthCheckable,IExposureControl):

    def __init__(self, vision_system, work_area_service: IWorkAreaService | None = None):
        self._vision_system = vision_system
        self._work_area_service = work_area_service
        self._running = False
        self._logger = logging.getLogger(self.__class__.__name__)

    def start(self) -> None:
        self._vision_system.start_system()
        self._running = True
        self._logger.info("VisionService started")

    def stop(self) -> None:
        self._vision_system.stop_system()
        self._running = False
        self._logger.info("VisionService stopped")

    def set_raw_mode(self, enabled: bool) -> None:
        self._vision_system.rawMode = enabled

    def capture_calibration_image(self) -> tuple[bool, str]:
        return self._vision_system.captureCalibrationImage()

    def calibrate_camera(self) -> tuple[bool, str]:
        return self._vision_system.calibrateCamera()

    def update_settings(self, settings: dict) -> tuple[bool, str]:
        return self._vision_system.updateSettings(settings)

    def is_healthy(self) -> bool:
        if not self._running:
            return False
        state_manager = self._vision_system.state_manager
        if state_manager is None:
            # no messaging wired — fall back to a running flag only
            return self._running
        from src.engine.vision.implementation.VisionSystem.core.external_communication.system_state_management import ServiceState
        return state_manager.state in (ServiceState.IDLE, ServiceState.STARTED)

    def save_work_area(self, area_type: str, pixel_points) -> tuple[bool, str]:
        import numpy as np
        data = {
            "area_type": area_type,
            "corners":   np.array(pixel_points, dtype=np.float32),
        }
        return self._vision_system.saveWorkAreaPoints(data)

    def get_latest_contours(self) -> list:
        return list(self._vision_system._latest_contours or [])

    def get_latest_frame(self) -> np.ndarray:
        corrected = self._vision_system.correctedImage
        return corrected if corrected is not None else self._vision_system.rawImage

    def get_latest_corrected_frame(self) -> np.ndarray | None:
        return self._vision_system.correctedImage

    def detect_aruco_markers(self, image: np.ndarray) -> tuple:
        return self._vision_system.detectArucoMarkers(image=image)

    def get_camera_width(self) -> int:
        return self._vision_system.camera_settings.get_camera_width()

    def get_camera_height(self) -> int:
        return self._vision_system.camera_settings.get_camera_height()

    def get_chessboard_width(self) -> int:
        return self._vision_system.camera_settings.get_chessboard_width()

    def get_chessboard_height(self) -> int:
        return self._vision_system.camera_settings.get_chessboard_height()

    def get_square_size_mm(self) -> float:
        return self._vision_system.camera_settings.get_square_size_mm()

    def set_draw_contours(self, enabled: bool) -> None:
        self._vision_system.camera_settings.set_draw_contours(enabled)

    def get_auto_brightness_enabled(self) -> bool:
        return bool(self._vision_system.camera_settings.get_brightness_auto())

    def set_auto_brightness_enabled(self, enabled: bool) -> None:
        self._vision_system.camera_settings.set_brightness_auto(enabled)

    def lock_auto_brightness_region(self) -> bool:
        return bool(self._vision_system.lock_auto_brightness_region())

    def unlock_auto_brightness_region(self) -> None:
        self._vision_system.unlock_auto_brightness_region()

    def lock_auto_brightness_adjustment(self) -> None:
        self._vision_system.lock_auto_brightness_adjustment()

    def unlock_auto_brightness_adjustment(self) -> None:
        self._vision_system.unlock_auto_brightness_adjustment()

    def get_perspective_matrix(self):
        return self._vision_system.perspectiveMatrix

    @property
    def camera_to_robot_matrix_path(self) -> str:
        return self._vision_system.camera_to_robot_matrix_path

    def get_work_area(self, area_type: str) -> tuple[bool, str, any]:
        return self._vision_system.getWorkAreaPoints(area_type)

    def run_matching(self, workpieces: list, contours: list):
        from src.engine.vision.implementation.VisionSystem.features.contour_matching import find_matching_workpieces
        result, no_matches, matched_contours = find_matching_workpieces(workpieces, contours)
        return (
            result,
            len(no_matches),
            [c.get() for c in matched_contours],
            [c.get() for c in no_matches],
        )

    def set_auto_exposure(self, enabled: bool) -> None:
        camera = self._vision_system.camera
        if hasattr(camera, "set_auto_exposure"):
            camera.set_auto_exposure(enabled)
        else:
            _logger.debug("set_auto_exposure: camera does not support exposure control, skipping")
        self.set_auto_brightness_enabled(enabled)

    def set_detection_area(self, area: str) -> None:
        self.set_active_work_area(area)

    def set_active_work_area(self, area_id: str | None) -> None:
        if self._work_area_service is not None:
            try:
                self._work_area_service.set_active_area_id(area_id)
            except KeyError as exc:
                self._logger.warning("Ignoring invalid active work area %r: %s", area_id, exc)
        self._vision_system.on_threshold_update({"region": area_id or ""})

    def get_capture_pos_offset(self) -> float:
        return self._vision_system.camera_settings.get_capture_pos_offset()
