import cv2
import numpy as np


def draw_image_center(frame) -> None:
    if frame is None:
        return
    frame_height, frame_width = frame.shape[:2]
    center_x, center_y = frame_width // 2, frame_height // 2
    color = (255, 0, 0)
    cv2.line(frame, (0, center_y), (frame_width, center_y), color, 1)
    cv2.line(frame, (center_x, 0), (center_x, frame_height), color, 1)
    cv2.circle(frame, (center_x, center_y), 2, color, -1)


def draw_live_overlay(context, frame, current_error_mm=None):
    if frame is None or not context.live_visualization:
        return frame

    draw_image_center(frame)

    target_ids = list(getattr(context, "target_marker_ids", None) or sorted(list(context.required_ids)))
    progress = (context.current_marker_id / len(target_ids)) * 100 if target_ids else 0.0
    _draw_progress_bar(frame, progress)
    _draw_status_text(frame, context.get_current_state_name())

    if target_ids and 0 <= context.current_marker_id < len(target_ids):
        _draw_marker_info(frame, target_ids[context.current_marker_id], context.current_marker_id, len(target_ids))

    current_state = getattr(context.state_machine, "current_state", None) if context.state_machine else None
    if current_state is not None and current_state.name == "ITERATE_ALIGNMENT":
        _draw_iteration_info(frame, context.iteration_count, context.max_iterations)
        if current_error_mm is not None:
            _draw_error_info(frame, current_error_mm, context.alignment_threshold_mm)

    _draw_progress_text(frame, progress)
    return frame


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
