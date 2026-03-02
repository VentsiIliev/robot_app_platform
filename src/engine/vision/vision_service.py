import logging

from src.engine.core.i_health_checkable import IHealthCheckable
from src.engine.vision.i_vision_service import IVisionService


class VisionService(IVisionService, IHealthCheckable):

    def __init__(self, vision_system):
        self._vision_system = vision_system
        self._running = False
        self._logger = logging.getLogger(self.__class__.__name__)

    def start(self) -> None:
        self._vision_system.start_system()
        self._running = True
        self._logger.info("VisionService started")

    def stop(self) -> None:
        self._vision_system.stop_system()
        self._running = False
        self._logger.info("VisionService stopped")

    def set_raw_mode(self, enabled: bool) -> None:
        self._vision_system.rawMode = enabled

    def capture_calibration_image(self) -> tuple[bool, str]:
        return self._vision_system.captureCalibrationImage()

    def calibrate_camera(self) -> tuple[bool, str]:
        return self._vision_system.calibrateCamera()

    def update_settings(self, settings: dict) -> tuple[bool, str]:
        return self._vision_system.updateSettings(settings)

    def is_healthy(self) -> bool:
        if not self._running:
            return False
        state_manager = self._vision_system.state_manager
        if state_manager is None:
            # no messaging wired — fall back to a running flag only
            return self._running
        from src.engine.vision.implementation.VisionSystem.core.external_communication.system_state_management import ServiceState
        return state_manager.state in (ServiceState.IDLE, ServiceState.STARTED)

    def save_work_area(self, area_type: str, pixel_points) -> tuple[bool, str]:
        import numpy as np
        data = {
            "area_type": area_type,
            "corners":   np.array(pixel_points, dtype=np.float32),
        }
        return self._vision_system.saveWorkAreaPoints(data)

    def get_work_area(self, area_type: str) -> tuple[bool, str, any]:
        return self._vision_system.getWorkAreaPoints(area_type)
