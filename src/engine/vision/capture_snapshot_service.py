from __future__ import annotations

import logging
import time
from typing import Callable, Optional

from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.work_areas.i_work_area_service import IWorkAreaService
from src.engine.vision.i_capture_snapshot_service import (
    ICaptureSnapshotService,
    VisionCaptureSnapshot,
)
from src.engine.vision.i_vision_service import IVisionService, VisionFrameUnavailableError

_logger = logging.getLogger(__name__)


class ActiveWorkAreaVerificationError(RuntimeError):
    """Raised when a vision capture is blocked by unverified work-area state."""


class CaptureSnapshotService(ICaptureSnapshotService):
    """Capture the latest vision data and robot pose as one runtime snapshot."""

    def __init__(
        self,
        vision_service: Optional[IVisionService],
        robot_service: Optional[IRobotService],
        work_area_service: Optional[IWorkAreaService] = None,
        active_work_area_validator: Optional[
            Callable[[str, Optional[list[float]]], tuple[bool, str]]
        ] = None,
    ) -> None:
        self._vision = vision_service
        self._robot = robot_service
        self._work_area_service = work_area_service
        self._active_work_area_validator = active_work_area_validator

    def capture_snapshot(self, source: str = "") -> VisionCaptureSnapshot:
        started = time.perf_counter()
        frame = None
        contours = []
        robot_pose_started = time.perf_counter()
        robot_pose = self._capture_robot_pose(source)
        robot_pose_elapsed = time.perf_counter() - robot_pose_started

        validate_started = time.perf_counter()
        self._validate_active_work_area(source, robot_pose)
        validate_elapsed = time.perf_counter() - validate_started

        vision_elapsed = 0.0
        if self._vision is not None:
            try:
                vision_started = time.perf_counter()
                frame, contours = self._vision.compute_contours_for_latest_frame()
                vision_elapsed = time.perf_counter() - vision_started
            except VisionFrameUnavailableError:
                _logger.error("Fresh vision frame unavailable for source=%s", source, exc_info=True)
                raise
            except Exception:
                _logger.exception("Failed to capture latest vision snapshot for source=%s", source)
                fallback_started = time.perf_counter()
                try:
                    frame = self._vision.get_latest_frame()
                except Exception:
                    _logger.exception("Failed to capture latest frame fallback for source=%s", source)
                try:
                    contours = list(self._vision.get_latest_contours())
                except Exception:
                    _logger.exception("Failed to capture latest contours fallback for source=%s", source)
                vision_elapsed = time.perf_counter() - fallback_started

        contour_count = len(contours or [])
        _logger.info(
            "[CAPTURE_TIMING] source=%s robot_pose_s=%.3f active_area_validate_s=%.3f "
            "vision_contours_s=%.3f total_s=%.3f contours=%d frame_available=%s",
            source,
            robot_pose_elapsed,
            validate_elapsed,
            vision_elapsed,
            time.perf_counter() - started,
            contour_count,
            frame is not None,
        )

        return VisionCaptureSnapshot(
            frame=frame,
            contours=contours,
            robot_pose=robot_pose,
            timestamp_s=time.time(),
            source=source,
        )

    def _capture_robot_pose(self, source: str) -> Optional[list[float]]:
        if self._robot is None:
            return None
        try:
            return list(self._robot.get_current_position())
        except Exception:
            _logger.exception("Failed to capture robot pose for source=%s", source)
            return None

    def _validate_active_work_area(
        self,
        source: str,
        robot_pose: Optional[list[float]],
    ) -> None:
        if self._work_area_service is None or self._active_work_area_validator is None:
            return
        try:
            active_area_id = str(self._work_area_service.get_active_area_id() or "").strip()
        except Exception as exc:
            raise ActiveWorkAreaVerificationError(
                "Cannot verify active work area before vision capture."
            ) from exc
        if not active_area_id:
            raise ActiveWorkAreaVerificationError(
                "Active work area is unknown. Move the robot to a declared capture position before capturing."
            )
        is_verified = getattr(self._work_area_service, "is_active_area_verified", None)
        if callable(is_verified) and not bool(is_verified()):
            raise ActiveWorkAreaVerificationError(
                f"Active work area '{active_area_id}' is not verified. "
                "Move the robot to the capture position from the platform before capturing."
            )
        ok, message = self._active_work_area_validator(active_area_id, robot_pose)
        if not ok:
            detail = message or f"Robot is not verified at active work area '{active_area_id}'."
            raise ActiveWorkAreaVerificationError(
                f"Vision capture blocked for {source or 'unknown source'}: {detail}"
            )
