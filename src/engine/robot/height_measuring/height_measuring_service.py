import logging
import time
from typing import Optional, List

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

from src.engine.repositories.interfaces.settings_repository import ISettingsRepository
from src.engine.robot.height_measuring.depth_map_data import DepthMapData
from src.engine.robot.height_measuring.i_height_measuring_service import IHeightMeasuringService
from src.engine.robot.height_measuring.laser_calibration_data import LaserCalibrationData
from src.engine.robot.height_measuring.laser_detection_service import LaserDetectionService
from src.engine.robot.height_measuring.settings import HeightMeasuringSettings
from src.engine.robot.interfaces import IRobotService

_logger = logging.getLogger(__name__)


class HeightMeasuringService(IHeightMeasuringService):
    def __init__(
        self,
        laser_service: LaserDetectionService,
        robot_service: IRobotService,
        repository: ISettingsRepository,
        config: Optional[HeightMeasuringSettings] = None,
        tool: int = 0,
        user: int = 0,
        depth_map_repository: Optional[ISettingsRepository] = None,
    ):
        self._laser            = laser_service
        self._robot            = robot_service
        self._repo             = repository
        self._depth_map_repo   = depth_map_repository
        self._config           = config
        self._tool             = tool
        self._user             = user
        self._calib: Optional[LaserCalibrationData] = None
        self._poly_model: Optional[LinearRegression] = None
        self._poly_transform: Optional[PolynomialFeatures] = None
        self._load_calibration()

    def is_calibrated(self) -> bool:
        return self._poly_model is not None

    def get_calibration_data(self) -> Optional[LaserCalibrationData]:
        return self._calib

    def reload_calibration(self) -> None:
        self._load_calibration()

    def save_height_map(self, samples: List[List[float]]) -> None:
        if not samples:
            return
        if self._depth_map_repo is None:
            _logger.warning("save_height_map: no depth_map_repository injected — cannot save depth map")
            return
        data = DepthMapData(points=[list(s) for s in samples])
        self._depth_map_repo.save(data)
        _logger.info("Depth map saved: %d points", len(samples))

    def get_depth_map_data(self) -> Optional[DepthMapData]:
        if self._depth_map_repo is None:
            return None
        try:
            data = self._depth_map_repo.load()
            return data if data.has_data() else None
        except Exception as e:
            _logger.error("Failed to load depth map data: %s", e)
            return None

    def measure_at(self, x: float, y: float) -> Optional[float]:
        if not self.is_calibrated():
            _logger.error("Cannot measure: calibration not loaded")
            return None

        cfg    = self._config
        ref    = self._calib.robot_initial_position
        target = [x, y, ref[2]] + list(ref[3:6])

        self._robot.move_linear(
            position=target,
            tool=self._tool,
            user=self._user,
            velocity=cfg.measurement_velocity,
            acceleration=cfg.measurement_acceleration,
            blendR=0,
            wait_to_reach=True,
        )
        time.sleep(cfg.delay_between_move_detect_ms / 1000.0)

        _, _, closest = self._laser.detect()
        if closest is None:
            _logger.warning("Laser not detected during measurement at (%.2f, %.2f)", x, y)
            return None

        pixel_delta = self._calib.zero_reference_coords[0] - closest[0]
        height_mm   = self._pixel_to_mm(pixel_delta)
        _logger.info(
            "Height at (%.2f, %.2f): %.4f mm  (delta=%.3f px)", x, y, height_mm, pixel_delta
        )
        return height_mm

    def _pixel_to_mm(self, pixel_delta: float) -> float:
        X = self._poly_transform.transform([[pixel_delta]])
        return float(self._poly_model.predict(X)[0])

    def _load_calibration(self) -> None:
        try:
            data = self._repo.load()
            if not data.is_calibrated():
                _logger.info("No calibration data found")
                return
            self._calib         = data
            self._poly_transform = PolynomialFeatures(data.polynomial_degree)
            self._poly_model     = LinearRegression()
            self._poly_model.coef_      = np.array(data.polynomial_coefficients)
            self._poly_model.intercept_ = data.polynomial_intercept
            dummy = np.array([[0.0]])
            self._poly_transform.fit(dummy)
            _logger.info("Calibration loaded: degree=%d, MSE=%.4f", data.polynomial_degree, data.polynomial_mse)
        except Exception as e:
            _logger.error("Failed to load calibration: %s", e)
            self._calib = self._poly_model = self._poly_transform = None

