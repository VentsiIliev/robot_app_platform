import logging
from typing import List, Optional, Tuple

import numpy as np

from src.applications.pick_target.service.i_pick_target_service import IPickTargetService

_logger = logging.getLogger(__name__)


class StubPickTargetService(IPickTargetService):
    def __init__(self):
        self._target = "camera_center"
        self._use_pickup_plane = False
        self._pickup_plane_rz = 90.0

    def capture(self) -> Tuple[Optional[np.ndarray], List[Tuple[float, float]], List[Tuple[float, float, float, float, float, float]]]:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        pixel_centroids = [(160.0, 240.0), (320.0, 240.0), (480.0, 240.0)]
        robot_targets   = [
            (-250.0, 420.0, 300.0, 180.0, 0.0, 90.0),
            (-150.0, 380.0, 300.0, 180.0, 0.0, 90.0),
            (-50.0,  400.0, 300.0, 180.0, 0.0, 90.0),
        ]
        return frame, pixel_centroids, robot_targets

    def move_to(self, x: float, y: float, z: float, rx: float, ry: float, rz: float) -> bool:
        _logger.info("[Stub] move_to(%.1f, %.1f, %.1f, rx_degrees=%.1f, ry_degrees=%.1f, rz_degrees=%.1f)", x, y, z, rx, ry, rz)
        return True

    def move_to_base(self, x: float, y: float, rx: float, ry: float, rz: float) -> bool:
        _logger.info("[Stub] move_to_base(%.1f, %.1f) [no correction]", x, y)
        return True

    def move_to_with_live_height(self, x: float, y: float, rx: float, ry: float, rz: float) -> bool:
        _logger.info("[Stub] move_to_with_live_height(%.1f, %.1f)", x, y)
        return True

    def move_to_calibration_position(self) -> bool:
        target = "HOME" if self._use_pickup_plane else "CALIBRATION"
        _logger.info("[Stub] move_to_start_position(%s)", target)
        return True

    def set_target(self, target: str) -> None:
        self._target = target
        _logger.info("[Stub] set_target(%s)", target)

    def set_use_pickup_plane(self, enabled: bool) -> None:
        self._use_pickup_plane = enabled
        _logger.info("[Stub] set_use_pickup_plane(%s)", enabled)

    def set_pickup_plane_rz(self, rz: float) -> None:
        self._pickup_plane_rz = rz
        _logger.info("[Stub] set_pickup_plane_rz(%.1f)", rz)

    def capture_contour_trajectory(self) -> List[np.ndarray]:
        _logger.info("[Stub] capture_contour_trajectory")
        # Return a simple square contour in robot space
        pts = np.array([[-250, 420], [-200, 420], [-200, 370], [-250, 370], [-250, 420]], dtype=np.float32)
        return [pts]

    def execute_contour_trajectory(
        self,
        contour_robot_pts: List[np.ndarray],
        z: float,
        vel: float,
        acc: float,
    ) -> Tuple[bool, str]:
        total = sum(len(c) for c in contour_robot_pts)
        _logger.info("[Stub] execute_contour_trajectory: %d contour(s), %d waypoints, z=%.1f vel=%.2f acc=%.2f",
                     len(contour_robot_pts), total, z, vel, acc)
        return True, f"Stub: {len(contour_robot_pts)} contour(s), {total} waypoints"
