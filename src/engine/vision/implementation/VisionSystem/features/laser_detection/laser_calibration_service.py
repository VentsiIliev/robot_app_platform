import logging
import time

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import PolynomialFeatures

from core.services.robot_service.impl.base_robot_service import RobotService
from modules.VisionSystem.laser_detection.config import LaserCalibrationConfig
from modules.VisionSystem.laser_detection.storage import LaserCalibrationStorage

_logger = logging.getLogger(__name__)


class LaserDetectionCalibration:
    def __init__(
            self,
            laser_service,
            robot_service: RobotService,
            config: LaserCalibrationConfig = None,
            storage: LaserCalibrationStorage = None
    ):
        """
        Initialize laser calibration service.

        Args:
            laser_service: LaserDetectionService instance
            robot_service: RobotService instance
            config: LaserCalibrationConfig instance (uses default if None)
            storage: LaserCalibrationStorage instance (creates new if None)
        """
        self.laser_service = laser_service
        self.robot_service = robot_service
        self.config = config if config is not None else LaserCalibrationConfig()
        self.storage = storage if storage is not None else LaserCalibrationStorage()

        self.zero_reference_coords = None
        self.calibration_data = []  # list of tuples holding actual delta in mm -> detected pixel delta
        self.poly_model = None
        self.poly_transform = None
        self.poly_degree = None
        self.robot_initial_position = None
        self.prev_reading = None

    def print_calibration_data(self):
        for i, entry in enumerate(self.calibration_data, start=1):
            _logger.info(f"{i}. [{entry}]")


    def move_to_initial_position(self, position):
        """Move robot to initial calibration position using config values."""
        self.robot_service.robot.move_liner(position = position,
                                            vel = self.config.calibration_velocity,
                                            acc = self.config.calibration_acceleration,
                                            tool = self.robot_service.robot_config.robot_tool,
                                            user = self.robot_service.robot_config.robot_user,
                                            blendR=0)
        # self.robot_service.move_to_position(
        #     position=position,
        #     tool=self.robot_service.robot_config.robot_tool,
        #     workpiece=self.robot_service.robot_config.robot_user,
        #     velocity=self.config.calibration_velocity,
        #     acceleration=self.config.calibration_acceleration,
        #     waitToReachPosition=False
        # )
        self.robot_service._waitForRobotToReachPosition(
            position,
            threshold=self.config.movement_threshold,
            delay=0,
            timeout=self.config.movement_timeout
        )
        return True

    def check_min_safety_limit(self):
        current_pos = self.robot_service.get_current_position()
        if current_pos is None:
            _logger.error("[ERROR] Unable to get current robot position.")

            return False
        min_z = self.robot_service.robot_config.robot_calibration_settings.min_safety_z_mm
        if current_pos[2] <= min_z:
            _logger.error(f"[ERROR] Current Z position {current_pos[2]}mm is at or below minimum safety limit of {min_z}mm.")

            return False
        return True

    def move_down_by_mm(self, mm):
        """Move robot down by specified mm using config values."""
        current_pos = self.robot_service.get_current_position()
        if current_pos is None:
            _logger.error("[ERROR] Unable to get current robot position.")

            return False
        new_pos = current_pos.copy()
        new_pos[2] -= mm  # assuming Z axis is at index 2
        self.robot_service.move_to_position(
            position=new_pos,
            tool=self.robot_service.robot_config.robot_tool,
            workpiece=self.robot_service.robot_config.robot_user,
            velocity=self.config.calibration_velocity,
            acceleration=self.config.calibration_acceleration,
            waitToReachPosition=False
        )
        self.robot_service._waitForRobotToReachPosition(
            new_pos,
            threshold=self.config.movement_threshold,
            delay=0,
            timeout=self.config.movement_timeout
        )
        return True

    def calibrate(self, initial_position):
        """
        Run laser calibration process.

        Args:
            initial_position: Initial robot position for calibration
            iterations: Number of calibration steps (uses config default if None)
            step_mm: Step size in mm (uses config default if None)
            delay_between_move_detect_ms: Delay between move and detect (uses config default if None)

        Returns:
            bool: True if successful, False otherwise
        """
        # Use config defaults if not specified
        iterations = self.config.num_iterations
        step_mm = self.config.step_size_mm
        delay_between_move_detect_ms = self.config.delay_between_move_detect_ms
        self.move_to_initial_position(initial_position)
        self.robot_initial_position = initial_position
        time.sleep(delay_between_move_detect_ms / 1000.0)
        mask, bright, closest = self.laser_service.detect()
        self.zero_reference_coords = closest
        if self.zero_reference_coords is None:
            _logger.error("[ERROR] Laser line not detected at initial position.")

            return False

        # add the zero point to the calibration data
        self.calibration_data.append((0, 0.0))  # height in mm, delta in pixels

        for i in range(1, iterations + 1):
            # move down the robot by step provided in mm
            self.move_down_by_mm(step_mm)
            time.sleep(delay_between_move_detect_ms / 1000.0)

            max_attempts = self.config.calibration_max_attempts
            while max_attempts > 0:
                mask, bright, closest = self.laser_service.detect()
                if closest is None:
                    _logger.warning(f"[WARN] Laser line not detected at iteration {i}. Skipping.")

                    continue

                delta_pixels = self.zero_reference_coords[0] - closest[0]  # X-axis delta
                if delta_pixels > 0:
                    max_attempts -= 1
                    continue

                if self.prev_reading is not None and delta_pixels > self.prev_reading:
                    _logger.warning(f"[WARN] Detected delta {delta_pixels} pixels is greater than previous reading {self.prev_reading} pixels. Retrying.")

                    max_attempts -= 1
                    self.prev_reading = delta_pixels
                    continue

                self.prev_reading = delta_pixels
                current_height = i * step_mm  # assuming Z axis is at index 2
                self.calibration_data.append((current_height, delta_pixels))
                _logger.info(f"[INFO] Captured calibration point: Height={current_height}mm, Delta={delta_pixels} pixels")

                max_attempts = 0

        self.pick_best_polynomial_fit(
            max_degree=self.config.max_polynomial_degree,
            save_filename="laser_calibration.json"
        )
        return True

    def save_calibration(self, filename="laser_calibration.json"):
        # Convert numpy types to Python native types for JSON serialization
        data_to_save = {
            "zero_reference_coords": [float(x) for x in
                                      self.zero_reference_coords] if self.zero_reference_coords is not None else None,
            "calibration_data": [(float(h), float(d)) for h, d in self.calibration_data],
            "robot_initial_position": [float(x) for x in
                                       self.robot_initial_position] if self.robot_initial_position is not None else None
        }

        if self.poly_model is not None:
            data_to_save["polynomial"] = {
                "coefficients": [float(c) for c in self.poly_model.coef_],
                "intercept": float(self.poly_model.intercept_),
                "degree": int(self.poly_degree),
                "mse": float(self.poly_mse)
            }

        return self.storage.save_calibration(data_to_save, filename)

    def pick_best_polynomial_fit(self, max_degree=None, save_filename=None):
        """
        Automatically pick the best polynomial degree for pixel_delta -> height mapping
        using cross-validated MSE (much more stable than R²).

        Args:
            max_degree: Maximum polynomial degree to test (uses config default if None)
            save_filename: Filename to save calibration (saves if not None)
        """

        # Use config default if not specified
        max_degree = max_degree if max_degree is not None else self.config.max_polynomial_degree

        if not self.calibration_data or len(self.calibration_data) < 3:
            _logger.warning("[WARN] Not enough calibration data to fit a model.")

            return None

        # Extract arrays
        heights = np.array([h for h, d in self.calibration_data])
        deltas = np.array([d for h, d in self.calibration_data]).reshape(-1, 1)

        best_mse = np.inf
        best_degree = 1
        best_model = None
        best_poly = None

        _logger.info("[INFO] Evaluating polynomial degrees...")


        for degree in range(1, max_degree + 1):
            # Create polynomial transform
            poly = PolynomialFeatures(degree)
            X_poly = poly.fit_transform(deltas)

            # Regression model
            model = LinearRegression()

            # 5-fold cross-validation MSE
            scores = cross_val_score(
                model,
                X_poly,
                heights,
                scoring='neg_mean_squared_error',
                cv=5
            )
            mse = -scores.mean()

            _logger.info(f"   Degree {degree}: CV-MSE = {mse:.6f}")


            # Select best (lowest MSE)
            if mse < best_mse:
                best_mse = mse
                best_degree = degree
                best_model = model
                best_poly = poly

            # Fit model now that it’s selected (we keep the final one)
            best_model.fit(best_poly.fit_transform(deltas), heights)

        # Save results
        self.poly_model = best_model
        self.poly_transform = best_poly
        self.poly_degree = best_degree
        self.poly_mse = best_mse

        _logger.info(f"[INFO] Best polynomial degree = {best_degree}  (CV-MSE={best_mse:.6f})")


        # Save to file if requested
        if save_filename:
            self.save_calibration(save_filename)
