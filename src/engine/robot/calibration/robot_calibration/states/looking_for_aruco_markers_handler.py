"""
Looking for ArUco Markers State Handler

Handles the state where the vision_service is looking for all required ArUco markers
in the camera feed to proceed with calibration.
"""

from collections import defaultdict
import logging

import numpy as np

from src.engine.robot.calibration.robot_calibration.live_feed import show_live_feed
from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import RobotCalibrationStates
from src.engine.robot.calibration.robot_calibration.target_planning import (
    build_partitioned_target_selection_plan,
)

_logger = logging.getLogger(__name__)

_N_REFERENCE_FRAMES = 10


def handle_looking_for_aruco_markers_state(context) -> RobotCalibrationStates:
    """
    Handle the LOOKING_FOR_ARUCO_MARKERS state.
    
    This state captures frames and looks for all required ArUco markers
    to proceed with the calibration process.
    
    Args:
        context: RobotCalibrationContext containing all calibration state
        
    Returns:
        Next state to transition to
    """
    # Flush camera buffer to get stable frame
    context.flush_camera_buffer()

    # Capture frame for ArUco detection
    all_aruco_detection_frame = context.wait_for_frame()
    if all_aruco_detection_frame is None:
        return RobotCalibrationStates.CANCELLED

    # Show live feed if visualization is enabled
    if context.live_visualization:
        show_live_feed(context, all_aruco_detection_frame, 0, broadcast_image=context.broadcast_events)

    # Find candidate markers in the current frame
    result = context.calibration_vision.find_required_aruco_markers(all_aruco_detection_frame)
    frame = result.frame

    averaged = _collect_averaged_reference_pixels(context, _N_REFERENCE_FRAMES)
    known_unreachable_ids = set()
    if getattr(context, "auto_skip_known_unreachable_markers", True):
        known_unreachable_ids = {
            int(marker_id)
            for marker_id in (getattr(context, "known_unreachable_marker_ids", set()) or set())
        }
    filtered_averaged = {
        int(marker_id): point
        for marker_id, point in averaged.items()
        if int(marker_id) not in known_unreachable_ids
    }
    auto_skipped_ids = sorted(
        int(marker_id) for marker_id in averaged.keys() if int(marker_id) in known_unreachable_ids
    )
    if auto_skipped_ids and getattr(context, "auto_skip_known_unreachable_markers", True):
        _logger.info(
            "Auto-skipping known-unreachable calibration markers: ids=%s",
            auto_skipped_ids,
        )
    required_partition_count = max(
        4,
        int(getattr(context, "homography_target_count", 16)),
    ) + max(
        0,
        int(getattr(context, "residual_target_count", 10)),
    ) + max(
        0,
        int(getattr(context, "validation_target_count", 6)),
    )
    if len(filtered_averaged) >= required_partition_count:
        selection_plan = build_partitioned_target_selection_plan(
            filtered_averaged,
            image_width=context.vision_service.get_camera_width(),
            image_height=context.vision_service.get_camera_height(),
            homography_targets=int(getattr(context, "homography_target_count", 16)),
            residual_targets=int(getattr(context, "residual_target_count", 10)),
            validation_targets=int(getattr(context, "validation_target_count", 6)),
            min_target_separation_px=float(getattr(context, "min_target_separation_px", 120.0)),
            preferred_ids=sorted(int(marker_id) for marker_id in getattr(context, "candidate_ids", set())),
        )
        context.available_marker_points_px = {
            int(marker_id): tuple(float(v) for v in point)
            for marker_id, point in filtered_averaged.items()
        }
        context.homography_marker_ids = list(selection_plan.homography_ids or [])
        context.residual_marker_ids = list(selection_plan.residual_ids or [])
        context.validation_marker_ids = list(selection_plan.validation_ids or [])
        context.execution_marker_ids = list(selection_plan.execution_ids or selection_plan.selected_ids)
        context.target_marker_ids = list(context.execution_marker_ids)
        context.recovery_marker_id = (
            int(context.target_marker_ids[0]) if context.target_marker_ids else None
        )
        context.marker_neighbor_ids = selection_plan.neighbor_ids
        context.target_selection_report = selection_plan.report
        context.failed_target_ids.clear()
        context.skipped_target_ids.clear()
        context.calibration_vision.detected_ids = set(filtered_averaged)
        context.calibration_vision.marker_top_left_corners = dict(filtered_averaged)
        _logger.info(
            "Calibration target grid created: available_ids=%s auto_skipped_known_unreachable_ids=%s homography_ids=%s residual_ids=%s validation_ids=%s execution_ids=%s report=%s",
            sorted(int(marker_id) for marker_id in filtered_averaged),
            auto_skipped_ids,
            list(context.homography_marker_ids),
            list(context.residual_marker_ids),
            list(context.validation_marker_ids),
            list(context.target_marker_ids),
            selection_plan.report,
        )
        return RobotCalibrationStates.ALL_ARUCO_FOUND
    else:
        # Stay in current state if not all markers found
        _logger.info(
            "Detected %d usable candidate markers after auto-skip (raw=%d); waiting for at least %d before selecting calibration targets",
            len(filtered_averaged),
            len(averaged),
            required_partition_count,
        )
        return RobotCalibrationStates.LOOKING_FOR_ARUCO_MARKERS


def _collect_averaged_reference_pixels(context, n_frames: int) -> dict[int, np.ndarray]:
    """
    Collect n_frames detections and replace marker_top_left_corners with the
    per-marker mean position.  Only frames where a marker is actually detected
    contribute to its average, so a momentary miss does not corrupt the result.
    """
    samples = defaultdict(list)

    for _ in range(n_frames):
        if context.stop_event.is_set():
            break
        frame = context.wait_for_frame()
        if frame is None:
            break
        per_frame = context.calibration_vision.collect_reference_sample(frame, allowed_ids=None)
        for marker_id, pt in per_frame.items():
            samples[marker_id].append(pt)

    averaged = {
        marker_id: np.mean(pts, axis=0).astype(np.float32)
        for marker_id, pts in samples.items()
        if pts
    }

    if averaged:
        _logger.info(
            "Reference pixels averaged over %d frames: %s",
            n_frames,
            {k: v.tolist() for k, v in averaged.items()},
        )
    return averaged
