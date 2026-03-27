import threading
import logging
from typing import Optional

import cv2
import numpy as np

from src.engine.vision.implementation.VisionSystem.core.camera.frame_grabber import FrameGrabber
from src.engine.vision.implementation.VisionSystem.core.camera.remote_camera import RemoteCamera
from src.engine.vision.implementation.VisionSystem.core.path_resolver import get_path_resolver
from src.engine.vision.implementation.VisionSystem.core.external_communication.system_state_management import (
    StateManager, ServiceState, MessagePublisher, SubscriptionManager,
)
from src.engine.vision.implementation.VisionSystem.core.service.internal_service import Service
from src.engine.vision.implementation.plvision.PLVision.Camera import Camera
from src.engine.vision.implementation.VisionSystem.camera_initialization import CameraInitializer
from src.engine.vision.implementation.plvision.PLVision import ImageProcessing
from src.engine.vision.implementation.VisionSystem.services import (
    ContourDetectionService, CalibrationService, ArucoDetectionService, BrightnessService, QrDetectionService,
)
from src.engine.work_areas.i_work_area_service import IWorkAreaService


_logger = logging.getLogger(__name__)

DEFAULT_STORAGE_PATH = str(get_path_resolver().vision_system_root / 'storage')


class VisionSystem:

    def __init__(self, storage_path=None, messaging_service=None, service=None,
                 work_area_service: IWorkAreaService | None = None):
        self.optimal_camera_matrix = None

        self.storage_path      = storage_path or DEFAULT_STORAGE_PATH
        self.service           = service or Service(data_storage_path=self.storage_path)
        self.messaging_service = messaging_service
        self._work_area_service = work_area_service
        self._active_area_id = work_area_service.get_active_area_id() if work_area_service is not None else ""
        self.service_id        = "vision_service"

        self.camera_settings = self.service.loadSettings()
        self.setup_camera()
        self.load_calibration_data()

        # ── Services (no back-references to VisionSystem) ─────────────────────
        self._brightness_service = BrightnessService(
            self.camera_settings,
            area_points_provider=self._get_active_brightness_area_points,
        )
        self._aruco_service      = ArucoDetectionService(self.camera_settings)
        self._qr_service = QrDetectionService()

        # ── Messaging (must come after _brightness_service is assigned) ───────
        self.message_publisher = None
        self.state_manager     = None
        if self.messaging_service is not None:
            self.setup_external_communication()

        # ── Remaining services (need message_publisher) ───────────────────────
        self._contour_service = ContourDetectionService(
            camera_settings   = self.camera_settings,
            message_publisher = self.message_publisher,
        )
        self._calibration_service = CalibrationService(
            camera_settings   = self.camera_settings,
            storage_path      = self.storage_path,
            message_publisher = self.message_publisher,
            messaging_service = self.messaging_service,
        )

        if self.service.cameraData is not None:
            self.cameraMatrix = self.service.get_camera_matrix()
            self.cameraDist   = self.service.get_distortion_coefficients()
        else:
            self.cameraMatrix = None
            self.cameraDist   = None

        # ── Frame state ───────────────────────────────────────────────────────────
        self.image          = None
        self.rawImage       = None
        self.correctedImage = None
        self.rawMode        = False
        self._latest_contours = []   # ← cached by run(), read by get_latest_contours()

        self.current_skip_frames = 0
        self.frame_grabber = FrameGrabber(self.camera, maxlen=5)
        self.frame_grabber.start()

        self.stop_signal  = False
        self.cameraThread = None

    # ── Setup ─────────────────────────────────────────────────────────────────

    def setup_external_communication(self) -> None:
        self.message_publisher = MessagePublisher(self.messaging_service)
        self.state_manager     = StateManager(
            service_id        = self.service_id,
            initial_state     = ServiceState.INITIALIZING,
            message_publisher = self.message_publisher,
        )
        SubscriptionManager(self, self.messaging_service).subscribe_all()

    def setup_camera(self) -> None:
        camera_index       = self.camera_settings.get_camera_index()
        camera_initializer = CameraInitializer(
            width  = self.camera_settings.get_camera_width(),
            height = self.camera_settings.get_camera_height(),
        )
        self.camera, camera_index = camera_initializer.initializeCameraWithRetry(camera_index)
        # TODO -- CHANGE CAMERA SOURCE HERE IF NEEDED (e.g. for remote camera)
        # self.camera = RemoteCamera(url = "http://192.168.222.178:5000/video_feed", width=self.camera_settings.get_camera_width(), height=self.camera_settings.get_camera_height())
        # self.camera = RemoteCamera(url = "http://192.168.222.110:5000/video_feed", width=self.camera_settings.get_camera_width(), height=self.camera_settings.get_camera_height())
        # self.camera.set_auto_exposure(True)
        self.camera_settings.set_camera_index(camera_index)

    def load_calibration_data(self) -> None:
        self.service.loadPerspectiveMatrix()
        self.service.loadCameraCalibrationData()
        self.service.loadCameraToRobotMatrix()

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def camera_to_robot_matrix_path(self):
        return self.service.camera_to_robot_matrix_path

    @property
    def cameraToRobotMatrix(self):
        return self.service.cameraToRobotMatrix

    @cameraToRobotMatrix.setter
    def cameraToRobotMatrix(self, value):
        self.service.cameraToRobotMatrix = value

    @property
    def perspectiveMatrix(self):
        return self.service.perspectiveMatrix

    @perspectiveMatrix.setter
    def perspectiveMatrix(self, value):
        self.service.perspectiveMatrix = value

    @property
    def stateTopic(self):
        return self.message_publisher.stateTopic if self.message_publisher else None

    @property
    def threshold_by_area(self) -> str:
        return self._get_active_area_id()

    @threshold_by_area.setter
    def threshold_by_area(self, value: str) -> None:
        self._active_area_id = str(value or "")
        if self._work_area_service is not None:
            self._work_area_service.set_active_area_id(value)

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        self.image = self.frame_grabber.get_latest()

        if self.current_skip_frames < self.camera_settings.get_skip_frames():
            self.current_skip_frames += 1
            return None, None, None

        if self.image is None:
            return None, None, None

        if self.state_manager is not None:
            self.state_manager.update_state(ServiceState.IDLE)

        self.rawImage = self.image.copy()

        if self.camera_settings.get_brightness_auto():
            self.image = self._brightness_service.adjust(self.image)

        if self.rawMode:
            if self.message_publisher:
                self.message_publisher.publish_latest_image(self.rawImage)
            return None, self.rawImage, None

        if self.camera_settings.get_contour_detection():
            active_area = self._get_active_area_id()
            contours, self.correctedImage, _ = self._contour_service.detect(
                image             = self.image,
                threshold         = self._get_thresh_by_area(active_area),
                is_calibrated     = self.cameraMatrix is not None,
                correct_image_fn  = self.correctImage,
                spray_area_points = self._get_area_points_by_region(active_area),
            )
            # `detect()` returns None when no contours pass the area filter.
            # Guard here so get_latest_contours() never returns None to callers.
            self._latest_contours = contours or []
            return contours, self.correctedImage, None

        if self.cameraMatrix is None:
            if self.message_publisher:
                self.message_publisher.publish_latest_image(self.image)
            return None, self.image, None

        self.correctedImage = self.correctImage(self.image)
        return None, self.correctedImage, None

    # ── Image correction ──────────────────────────────────────────────────────

    def correctImage(self, image):
        if self.optimal_camera_matrix is None:
            self.optimal_camera_matrix, self.roi = cv2.getOptimalNewCameraMatrix(
                self.cameraMatrix, self.cameraDist,
                (self.camera_settings.get_camera_width(), self.camera_settings.get_camera_height()),
                0.5,
                (self.camera_settings.get_camera_width(), self.camera_settings.get_camera_height()),
            )
        image = ImageProcessing.undistortImage(
            image, self.cameraMatrix, self.cameraDist,
            self.camera_settings.get_camera_width(),
            self.camera_settings.get_camera_height(),
            crop=False,
            optimal_camera_matrix=self.optimal_camera_matrix,
            roi=self.roi,
        )
        if self.perspectiveMatrix is not None:
            image = cv2.warpPerspective(
                image, self.perspectiveMatrix,
                (self.camera_settings.get_camera_width(), self.camera_settings.get_camera_height()),
            )
        return image

    # ── Calibration ───────────────────────────────────────────────────────────

    def captureCalibrationImage(self) -> tuple[bool, str]:
        return self._calibration_service.capture_image(self.rawImage)

    def calibrateCamera(self) -> tuple[bool, str]:
        outcome = self._calibration_service.calibrate(self.rawImage)
        if outcome.success:
            self.cameraMatrix          = outcome.camera_matrix
            self.cameraDist            = outcome.distortion_coefficients
            self.perspectiveMatrix     = outcome.perspective_matrix
            self.optimal_camera_matrix = None
            self.service.loadCameraCalibrationData()
            # Note: do NOT reload perspectiveMatrix from disk here — the outcome
            # already provides the correct value and the file may not exist yet.
            self.service.loadCameraToRobotMatrix()
            _logger.info("Camera calibration completed and vision_service recalibrated")
        return outcome.success, outcome.message

    # ── ArUco ─────────────────────────────────────────────────────────────────

    def detectArucoMarkers(self, flip=False, image=None):
        return self._aruco_service.detect(
            corrected_image = self.correctedImage,
            flip            = flip,
            image           = image,
        )

    # ── QR ────────────────────────────────────────────────────────────────────

    def detectQrCode(self) -> Optional[str]:
        return self._qr_service.detect(self.rawImage)

    # ── Settings ──────────────────────────────────────────────────────────────

    def updateSettings(self, settings: dict) -> tuple[bool, str]:
        def reinit_camera(width: int, height: int) -> None:
            self.camera = Camera(width, height)

        return self.service.updateSettings(
            camera_settings       = self.camera_settings,
            settings              = settings,
            brightness_controller = self._brightness_service.brightness_controller,
            reinit_camera         = reinit_camera,
        )

    def get_camera_settings(self):
        return self.camera_settings

    # ── Work area ─────────────────────────────────────────────────────────────

    def saveWorkAreaPoints(self, data):
        if self._work_area_service is None:
            return False, "Work area service unavailable"
        if not isinstance(data, dict):
            return False, "Invalid work area payload"
        area_type = str(data.get("area_type", "")).strip()
        corners = data.get("corners")
        if not area_type:
            return False, "Area type is required"
        if corners is None:
            return False, "No points provided"
        width = float(self.camera_settings.get_camera_width())
        height = float(self.camera_settings.get_camera_height())
        normalized = []
        for point in np.asarray(corners).tolist():
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                continue
            normalized.append((float(point[0]) / width, float(point[1]) / height))
        return self._work_area_service.save_work_area(area_type, normalized)

    def getWorkAreaPoints(self, area_type):
        if not area_type:
            return False, "Area type is required", None
        if self._work_area_service is None:
            return False, "Work area service unavailable", None
        points = self._work_area_service.get_work_area(area_type)
        if not points:
            return True, f"No saved points for {area_type}", None
        width = float(self.camera_settings.get_camera_width())
        height = float(self.camera_settings.get_camera_height())
        pixel_points = [(x * width, y * height) for x, y in points]
        return True, f"Work area points retrieved for {area_type}", pixel_points

    # ── Threshold ─────────────────────────────────────────────────────────────

    def on_threshold_update(self, message) -> None:
        self._active_area_id = str(message.get("region", "") or "")
        if self._work_area_service is None:
            return
        try:
            self._work_area_service.set_active_area_id(message.get("region", ""))
        except KeyError as exc:
            _logger.warning("Ignoring invalid active work area update: %s", exc)

    def _get_thresh_by_area(self, area: str) -> int:
        definition = (
            self._work_area_service.get_area_definition(area)
            if self._work_area_service is not None and area
            else None
        )
        profile = definition.threshold_profile if definition is not None else "default"
        if profile == "pickup":
            return self.camera_settings.get_threshold_pickup_area()
        return self.camera_settings.get_threshold()

    def get_thresh_by_area(self, area: str) -> int:
        return self._get_thresh_by_area(area)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start_system(self) -> None:
        self.stop_signal  = False
        self.cameraThread = threading.Thread(target=self._loop, name="_loop", daemon=True)
        self.cameraThread.start()

    def stop_system(self) -> None:
        _logger.info("Stopping VisionSystem...")
        self.stop_signal = True
        self.camera.stop_stream()
        self.camera.stopCapture()
        if self.cameraThread is not None:
            self.cameraThread.join()

    def _loop(self) -> None:
        while not self.stop_signal:
            self.run()

    def _get_area_points_by_region(self, area: str):
        if self._work_area_service is None or not area:
            return None
        return self._work_area_service.get_detection_roi_pixels(
            area,
            self.camera_settings.get_camera_width(),
            self.camera_settings.get_camera_height(),
        )

    def _get_active_brightness_area_points(self):
        active_area = self._get_active_area_id()
        if self._work_area_service is None or not active_area:
            return None
        return self._work_area_service.get_brightness_roi_pixels(
            active_area,
            self.camera_settings.get_camera_width(),
            self.camera_settings.get_camera_height(),
        )

    def _get_active_area_id(self) -> str:
        if self._work_area_service is not None:
            active = self._work_area_service.get_active_area_id()
            if active:
                self._active_area_id = active
        return str(self._active_area_id or "")
