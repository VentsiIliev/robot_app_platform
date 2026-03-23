from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import numpy as np

RobotPose = Tuple[float, float, float, float, float, float]  # (x, y, z, rx_degrees, ry_degrees, rz_degrees)


class IPickTargetService(ABC):

    @abstractmethod
    def capture(self) -> Tuple[Optional[np.ndarray], List[Tuple[float, float]], List[RobotPose]]:
        """
        Snapshot the current vision state.
        Returns (frame, pixel_centroids [(x_pixels, y_pixels)], robot_targets [(x, y, z, rx_degrees, ry_degrees, rz_degrees)]).
        Each robot target is a complete height-corrected approach pose.
        frame may be None if vision is unavailable.
        """

    @abstractmethod
    def move_to(self, x: float, y: float, z: float, rx: float, ry: float, rz: float) -> bool:
        """Move robot to the given pose. z is the pre-computed height-corrected approach height."""

    @abstractmethod
    def move_to_base(self, x: float, y: float, rx: float, ry: float, rz: float) -> bool:
        """Move robot to (x, y) at base Z with the given orientation — no height correction."""

    @abstractmethod
    def move_to_with_live_height(self, x: float, y: float, rx: float, ry: float, rz: float) -> bool:
        """Move to (x, y) at base Z, measure surface height live, then adjust Z."""

    @abstractmethod
    def move_to_calibration_position(self) -> bool:
        """Move robot to the mode-appropriate start position. Returns success."""

    @abstractmethod
    def set_target(self, target: str) -> None:
        """Select the target reference: camera_center, tool, or gripper."""

    @abstractmethod
    def set_use_pickup_plane(self, enabled: bool) -> None:
        """When True, map transformed points into the pickup plane and use pickup orientation."""

    @abstractmethod
    def set_pickup_plane_rz(self, rz: float) -> None:
        """Set the pickup-plane RZ orientation used for manual testing."""

    @abstractmethod
    def capture_contour_trajectory(self) -> List[np.ndarray]:
        """
        Transform the latest detected contours to robot-space waypoints.
        Returns a list of (N, 2) float32 arrays — one per detected contour.
        Each row is (robot_x, robot_y) in mm.
        """

    @abstractmethod
    def execute_contour_trajectory(
        self,
        contour_robot_pts: List[np.ndarray],
        z: float,
        vel: float,
        acc: float,
    ) -> Tuple[bool, str]:
        """
        Execute a robot trajectory that traces the supplied contour waypoints.
        contour_robot_pts: list of (N, 2) float32 arrays in robot-space mm.
        z: fixed Z height in mm.
        vel / acc: normalised 0–1 speed fraction.
        Returns (success, message).
        """
