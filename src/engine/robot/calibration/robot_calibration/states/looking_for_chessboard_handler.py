"""
Looking for Chessboard State Handler

Handles the state where the vision_service is looking for a chessboard pattern
in the camera feed to establish the reference coordinate vision_service.
"""
import logging
_logger = logging.getLogger(__name__)
import os
import cv2
import numpy as np
from src.engine.robot.calibration.robot_calibration.overlay import draw_image_center
from src.engine.robot.calibration.robot_calibration.live_feed import show_live_feed
from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import RobotCalibrationStates
from src.engine.robot.calibration.robot_calibration.logging import construct_chessboard_state_log_message
from src.engine.robot.calibration.robot_calibration.calibration_report import (
    derive_calibration_artifact_paths,
    save_geometry_scale_artifact,
)


def handle_looking_for_chessboard_state(context) -> RobotCalibrationStates:
    """
    Handle the LOOKING_FOR_CHESSBOARD state.
    
    This state captures frames and looks for a chessboard pattern to establish
    the reference coordinate vision_service and compute pixels-per-millimeter scale.
    
    Args:
        context: RobotCalibrationContext containing all calibration state
        
    Returns:
        Next state to transition to
    """
    # Get frame for chessboard detection
    chessboard_frame = context.wait_for_frame()
    if chessboard_frame is None:
        return RobotCalibrationStates.CANCELLED

    if context.live_visualization or context.broadcast_events:
        show_live_feed(
            context,
            chessboard_frame,
            current_error_mm=None,
            broadcast_image=context.broadcast_events,
        )

    # Find chessboard and compute pixels per millimeter
    result = context.calibration_vision.find_chessboard_and_compute_ppm(chessboard_frame)
    found = result.found
    ppm = result.ppm
    context.bottom_left_chessboard_corner_px = result.bottom_left_px

    # Log the chessboard detection result
    message = construct_chessboard_state_log_message(
        found=found,
        ppm=ppm if found else None,
        bottom_left_corner=context.bottom_left_chessboard_corner_px,
        debug_enabled=context.debug,
        detection_message=result.message
    )
    _logger.info(message)

    if found:
        # Store the pixels per millimeter for later use
        context.calibration_vision.PPM = ppm
        _persist_initial_ppm(context, ppm)
        _log_chessboard_pose(context)
        
        if context.debug:
            draw_image_center(chessboard_frame)
        
        return RobotCalibrationStates.CHESSBOARD_FOUND
    else:
        # Stay in current state if chessboard not found
        return RobotCalibrationStates.LOOKING_FOR_CHESSBOARD


def _persist_initial_ppm(context, ppm: float) -> None:
    _persist_initial_ppm_artifact(context, ppm)

    settings_service = context.settings_service
    calibration_key = context.calibration_settings_key
    if settings_service is None or calibration_key is None:
        return
    try:
        calibration_settings = settings_service.get(calibration_key)
        if calibration_settings is None:
            return
        calibration_settings.initial_ppm = ppm
        settings_service.save(calibration_key, calibration_settings)
        _logger.info("Initial PPM=%.3f saved to calibration settings", ppm)
    except Exception as exc:
        _logger.warning("Failed to persist initial PPM=%.3f: %s", ppm, exc)


def _persist_initial_ppm_artifact(context, ppm: float) -> None:
    try:
        matrix_path = context.vision_service.camera_to_robot_matrix_path
        artifact_paths = derive_calibration_artifact_paths(matrix_path)
        bottom_left = getattr(context, "bottom_left_chessboard_corner_px", None)
        center = getattr(context.calibration_vision, "chessboard_center_px", None)
        payload = {
            "source": "reference_board_detection",
            "board_kind": getattr(context.calibration_vision, "detected_reference_board_kind", None),
            "ppm": float(ppm),
            "mm_per_px": float(1.0 / ppm) if ppm else None,
            "square_size_mm": float(context.square_size_mm),
            "z_current": float(context.Z_current) if context.Z_current is not None else None,
            "z_target": float(context.Z_target) if context.Z_target is not None else None,
            "ppm_scale": float(context.ppm_scale) if context.ppm_scale is not None else None,
            "bottom_left_px": _point_to_list(bottom_left),
            "board_center_px": _point_to_list(center),
        }
        save_geometry_scale_artifact(payload, artifact_paths["geometry_scale_path"])
        _logger.info(
            "Initial geometry PPM=%.3f saved to %s",
            ppm,
            artifact_paths["geometry_scale_path"],
        )
    except Exception as exc:
        _logger.warning("Failed to persist initial geometry PPM=%.3f: %s", ppm, exc)


def _point_to_list(point) -> list[float] | None:
    if point is None:
        return None
    arr = np.asarray(point, dtype=float).reshape(-1)
    if arr.size < 2:
        return None
    return [float(arr[0]), float(arr[1])]


def _log_chessboard_pose(context) -> None:
    """Compute and log chessboard pose via solvePnP for diagnostic purposes."""
    corners = getattr(context.calibration_vision, "original_chessboard_corners", None)
    if corners is None:
        return

    try:
        storage_dir = os.path.dirname(context.vision_service.camera_to_robot_matrix_path)
        data = np.load(os.path.join(storage_dir, "camera_calibration.npz"))
        K, dist = data["mtx"], data["dist"]
    except Exception as exc:
        _logger.warning("Chessboard PnP: could not load camera calibration: %s", exc)
        return

    board_obj_pts = getattr(context.calibration_vision, "original_board_object_points", None)
    if board_obj_pts is not None:
        objp = np.asarray(board_obj_pts, dtype=np.float32).reshape(-1, 3)
    else:
        cols, rows = context.chessboard_size
        sq = float(context.square_size_mm)
        objp = np.zeros((cols * rows, 3), np.float32)
        objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * sq
    img_pts = corners.reshape(-1, 2).astype(np.float32)

    ok, rvec, tvec = cv2.solvePnP(objp, img_pts, K, dist, flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok:
        _logger.warning("Chessboard PnP: solvePnP failed")
        return

    projected, _ = cv2.projectPoints(objp, rvec, tvec, K, dist)
    reproj_error = float(np.sqrt(np.mean((projected.reshape(-1, 2) - img_pts) ** 2)))
    tx, ty, tz = tvec.flatten()
    rx, ry, rz = rvec.flatten()

    robot_pose = context.calibration_robot_controller.get_current_position()
    if robot_pose and len(robot_pose) >= 6:
        pose_str = "robot=(x=%.2f y=%.2f z=%.2f rx=%.4f ry=%.4f rz=%.4f)" % tuple(robot_pose[:6])
    else:
        pose_str = "robot=unavailable"

    _logger.info(
        "Chessboard PnP pose — tvec=(x=%.2f y=%.2f z=%.2f)mm  rvec=(%.4f, %.4f, %.4f)rad  reproj=%.3fpx  %s",
        tx, ty, tz, rx, ry, rz, reproj_error, pose_str,
    )
