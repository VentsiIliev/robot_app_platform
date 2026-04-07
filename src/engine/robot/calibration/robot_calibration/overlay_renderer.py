from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import cv2


@dataclass(frozen=True)
class OverlayStatus:
    state_name: str
    target_ids: list[int]
    current_marker_index: int
    iteration_count: int
    max_iterations: int
    alignment_threshold_mm: float
    current_error_mm: float | None = None


class CalibrationRenderer(Protocol):
    def draw_image_center(self, frame) -> None:
        ...

    def render_live_overlay(self, frame, status: OverlayStatus):
        ...


class NoOpCalibrationRenderer:
    def draw_image_center(self, frame) -> None:
        return None

    def render_live_overlay(self, frame, status: OverlayStatus):
        return frame


class OpenCvCalibrationRenderer:
    def draw_image_center(self, frame) -> None:
        if frame is None:
            return
        frame_height, frame_width = frame.shape[:2]
        center_x, center_y = frame_width // 2, frame_height // 2
        color = (255, 0, 0)
        cv2.line(frame, (0, center_y), (frame_width, center_y), color, 1)
        cv2.line(frame, (center_x, 0), (center_x, frame_height), color, 1)
        cv2.circle(frame, (center_x, center_y), 2, color, -1)

    def render_live_overlay(self, frame, status: OverlayStatus):
        self.draw_image_center(frame)
        progress_pct = (
            (status.current_marker_index / len(status.target_ids)) * 100
            if status.target_ids
            else 0.0
        )
        _draw_progress_bar(frame, progress_pct)
        _draw_status_text(frame, status.state_name)

        if status.target_ids and 0 <= status.current_marker_index < len(status.target_ids):
            _draw_marker_info(
                frame,
                status.target_ids[status.current_marker_index],
                status.current_marker_index,
                len(status.target_ids),
            )

        if status.state_name == "ITERATE_ALIGNMENT":
            _draw_iteration_info(frame, status.iteration_count, status.max_iterations)
            if status.current_error_mm is not None:
                _draw_error_info(frame, status.current_error_mm, status.alignment_threshold_mm)

        _draw_progress_text(frame, progress_pct)
        return frame


def get_calibration_renderer(context) -> CalibrationRenderer:
    renderer = getattr(context, "calibration_renderer", None)
    if renderer is not None:
        return renderer
    return OpenCvCalibrationRenderer()


def _draw_progress_bar(frame, progress: float) -> None:
    left = 10
    bottom = frame.shape[0] - 30
    top = frame.shape[0] - 50
    width = 300
    fill_width = int(max(0.0, min(100.0, progress)) * 3)
    cv2.rectangle(frame, (left, top), (left + fill_width, bottom), (0, 255, 0), -1)
    cv2.rectangle(frame, (left, top), (left + width, bottom), (255, 255, 255), 2)


def _draw_status_text(frame, status_text: str) -> None:
    cv2.putText(frame, f"State: {status_text}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


def _draw_marker_info(frame, marker_id: int, marker_index: int, total_markers: int) -> None:
    cv2.putText(
        frame,
        f"Marker: {marker_id} ({marker_index + 1}/{total_markers})",
        (10, 55),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
    )


def _draw_iteration_info(frame, iteration_count: int, max_iterations: int) -> None:
    cv2.putText(
        frame,
        f"Iteration: {iteration_count}/{max_iterations}",
        (10, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 0),
        2,
    )


def _draw_error_info(frame, current_error_mm: float, threshold_mm: float) -> None:
    color = (0, 255, 0) if current_error_mm <= threshold_mm else (0, 0, 255)
    cv2.putText(
        frame,
        f"Error: {current_error_mm:.3f}mm",
        (10, 105),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        color,
        2,
    )


def _draw_progress_text(frame, progress: float) -> None:
    cv2.putText(
        frame,
        f"Progress: {progress:.0f}%",
        (10, frame.shape[0] - 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
    )
