import logging
import time
from typing import TYPE_CHECKING, Optional, List

import numpy as np

if TYPE_CHECKING:
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import PolynomialFeatures

from src.engine.repositories.interfaces.settings_repository import ISettingsRepository
from src.engine.robot.height_measuring.depth_map_data import DepthMapData, DepthMapLibraryData
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

    def save_height_map(
        self,
        samples: List[List[float]],
        area_id: str = "",
        marker_ids: Optional[List[int]] = None,
        point_labels: Optional[List[str]] = None,
        grid_rows: int = 0,
        grid_cols: int = 0,
        planned_points: Optional[List[List[float]]] = None,
        planned_point_labels: Optional[List[str]] = None,
        unavailable_point_labels: Optional[List[str]] = None,
    ) -> None:
        if not samples:
            return
        if self._depth_map_repo is None:
            _logger.warning("save_height_map: no depth_map_repository injected — cannot save depth map")
            return
        key = str(area_id or "default")
        data = DepthMapData(
            area_id=key,
            points=[list(s) for s in samples],
            marker_ids=[int(v) for v in marker_ids] if marker_ids else [],
            point_labels=[str(v) for v in point_labels] if point_labels else [],
            grid_rows=int(grid_rows or 0),
            grid_cols=int(grid_cols or 0),
            planned_points=[list(point) for point in planned_points] if planned_points else [],
            planned_point_labels=[str(v) for v in planned_point_labels] if planned_point_labels else [],
            unavailable_point_labels=[str(v) for v in unavailable_point_labels] if unavailable_point_labels else [],
        )
        library = self._load_depth_map_library()
        library.set(key, data)
        self._depth_map_repo.save(library)
        _logger.info("Depth map saved for area '%s': %d points", key, len(samples))

    def get_depth_map_data(self, area_id: str = "") -> Optional[DepthMapData]:
        if self._depth_map_repo is None:
            return None
        try:
            library = self._load_depth_map_library()
            key = str(area_id or "default")
            if key in library.maps:
                data = library.maps[key]
                return data if data.has_data() else None
            for data in library.maps.values():
                if data.has_data():
                    return data
            return None
        except Exception as e:
            _logger.error("Failed to load depth map data: %s", e)
            return None

    def _load_depth_map_library(self) -> DepthMapLibraryData:
        if self._depth_map_repo is None:
            return DepthMapLibraryData()
        data = self._depth_map_repo.load()
        if isinstance(data, DepthMapLibraryData):
            return data
        if isinstance(data, DepthMapData):
            key = str(data.area_id or "default")
            return DepthMapLibraryData(maps={key: data})
        return DepthMapLibraryData()

    def begin_measurement_session(self) -> None:
        self._laser.begin_measurement_session()

    def end_measurement_session(self) -> None:
        self._laser.end_measurement_session()

    def measure_at(self, x: float, y: float, *, already_at_xy: bool = False) -> Optional[float]:
        if not self.is_calibrated():
            _logger.error("Cannot measure: calibration not loaded")
            return None

        cfg    = self._config
        ref    = self._calib.robot_initial_position
        if not already_at_xy:
            target = [x, y, ref[2]] + list(ref[3:6])
            moved = self._robot.move_linear(
                position=target,
                tool=self._tool,
                user=self._user,
                velocity=cfg.measurement_velocity,
                acceleration=cfg.measurement_acceleration,
                blendR=0,
                wait_to_reach=True,
            )
            if not moved:
                _logger.warning("Failed to move to measurement point (%.2f, %.2f)", x, y)
                return None
        time.sleep(cfg.delay_between_move_detect_ms / 1000.0)

        _, _, closest = self._laser.detect()
        if closest is None:
            _logger.warning("Laser not detected during measurement at (%.2f, %.2f)", x, y)
            return None

        pixel_delta = self._calib.zero_reference_coords[0] - closest[0]
        raw_height_mm = self._pixel_to_mm(pixel_delta)
        height_mm = raw_height_mm - float(getattr(self._calib, "zero_height_offset_mm", 0.0))
        _logger.info(
            "Height at (%.2f, %.2f): %.4f mm  (raw=%.4f mm, zero_offset=%.4f mm, delta=%.3f x_pixels)",
            x,
            y,
            height_mm,
            raw_height_mm,
            float(getattr(self._calib, "zero_height_offset_mm", 0.0)),
            pixel_delta,
        )
        return height_mm

    def _pixel_to_mm(self, pixel_delta: float) -> float:
        X = self._poly_transform.transform([[pixel_delta]])
        return float(self._poly_model.predict(X)[0])

    def _load_calibration(self) -> None:
        try:
            from sklearn.linear_model import LinearRegression  # lazy import — sklearn not always available
            from sklearn.preprocessing import PolynomialFeatures

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
