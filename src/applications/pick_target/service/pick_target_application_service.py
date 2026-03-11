import logging
from typing import List, Optional, Tuple

import numpy as np

from src.applications.pick_target.service.i_pick_target_service import IPickTargetService
from src.engine.core.i_coordinate_transformer import ICoordinateTransformer
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.vision.i_vision_service import IVisionService
from src.engine.vision.implementation.VisionSystem.core.models.contour import Contour

_logger = logging.getLogger(__name__)

_Z = 300.0


class PickTargetApplicationService(IPickTargetService):

    def __init__(
        self,
        vision_service:  Optional[IVisionService],
        robot_service:   Optional[IRobotService],
        transformer:     Optional[ICoordinateTransformer],
        robot_config=None,
        navigation=None,
    ):
        self._vision        = vision_service
        self._robot         = robot_service
        self._transformer   = transformer
        self._robot_config  = robot_config
        self._navigation    = navigation
        self._use_tcp       = False

    def set_use_tcp(self, enabled: bool) -> None:
        self._use_tcp = enabled

    def _tool(self) -> int:
        return self._robot_config.robot_tool if self._robot_config else 0

    def _user(self) -> int:
        return self._robot_config.robot_user if self._robot_config else 0

    def capture(self) -> Tuple[Optional[np.ndarray], List[Tuple[float, float]], List[Tuple[float, float]]]:
        if self._vision is None:
            _logger.warning("Vision service not available")
            return None, [], []

        frame = self._vision.get_latest_frame()
        raw_contours = self._vision.get_latest_contours()

        pixel_centroids: List[Tuple[float, float]] = []
        robot_centroids: List[Tuple[float, float]] = []

        for raw in raw_contours:
            try:
                cnt = Contour(raw)
                px, py = cnt.getCentroid()
                pixel_centroids.append((px, py))
                if self._transformer is not None:
                    if self._use_tcp:
                        rx, ry = self._transformer.transform_to_tcp(px, py)
                    else:
                        rx, ry = self._transformer.transform(px, py)
                    robot_centroids.append((rx, ry))
            except Exception:
                _logger.exception("Failed to process contour centroid")

        return frame, pixel_centroids, robot_centroids

    def move_to(self, robot_x: float, robot_y: float) -> bool:
        if self._robot is None:
            _logger.warning("Robot service not available — cannot move")
            return False
        try:
            current = self._robot.get_current_position()
            if not current or len(current) < 6:
                _logger.warning("get_current_position returned %s — using default orientation", current)
                rx, ry, rz = 180.0, 0.0, 0.0
            else:
                rx, ry, rz = current[3], current[4], current[5]
            return self._robot.move_ptp(
                [robot_x, robot_y, _Z, rx, ry, rz],
                tool=self._tool(),
                user=self._user(),
                velocity=20,
                acceleration=10,
                wait_to_reach=True,
            )
        except Exception:
            _logger.exception("move_to(%.1f, %.1f) failed", robot_x, robot_y)
            return False

    def move_to_calibration_position(self) -> bool:
        if self._navigation is None:
            _logger.warning("Navigation service not available")
            return False
        try:
            z_offset = self._vision.get_capture_pos_offset() if self._vision is not None else 0.0
            return self._navigation.move_to_calibration_position(z_offset=z_offset)
        except Exception:
            _logger.exception("move_to_calibration_position failed")
            return False

