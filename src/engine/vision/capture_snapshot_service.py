from __future__ import annotations

import logging
import time
from typing import Optional

from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.vision.i_capture_snapshot_service import (
    ICaptureSnapshotService,
    VisionCaptureSnapshot,
)
from src.engine.vision.i_vision_service import IVisionService

_logger = logging.getLogger(__name__)


class CaptureSnapshotService(ICaptureSnapshotService):
    """Capture the latest vision data and robot pose as one runtime snapshot."""

    def __init__(
        self,
        vision_service: Optional[IVisionService],
        robot_service: Optional[IRobotService],
    ) -> None:
        self._vision = vision_service
        self._robot = robot_service

    def capture_snapshot(self, source: str = "") -> VisionCaptureSnapshot:
        frame = None
        contours = []
        robot_pose = None

        if self._vision is not None:
            try:
                frame = self._vision.get_latest_frame()
            except Exception:
                _logger.exception("Failed to capture latest frame for source=%s", source)
            try:
                contours = list(self._vision.get_latest_contours())
            except Exception:
                _logger.exception("Failed to capture latest contours for source=%s", source)

        if self._robot is not None:
            try:
                robot_pose = list(self._robot.get_current_position())
            except Exception:
                _logger.exception("Failed to capture robot pose for source=%s", source)

        return VisionCaptureSnapshot(
            frame=frame,
            contours=contours,
            robot_pose=robot_pose,
            timestamp_s=time.time(),
            source=source,
        )
