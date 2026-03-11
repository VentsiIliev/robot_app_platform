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

    def capture(self) -> Tuple[Optional[np.ndarray], List[Tuple[float, float]], List[Tuple[float, float]]]:
        return self._service.capture()

    def move_to(self, robot_x: float, robot_y: float) -> bool:
        return self._service.move_to(robot_x, robot_y)

    def move_to_calibration_position(self) -> bool:
        return self._service.move_to_calibration_position()

    def set_use_tcp(self, enabled: bool) -> None:
        self._service.set_use_tcp(enabled)
