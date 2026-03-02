import threading
import logging
from typing import Optional

import cv2

from src.engine.vision.implementation.VisionSystem.core.camera.frame_grabber import FrameGrabber
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


_logger = logging.getLogger(__name__)

DEFAULT_STORAGE_PATH = str(get_path_resolver().vision_system_root / 'storage')


class VisionSystem:

    def __init__(self, storage_path=None, messaging_service=None, service=None):
        self.optimal_camera_matrix = None

        self.storage_path      = storage_path or DEFAULT_STORAGE_PATH
        self.service           = service or Service(data_storage_path=self.storage_path)
        self.messaging_service = messaging_service
        self.service_id        = "vision_system"

        self.camera_settings = self.service.loadSettings()
        self.setup_camera()
        self.load_calibration_data()

        # ── Services (no back-references to VisionSystem) ─────────────────────
        self._brightness_service = BrightnessService(self.camera_settings)
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

        # ── Calibration state ─────────────────────────────────────────────────
        self.threshold_by_area = "spray"

        if self.service.isCalibrated:
            self.cameraMatrix = self.service.get_camera_matrix()
            self.cameraDist   = self.service.get_distortion_coefficients()
        else:
            self.cameraMatrix = None
            self.cameraDist   = None

        # ── Frame state ───────────────────────────────────────────────────────
        self.image          = None
        self.rawImage       = None
        self.correctedImage = None
        self.rawMode        = False

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
        self.camera.set_auto_exposure(True)
        self.camera_settings.set_camera_index(camera_index)

    def load_calibration_data(self) -> None:
        self.service.loadPerspectiveMatrix()
        self.service.loadCameraCalibrationData()
        self.service.loadCameraToRobotMatrix()
        self.service.loadWorkAreaPoints()

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
            contours, self.correctedImage, _ = self._contour_service.detect(
                image             = self.image,
                threshold         = self._get_thresh_by_area(self.threshold_by_area),
                is_calibrated     = self.service.isCalibrated,
                correct_image_fn  = self.correctImage,
                spray_area_points = self.service.sprayAreaPoints,
            )
            return contours, self.correctedImage, None

        if not self.service.isCalibrated:
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
            self.service.loadPerspectiveMatrix()
            self.service.loadCameraToRobotMatrix()
            if self.service.cameraData is not None and self.service.cameraToRobotMatrix is not None:
                self.service.isCalibrated = True
            _logger.info("Camera calibration completed and system recalibrated")
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
        return self.service.saveWorkAreaPoints(data)

    def getWorkAreaPoints(self, area_type):
        if not area_type:
            return False, "Area type is required", None
        if area_type not in ('pickup', 'spray', 'work'):
            return False, f"Invalid area_type: {area_type!r}. Must be 'pickup', 'spray', or 'work'", None
        try:
            points = {
                'pickup': self.service.pickupAreaPoints,
                'spray':  self.service.sprayAreaPoints,
                'work':   self.service.workAreaPoints,
            }[area_type]
            if points is not None:
                return True, f"Work area points retrieved for {area_type}", (
                    points.tolist() if hasattr(points, 'tolist') else points
                )
            return True, f"No saved points for {area_type}", None
        except Exception as exc:
            _logger.error("Error loading %s area points: %s", area_type, exc)
            return False, f"Error loading {area_type} area points: {exc}", None

    # ── Threshold ─────────────────────────────────────────────────────────────

    def on_threshold_update(self, message) -> None:
        self.threshold_by_area = message.get("region", "")

    def _get_thresh_by_area(self, area: str) -> int:
        if area == "pickup":
            return self.camera_settings.get_threshold_pickup_area()
        if area == "spray":
            return self.camera_settings.get_threshold()
        raise ValueError(f"Invalid threshold area: {area!r}")

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
