import threading
from typing import Callable, List, Optional, Tuple

from src.applications.base.i_application_model import IApplicationModel
from src.applications.aruco_z_probe.service.i_aruco_z_probe_service import (
    ArucoZSample,
    IArucoZProbeService,
)


class ArucoZProbeModel(IApplicationModel):

    def __init__(self, service: IArucoZProbeService):
        self._service = service

    def load(self) -> None:
        pass

    def save(self, *args, **kwargs) -> None:
        pass

    def move_to_calibration_position(self) -> bool:
        return self._service.move_to_calibration_position()

    def run_sweep(
        self,
        marker_id: int,
        min_z: float,
        sample_count: int,
        detection_attempts: int,
        stop_event: threading.Event,
        progress_cb: Callable[[int, int, float, Optional[float], Optional[float]], None],
        log_cb: Optional[Callable[[str], None]] = None,
        stabilization_delay: float = 0.3,
    ) -> Tuple[bool, str, List[ArucoZSample]]:
        return self._service.run_sweep(
            marker_id=marker_id,
            min_z=min_z,
            sample_count=sample_count,
            detection_attempts=detection_attempts,
            stop_event=stop_event,
            progress_cb=progress_cb,
            log_cb=log_cb,
            stabilization_delay=stabilization_delay,
        )

    def run_verification(
        self,
        z_heights: List[float],
        marker_id: int,
        detection_attempts: int,
        stop_event: threading.Event,
        progress_cb: Callable[[int, int, float, Optional[float], Optional[float]], None],
        log_cb: Optional[Callable[[str], None]] = None,
        stabilization_delay: float = 0.3,
    ) -> Tuple[bool, str, List[ArucoZSample]]:
        return self._service.run_verification(
            z_heights=z_heights,
            marker_id=marker_id,
            detection_attempts=detection_attempts,
            stop_event=stop_event,
            progress_cb=progress_cb,
            log_cb=log_cb,
            stabilization_delay=stabilization_delay,
        )
