import logging
import threading
import time
from typing import List, Optional, Tuple

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import PolynomialFeatures

from src.engine.repositories.interfaces.settings_repository import ISettingsRepository
from src.engine.robot.height_measuring.laser_calibration_data import LaserCalibrationData
from src.engine.robot.height_measuring.laser_detection_service import LaserDetectionService
from src.engine.robot.height_measuring.settings import LaserCalibrationSettings
from src.engine.robot.interfaces import IRobotService

_logger = logging.getLogger(__name__)


class LaserCalibrationService:
    def __init__(
        self,
        laser_service: LaserDetectionService,
        robot_service: IRobotService,
        repository: ISettingsRepository,
        config: Optional[LaserCalibrationSettings] = None,
        tool: int = 0,
        user: int = 0,
    ):
        self._laser  = laser_service
        self._robot  = robot_service
        self._repo   = repository
        self._config = config or LaserCalibrationSettings()
        self._tool   = tool
        self._user   = user
        self._data: Optional[LaserCalibrationData] = None

    def get_calibration_data(self) -> Optional[LaserCalibrationData]:
        return self._data

    def calibrate(self, initial_position: Optional[List[float]] = None,stop_event: threading.Event = None) -> bool:
        cfg = self._config
        pos = initial_position or cfg.calibration_initial_position

        self._robot.move_linear(
            position=pos,
            tool=self._tool,
            user=self._user,
            velocity=cfg.calibration_velocity,
            acceleration=cfg.calibration_acceleration,
            blendR=0,
            wait_to_reach=True,
        )
        time.sleep(cfg.delay_between_move_detect_ms / 1000.0)

        _, _, zero_ref = self._laser.detect()
        if zero_ref is None:
            _logger.error("Laser not detected at initial calibration position")
            return False

        _logger.info("Zero reference: %s", zero_ref)
        points: List[Tuple[float, float]] = [(0.0, 0.0)]

        for i in range(1, cfg.num_iterations + 1):

            if stop_event and stop_event.is_set():  # ← cancellation check
                _logger.info("Calibration cancelled at iteration %d", i)
                return False

            current = self._robot.get_current_position()
            if not current:
                _logger.error("Cannot get robot position at iteration %d", i)
                return False

            step_pos = list(current)
            step_pos[2] -= cfg.step_size_mm
            self._robot.move_linear(
                position=step_pos,
                tool=self._tool,
                user=self._user,
                velocity=cfg.calibration_velocity,
                acceleration=cfg.calibration_acceleration,
                blendR=0,
                wait_to_reach=True,
            )
            time.sleep(cfg.delay_between_move_detect_ms / 1000.0)

            for _ in range(cfg.calibration_max_attempts):
                _, _, closest = self._laser.detect()
                if closest is None:
                    _logger.warning("No detection at iteration %d, retrying", i)
                    continue
                delta = zero_ref[0] - closest[0]
                if delta >= 0:
                    continue
                points.append((float(i * cfg.step_size_mm), float(delta)))
                _logger.info(
                    "Point %d: height=%.2f mm, delta=%.3f px", i, i * cfg.step_size_mm, delta
                )
                break

        if len(points) < 3:
            _logger.error("Not enough calibration points (%d); need at least 3", len(points))
            return False

        calib_data = self._fit_polynomial(points, pos, zero_ref)
        self._data = calib_data
        self._repo.save(calib_data)
        _logger.info(
            "Calibration saved: degree=%d, MSE=%.6f", calib_data.polynomial_degree, calib_data.polynomial_mse
        )
        return True

    def _fit_polynomial(
        self,
        points: List[Tuple[float, float]],
        robot_initial_position: List[float],
        zero_ref: Tuple[float, float],
    ) -> LaserCalibrationData:
        heights = np.array([h for h, _ in points])
        deltas  = np.array([d for _, d in points]).reshape(-1, 1)
        cv_folds = min(5, len(points))

        best_mse, best_degree, best_model, best_poly = np.inf, 1, None, None
        for degree in range(1, self._config.max_polynomial_degree + 1):
            poly  = PolynomialFeatures(degree)
            X     = poly.fit_transform(deltas)
            model = LinearRegression()
            scores = cross_val_score(model, X, heights, scoring="neg_mean_squared_error", cv=cv_folds)
            mse = -scores.mean()
            _logger.debug("Degree %d: CV-MSE=%.6f", degree, mse)
            if mse < best_mse:
                best_mse, best_degree, best_model, best_poly = mse, degree, model, poly

        best_model.fit(best_poly.fit_transform(deltas), heights)
        _logger.info("Best polynomial degree=%d, MSE=%.6f", best_degree, best_mse)

        return LaserCalibrationData(
            zero_reference_coords=list(zero_ref),
            robot_initial_position=list(robot_initial_position),
            calibration_points=[[float(h), float(d)] for h, d in points],
            polynomial_coefficients=list(best_model.coef_),
            polynomial_intercept=float(best_model.intercept_),
            polynomial_degree=best_degree,
            polynomial_mse=best_mse,
        )

