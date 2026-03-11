import logging
from typing import List, Optional, Tuple

import numpy as np

from src.applications.pick_target.service.i_pick_target_service import IPickTargetService

_logger = logging.getLogger(__name__)


class StubPickTargetService(IPickTargetService):

    def capture(self) -> Tuple[Optional[np.ndarray], List[Tuple[float, float]], List[Tuple[float, float]]]:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        pixel_centroids = [(160.0, 240.0), (320.0, 240.0), (480.0, 240.0)]
        robot_centroids = [(-250.0, 420.0), (-150.0, 380.0), (-50.0, 400.0)]
        return frame, pixel_centroids, robot_centroids

    def move_to(self, robot_x: float, robot_y: float) -> bool:
        _logger.info("[Stub] move_to(%.1f, %.1f)", robot_x, robot_y)
        return True

    def move_to_calibration_position(self) -> bool:
        _logger.info("[Stub] move_to_calibration_position")
        return True

    def set_use_tcp(self, enabled: bool) -> None:
        _logger.info("[Stub] set_use_tcp(%s)", enabled)
