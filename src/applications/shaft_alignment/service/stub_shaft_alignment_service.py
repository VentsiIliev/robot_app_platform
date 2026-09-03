from __future__ import annotations

import math
import time
from dataclasses import replace

import numpy as np

from src.applications.shaft_alignment.service.i_shaft_alignment_service import (
    AlignmentSnapshot,
    AlignmentThresholds,
    IShaftAlignmentService,
)
from src.applications.shaft_alignment.settings.shaft_alignment_settings import ShaftAlignmentSettings


class StubShaftAlignmentService(IShaftAlignmentService):
    """Animated standalone backend for developing the application without hardware."""

    def __init__(self) -> None:
        self._running = False
        self._thresholds = AlignmentThresholds()
        self._capture_required = 0
        self._capture_started = 0.0
        self._reference_available = False
        self._region = None
        self._settings = ShaftAlignmentSettings()
        self._check_sample_count = 0
        self._restore_settings_state()

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def set_detection_region(self, left, top, right, bottom) -> None:
        self._region = (float(left), float(top), float(right), float(bottom))
        self._settings = replace(self._settings, detection_region_normalized=self._region)

    def clear_detection_region(self) -> None:
        self._region = None
        self._settings = replace(self._settings, detection_region_normalized=None)

    def capture_reference(self, sample_count: int) -> None:
        self._capture_required = max(1, int(sample_count))
        self._capture_started = time.monotonic()
        self._reference_available = False
        self._check_sample_count = 0
        self._settings = replace(
            self._settings,
            reference_tcp_x_mm=None,
            reference_tcp_y_mm=None,
            reference_orientation_deg=None,
            reference_marker_width_mm=None,
            reference_marker_height_mm=None,
            reference_marker_corners_normalized=None,
        )

    def set_thresholds(self, thresholds: AlignmentThresholds) -> None:
        self._thresholds = thresholds
        self._settings = replace(
            self._settings,
            misalignment_dx_threshold_mm=thresholds.dx_mm,
            misalignment_dy_threshold_mm=thresholds.dy_mm,
            misalignment_drz_threshold_deg=thresholds.drz_deg,
            misalignment_dw_threshold_mm=thresholds.dw_mm,
            misalignment_dh_threshold_mm=thresholds.dh_mm,
        )

    def get_settings(self) -> ShaftAlignmentSettings:
        return self._settings

    def save_settings(self, settings: ShaftAlignmentSettings) -> None:
        settings.validate()
        self._settings = settings
        self._restore_settings_state()

    def check_alignment(self) -> bool:
        snapshot = self.get_snapshot()
        return bool(
            snapshot.reference_available
            and snapshot.detected
            and snapshot.dx_mm is not None
            and self._check_sample_count >= self._settings.alignment_check_samples
            and not snapshot.misaligned
        )

    def get_snapshot(self) -> AlignmentSnapshot:
        frame = np.full((720, 1280, 3), (248, 249, 250), dtype=np.uint8)
        if not self._running:
            return AlignmentSnapshot(frame=frame, message="Detection stopped")
        elapsed = time.monotonic()
        dx = 0.65 * math.sin(elapsed * 0.7)
        dy = 0.45 * math.cos(elapsed * 0.6)
        drz = 0.8 * math.sin(elapsed * 0.5)
        dw = 0.25 * math.sin(elapsed * 0.4)
        dh = 0.2 * math.cos(elapsed * 0.45)
        captured = min(
            self._capture_required,
            int((elapsed - self._capture_started) * 10),
        ) if self._capture_required else 0
        capturing = bool(self._capture_required and captured < self._capture_required)
        if self._capture_required and not capturing:
            self._reference_available = True
            if self._settings.reference_tcp_x_mm is None:
                self._settings = replace(
                    self._settings,
                    reference_tcp_x_mm=257.75,
                    reference_tcp_y_mm=215.7,
                    reference_orientation_deg=0.0,
                    reference_marker_width_mm=11.0,
                    reference_marker_height_mm=11.0,
                    reference_marker_corners_normalized=(
                        (0.46, 0.42), (0.54, 0.42),
                        (0.54, 0.56), (0.46, 0.56),
                    ),
                )
        if self._reference_available and not capturing:
            self._check_sample_count = min(
                self._settings.alignment_check_samples,
                self._check_sample_count + 1,
            )
        exceeded = tuple(
            name for name, value, limit in (
                ("dX", dx, self._thresholds.dx_mm),
                ("dY", dy, self._thresholds.dy_mm),
                ("dRZ", drz, self._thresholds.drz_deg),
                ("dW", dw, self._thresholds.dw_mm),
                ("dH", dh, self._thresholds.dh_mm),
            ) if self._reference_available and abs(value) > limit
        )
        return AlignmentSnapshot(
            frame=frame,
            running=True,
            detected=True,
            marker_id=2,
            marker_corners_normalized=((0.46, 0.42), (0.54, 0.42), (0.54, 0.56), (0.46, 0.56)),
            reference_marker_corners_normalized=(
                self._settings.reference_marker_corners_normalized or ()
            ),
            detection_region_normalized=self._region,
            tcp_x_mm=257.75 + dx,
            tcp_y_mm=215.7 + dy,
            orientation_deg=drz,
            marker_width_mm=11.0 + dw,
            marker_height_mm=11.0 + dh,
            reference_tcp_x_mm=self._settings.reference_tcp_x_mm,
            reference_tcp_y_mm=self._settings.reference_tcp_y_mm,
            reference_orientation_deg=self._settings.reference_orientation_deg,
            reference_marker_width_mm=self._settings.reference_marker_width_mm,
            reference_marker_height_mm=self._settings.reference_marker_height_mm,
            dx_mm=dx if self._reference_available else None,
            dy_mm=dy if self._reference_available else None,
            drz_deg=drz if self._reference_available else None,
            dw_mm=dw if self._reference_available else None,
            dh_mm=dh if self._reference_available else None,
            reference_capturing=capturing,
            reference_samples=captured,
            reference_samples_required=self._capture_required,
            reference_available=self._reference_available,
            misaligned=bool(exceeded),
            exceeded_limits=exceeded,
            message="Marker detected",
        )

    def _restore_settings_state(self) -> None:
        self._region = self._settings.detection_region_normalized
        self._reference_available = self._settings.reference_tcp_x_mm is not None
