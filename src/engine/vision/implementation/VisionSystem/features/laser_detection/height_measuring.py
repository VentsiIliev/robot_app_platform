import logging
import time

import numpy as np
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import LinearRegression
from core.services.robot_service.impl.base_robot_service import RobotService
from modules.VisionSystem.laser_detection.laser_detection_service import LaserDetectionService
from modules.VisionSystem.laser_detection.config import HeightMeasuringConfig
from modules.VisionSystem.laser_detection.storage import LaserCalibrationStorage

_logger = logging.getLogger(__name__)


class HeightMeasuringService:
    def __init__(
        self,
        laser_detection_service: LaserDetectionService,
        robot_service: RobotService,
        config: HeightMeasuringConfig = None,
        storage: LaserCalibrationStorage = None,
        calibration_filename=None
    ):
        """
        Initialize height measuring service.

        Args:
            laser_detection_service: LaserDetectionService instance
            robot_service: RobotService instance
            config: HeightMeasuringConfig instance (uses default if None)
            storage: LaserCalibrationStorage instance (creates new if None)
            calibration_filename: Name of calibration file (uses config default if None)
        """
        self.laser_detection_service = laser_detection_service
        self.robot_service = robot_service
        self.config = config if config is not None else HeightMeasuringConfig()
        self.storage = storage if storage is not None else LaserCalibrationStorage()

        # Use config default calibration filename if not provided
        self.calibration_filename = calibration_filename if calibration_filename is not None else self.config.calibration_filename

        self.poly_model = None
        self.poly_transform = None
        self.poly_degree = None
        self.mse = None
        self.zero_reference_z = None  # Z position of the reference plane
        self.reference_xy = None      # XY position used during calibration
        self.zero_reference_coords = None  # Pixel coordinates of the zero reference
        self.load_calibration_curve()

    def load_calibration_curve(self):
        """
        Loads calibration data and polynomial model from storage service.
        """
        try:
            # Use storage service to load calibration
            data = self.storage.load_calibration(self.calibration_filename)

            if data is None:
                raise ValueError(f"Calibration file '{self.calibration_filename}' not found")

            poly_data = data.get("polynomial")
            if not poly_data:
                raise ValueError("No polynomial data found in calibration file.")

            # Reconstruct the polynomial model
            self.poly_degree = poly_data["degree"]
            self.mse = poly_data["mse"]

            self.poly_transform = PolynomialFeatures(self.poly_degree)
            self.poly_model = LinearRegression()
            self.poly_model.coef_ = np.array(poly_data["coefficients"])
            self.poly_model.intercept_ = poly_data["intercept"]

            # Load zero-reference coordinates (pixel position)
            self.zero_reference_coords = data.get("zero_reference_coords", None)

            # Load robot initial position [X, Y, Z, RX, RY, RZ]
            robot_initial_pos = data.get("robot_initial_position", None)
            if robot_initial_pos:
                self.zero_reference_z = robot_initial_pos[2]  # Z coordinate
                self.reference_xy = [robot_initial_pos[0], robot_initial_pos[1]]  # X, Y coordinates
                _logger.info(f"[HeightMeasuring] Zero reference Z: {self.zero_reference_z} mm")

                _logger.info(f"[HeightMeasuring] Reference XY: {self.reference_xy}")

            else:
                _logger.info("[HeightMeasuring] No robot_initial_position found in calibration file.")


            _logger.info(f"[HeightMeasuring] Calibration loaded: degree={self.poly_degree}, mes={self.mse:.4f}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            _logger.error(f"[HeightMeasuring] Failed to load calibration: {e}")

            self.poly_model = None
            self.poly_transform = None

    def pixel_to_mm(self, pixel_delta):
        """
        Query the height in mm from a pixel delta using the loaded polynomial model.
        """
        if self.poly_model is None or self.poly_transform is None:
            raise RuntimeError("Polynomial model not loaded. Call load_calibration_curve() first.")

        X = self.poly_transform.fit_transform([[pixel_delta]])
        return float(self.poly_model.predict(X))

    def move_to(self, x=None, y=None, wait=True):
        """
        Move the robot to the given X, Y (or reference XY if None) while keeping Z at the zero reference height.
        Uses config values for movement parameters.
        """
        if self.zero_reference_z is None:
            raise RuntimeError("Zero reference Z not set. Cannot move safely.")

        if x is None or y is None:
            if self.reference_xy is None:
                raise RuntimeError("Reference XY position not set.")
            x, y = self.reference_xy

        # Keep current robot orientation (RX, RY, RZ)
        current_pos = self.robot_service.get_current_position()
        if current_pos is None:
            raise RuntimeError("Cannot get current robot position.")

        target_pos_full = [x, y, self.zero_reference_z] + [180 ,0,0]  # Assuming fixed orientation
        self.robot_service.move_to_position(
            position=target_pos_full,
            tool=self.robot_service.robot_config.robot_tool,
            workpiece=self.robot_service.robot_config.robot_user,
            velocity=self.config.measurement_velocity,
            acceleration=self.config.measurement_acceleration,
            waitToReachPosition=wait
        )
        if wait:
            self.robot_service._waitForRobotToReachPosition(
                target_pos_full,
                threshold=self.config.measurement_threshold,
                delay=0,
                timeout=self.config.measurement_timeout
            )

    def measure_at(self, x=None, y=None):
        """
        Move to XY (or reference XY if None) and measure the laser height in mm.
        Uses config values for measurement parameters.
        """
        # Move robot to XY
        self.move_to(x, y, wait=True)
        time.sleep(self.config.delay_between_move_detect_ms/1000.0)

        # Detect laser line using config values
        mask, bright, closest = self.laser_detection_service.detect()
        if closest is None:
            _logger.warning("[WARN] Laser line not detected.")

            return None

        pixel_delta = self.zero_reference_coords[0] - closest[0]

        height_mm = self.pixel_to_mm(pixel_delta)

        _logger.info(f"[INFO] Zero reference pixel X: {self.zero_reference_coords[0]:.2f}")

        _logger.info(f"[INFO] Current detection pixel X: {closest[0]:.2f}")

        _logger.info(f"[INFO] Pixel delta: {pixel_delta:.2f}")

        _logger.info(f"[INFO] Calculated height: {height_mm:.4f} mm")


        return height_mm,pixel_delta
