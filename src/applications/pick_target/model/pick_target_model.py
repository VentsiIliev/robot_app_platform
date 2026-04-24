from typing import List, Optional, Tuple

import numpy as np

from src.applications.base.i_application_model import IApplicationModel
from src.applications.pick_target.service.i_pick_target_service import IPickTargetService


class PickTargetModel(IApplicationModel):

    def __init__(self, service: IPickTargetService):
        self._service = service

    def load(self) -> None:
        pass

    def save(self, *args, **kwargs) -> None:
        pass

    def capture(self) -> Tuple[Optional[np.ndarray], List[Tuple[float, float]], List[Tuple[float, float, float, float, float, float]]]:
        return self._service.capture()

    def move_to(self, x: float, y: float, z: float, rx: float, ry: float, rz: float) -> bool:
        return self._service.move_to(x, y, z, rx, ry, rz)

    def move_to_base(self, x: float, y: float, rx: float, ry: float, rz: float, z: float | None = None) -> bool:
        return self._service.move_to_base(x, y, rx, ry, rz, z)

    def move_to_with_live_height(self, x: float, y: float, rx: float, ry: float, rz: float, z: float | None = None) -> bool:
        return self._service.move_to_with_live_height(x, y, rx, ry, rz, z)

    def move_to_calibration_position(self) -> bool:
        return self._service.move_to_calibration_position()

    def set_target(self, target: str) -> None:
        self._service.set_target(target)

    def set_use_pickup_plane(self, enabled: bool) -> None:
        self._service.set_use_pickup_plane(enabled)

    def set_pickup_plane_rz(self, rz: float) -> None:
        self._service.set_pickup_plane_rz(rz)

    def capture_contour_trajectory(self) -> List[np.ndarray]:
        return self._service.capture_contour_trajectory()

    def execute_contour_trajectory(
        self,
        contour_robot_pts: List[np.ndarray],
        z: float,
        vel: float,
        acc: float,
    ) -> Tuple[bool, str]:
        return self._service.execute_contour_trajectory(contour_robot_pts, z, vel, acc)
