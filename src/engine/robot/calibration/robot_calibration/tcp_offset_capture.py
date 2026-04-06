import logging
import math
from dataclasses import dataclass

import numpy as np

from src.engine.robot.calibration.robot_calibration.ppm_utils import (
    adaptive_stability_wait,
    clear_ppm_probe,
    get_working_ppm,
)


_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CameraTcpOffsetSample:
    marker_id: int
    sample_index: int
    reference_rz: float
    sample_rz: float
    world_dx: float
    world_dy: float
    local_dx: float
    local_dy: float


def capture_tcp_offset_for_current_marker(context) -> bool:
    cfg = getattr(context, "camera_tcp_offset_config", None)
    if cfg is None or not getattr(cfg, "run_during_robot_calibration", False):
        return True

    required_ids_list = list(getattr(context, "target_marker_ids", None) or sorted(list(context.required_ids)))
    marker_id = required_ids_list[context.current_marker_id]
    if not hasattr(context, "camera_tcp_offset_captured_markers"):
        context.camera_tcp_offset_captured_markers = set()
    current_pose = context.calibration_robot_controller.get_current_position()
    if not current_pose or len(current_pose) < 6:
        context.calibration_error_message = "Current pose unavailable before TCP offset capture"
        return False

    reference_pose = _move_and_realign_marker(context, marker_id, cfg.approach_rz)
    if reference_pose is None:
        return False

    context.robot_positions_for_calibration[marker_id] = list(reference_pose)
    if not hasattr(context, "camera_tcp_offset_samples"):
        context.camera_tcp_offset_samples = []

    # Snapshot ppm_working — TCP rotation fools the axis mapping so ppm_obs would be
    # systematically underestimated (≈ true_ppm × cos(rotation_angle)).  Refinement
    # during rotated recenter corrupts ppm_working for subsequent markers.
    _ppm_snapshot = getattr(context, "ppm_working", None)

    try:
        for index in range(1, cfg.iterations + 1):
            if context.stop_event.is_set():
                _restore_reference_pose(context, reference_pose, "after stop request")
                return False

            sample_rz = cfg.approach_rz + index * cfg.rotation_step_deg
            aligned_pose = _move_and_realign_marker(context, marker_id, sample_rz)
            if aligned_pose is None:
                _restore_reference_pose(context, reference_pose, "after failure")
                return False

            world_dx = float(aligned_pose[0] - reference_pose[0])
            world_dy = float(aligned_pose[1] - reference_pose[1])
            try:
                local_dx, local_dy = _solve_local_offset(
                    world_dx,
                    world_dy,
                    reference_rz_deg=cfg.approach_rz,
                    sample_rz_deg=sample_rz,
                )
            except ValueError as exc:
                context.calibration_error_message = str(exc)
                _restore_reference_pose(context, reference_pose, "after invalid TCP offset sample")
                return False
            sample = CameraTcpOffsetSample(
                marker_id=marker_id,
                sample_index=index - 1,
                reference_rz=float(cfg.approach_rz),
                sample_rz=float(sample_rz),
                world_dx=world_dx,
                world_dy=world_dy,
                local_dx=float(local_dx),
                local_dy=float(local_dy),
            )
            context.camera_tcp_offset_samples.append(sample)
            _logger.info(
                "Captured TCP offset sample: marker=%d sample=%d/%d reference_rz=%.3f sample_rz=%.3f "
                "world=(%.6f, %.6f) local=(%.6f, %.6f)",
                marker_id,
                index,
                cfg.iterations,
                cfg.approach_rz,
                sample_rz,
                world_dx,
                world_dy,
                local_dx,
                local_dy,
            )
    finally:
        # Always restore the pre-TCP-capture ppm_working so the corrupted
        # per-rotation observations don't bleed into subsequent marker alignment.
        if _ppm_snapshot is not None:
            if context.ppm_working != _ppm_snapshot:
                _logger.info(
                    "PPM restored after TCP capture: %.3f → %.3f",
                    context.ppm_working, _ppm_snapshot,
                )
            context.ppm_working = _ppm_snapshot

    if _move_to_pose(context, reference_pose, "restore tcp-offset reference pose",
                     velocity=int(getattr(cfg, "velocity", 20)),
                     acceleration=int(getattr(cfg, "acceleration", 10))) is None:
        return False
    context.camera_tcp_offset_captured_markers.add(marker_id)
    return True


def finalize_tcp_offset_calibration(context) -> tuple[bool, str]:
    cfg = getattr(context, "camera_tcp_offset_config", None)
    samples = [
        sample
        for sample in getattr(context, "camera_tcp_offset_samples", [])
        if not math.isclose(float(sample.sample_rz), float(sample.reference_rz), abs_tol=1e-9)
    ]
    min_samples = getattr(cfg, "min_samples", 3)
    if len(samples) < min_samples:
        return False, f"Not enough TCP offset samples collected ({len(samples)}/{min_samples})"

    offset_x = float(np.mean([sample.local_dx for sample in samples]))
    offset_y = float(np.mean([sample.local_dy for sample in samples]))
    std_x = float(np.std([sample.local_dx for sample in samples]))
    std_y = float(np.std([sample.local_dy for sample in samples]))
    max_std = float(getattr(cfg, "max_acceptance_std_mm", 10.0))

    _logger.info(_build_tcp_offset_summary(samples, offset_x=offset_x, offset_y=offset_y, std_x=std_x, std_y=std_y))

    if std_x > max_std or std_y > max_std:
        return False, (
            f"TCP offset sample spread too high: std_x={std_x:.3f}mm std_y={std_y:.3f}mm "
            f"(limit {max_std:.3f}mm)"
        )

    robot_config = getattr(context, "robot_config", None)
    settings_service = getattr(context, "settings_service", None)
    robot_config_key = getattr(context, "robot_config_key", "robot_config")
    if robot_config is None or settings_service is None:
        return False, "Robot config/settings unavailable for saving TCP offsets"

    robot_config.camera_to_tcp_x_offset = offset_x
    robot_config.camera_to_tcp_y_offset = offset_y
    settings_service.save(robot_config_key, robot_config)
    return True, (
        f"Saved camera_to_tcp_x_offset={offset_x:.6f} camera_to_tcp_y_offset={offset_y:.6f} "
        f"std=({std_x:.6f}, {std_y:.6f})"
    )


def _build_tcp_offset_summary(
    samples: list[CameraTcpOffsetSample],
    *,
    offset_x: float,
    offset_y: float,
    std_x: float,
    std_y: float,
) -> str:
    dx_arr = np.array([sample.local_dx for sample in samples], dtype=np.float64)
    dy_arr = np.array([sample.local_dy for sample in samples], dtype=np.float64)
    lines = [
        "=== TCP OFFSET CALIBRATION SUMMARY ===",
        f"Samples used: {len(samples)}",
        "Raw samples:",
    ]
    for sample in samples:
        lines.append(
            "  "
            f"marker={sample.marker_id} idx={sample.sample_index} "
            f"ref_rz={sample.reference_rz:.3f} sample_rz={sample.sample_rz:.3f} "
            f"world=({sample.world_dx:.6f}, {sample.world_dy:.6f}) "
            f"local=({sample.local_dx:.6f}, {sample.local_dy:.6f})"
        )

    grouped: dict[float, list[CameraTcpOffsetSample]] = {}
    for sample in samples:
        grouped.setdefault(float(sample.sample_rz), []).append(sample)

    lines.append("Grouped by sample_rz:")
    for sample_rz in sorted(grouped):
        group = grouped[sample_rz]
        group_mean_x = float(np.mean([sample.local_dx for sample in group]))
        group_mean_y = float(np.mean([sample.local_dy for sample in group]))
        group_std_x = float(np.std([sample.local_dx for sample in group]))
        group_std_y = float(np.std([sample.local_dy for sample in group]))
        lines.append(
            "  "
            f"sample_rz={sample_rz:.3f} "
            f"count={len(group)} "
            f"mean_local=({group_mean_x:.6f}, {group_mean_y:.6f}) "
            f"std_local=({group_std_x:.6f}, {group_std_y:.6f})"
        )

    lines.extend(
        [
            "Final aggregate:",
            f"  mean_local=({offset_x:.6f}, {offset_y:.6f})",
            f"  std_local=({std_x:.6f}, {std_y:.6f})",
            f"  range_local_x=({dx_arr.min():.6f}, {dx_arr.max():.6f}) span={dx_arr.max() - dx_arr.min():.6f}",
            f"  range_local_y=({dy_arr.min():.6f}, {dy_arr.max():.6f}) span={dy_arr.max() - dy_arr.min():.6f}",
            "====================================",
        ]
    )
    return "\n".join(lines)


def should_capture_tcp_offset_for_current_marker(context) -> bool:
    cfg = getattr(context, "camera_tcp_offset_config", None)
    if cfg is None:
        return False
    if not getattr(cfg, "run_during_robot_calibration", False):
        return False
    if getattr(cfg, "iterations", 0) <= 0:
        return False
    captured_markers = getattr(context, "camera_tcp_offset_captured_markers", set())
    max_markers = max(0, int(getattr(cfg, "max_markers_for_tcp_capture", 0)))
    if max_markers > 0 and len(captured_markers) >= max_markers:
        return False
    return True


def _move_and_realign_marker(context, marker_id: int, target_rz: float):
    start_pose = context.calibration_robot_controller.get_current_position()
    if not start_pose or len(start_pose) < 6:
        context.calibration_error_message = "Current pose unavailable during TCP offset capture"
        return None

    cfg = getattr(context, "camera_tcp_offset_config", None)
    _vel = int(getattr(cfg, "velocity", 20)) if cfg is not None else None
    _acc = int(getattr(cfg, "acceleration", 10)) if cfg is not None else None

    target_pose = [start_pose[0], start_pose[1], start_pose[2], start_pose[3], start_pose[4], target_rz]
    if _move_to_pose(context, target_pose, f"tcp-offset sample rz={target_rz:.3f}", velocity=_vel, acceleration=_acc) is None:
        return None

    actual_pose = context.calibration_robot_controller.get_current_position()
    if actual_pose and len(actual_pose) >= 6:
        actual_rz = actual_pose[5]
        rz_error = abs(actual_rz - target_rz)
        _logger.info(
            "TCP rotation verify: target_rz=%.3f  actual_rz=%.3f  error=%.3f deg  "
            "xyz=(%.3f, %.3f, %.3f)",
            target_rz, actual_rz, rz_error,
            actual_pose[0], actual_pose[1], actual_pose[2],
        )
        if rz_error > 2.0:
            _logger.warning(
                "TCP rotation FAILED: robot did not reach target_rz=%.3f "
                "(actual=%.3f, error=%.3f deg) — aborting sample to prevent corrupt data",
                target_rz, actual_rz, rz_error,
            )
            context.calibration_error_message = (
                f"TCP rotation failed: target_rz={target_rz:.3f} actual_rz={actual_rz:.3f} "
                f"(error={rz_error:.3f} deg > 2.0 deg limit)"
            )
            return None
    else:
        _logger.warning("TCP rotation verify: could not read back robot pose after rotation move")

    if context.interruptible_sleep(getattr(context.camera_tcp_offset_config, "settle_time_s", 0.0)):
        context.calibration_error_message = "TCP offset capture cancelled during settle wait"
        return None

    # Robot just rotated — its XY shifted by the TCP offset, so the probe from the
    # main alignment phase is no longer valid. Also reset the derivative state so the
    # large error jump (converged→rotated) isn't misread as overshoot and doesn't clamp
    # the first correction step to ~0.85mm via the derivative brake.
    clear_ppm_probe(context)
    context.calibration_robot_controller.reset_derivative_state()

    cfg_rz = getattr(context, "camera_tcp_offset_config", None)
    reference_rz = float(getattr(cfg_rz, "approach_rz", 0.0)) if cfg_rz is not None else 0.0
    camera_rotation_deg = target_rz - reference_rz
    return _align_marker_to_center(
        context,
        marker_id,
        max_iterations=getattr(context.camera_tcp_offset_config, "recenter_max_iterations", context.max_iterations),
        camera_rotation_deg=camera_rotation_deg,
    )


def _align_marker_to_center(context, marker_id: int, max_iterations: int, camera_rotation_deg: float = 0.0):
    image_center_px = (
        context.vision_service.get_camera_width() // 2,
        context.vision_service.get_camera_height() // 2,
    )

    for iteration in range(1, max_iterations + 1):
        if context.stop_event.is_set():
            context.calibration_error_message = "TCP offset capture cancelled"
            return None

        frame = context.wait_for_frame()
        if frame is None:
            context.calibration_error_message = "TCP offset capture cancelled while waiting for frame"
            return None

        result = context.calibration_vision.detect_specific_marker(frame, marker_id)
        if not result.found:
            _logger.info("TCP offset capture: marker %d not found during recenter iteration %d", marker_id, iteration)
            continue

        context.calibration_vision.update_marker_top_left_corners(marker_id, result.aruco_corners, result.aruco_ids)
        marker_top_left_px = context.calibration_vision.marker_top_left_corners[marker_id]

        offset_x_px = marker_top_left_px[0] - image_center_px[0]
        offset_y_px = marker_top_left_px[1] - image_center_px[1]
        current_error_px = float(np.sqrt(offset_x_px ** 2 + offset_y_px ** 2))

        # Read PPM without refinement — at rotated orientations the axis mapping is
        # no longer aligned with the robot XY axes, so ppm_obs = true_ppm × cos(θ).
        # Updating ppm_working here would corrupt it progressively across rotation
        # samples, causing step sizes 2–3× too large and diverging oscillation.
        ppm = get_working_ppm(context)

        current_error_mm = current_error_px / ppm
        if current_error_mm <= context.alignment_threshold_mm:
            return context.calibration_robot_controller.get_current_position()

        offset_x_mm = offset_x_px / ppm
        offset_y_mm = offset_y_px / ppm

        if camera_rotation_deg != 0.0:
            # The camera has rotated by camera_rotation_deg relative to the reference
            # pose at which the axis mapping was calibrated.  Pixel offsets are now in
            # the rotated camera frame; de-rotate them back to the reference frame
            # before applying the axis mapping so the robot moves in the correct
            # direction.  Without this correction the X/Y corrections flip signs
            # repeatedly at large rotation angles (≥ 25°), causing 30+ iteration
            # oscillation instead of clean convergence.
            theta = math.radians(camera_rotation_deg)
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)
            derotated_x_mm = offset_x_mm * cos_t + offset_y_mm * sin_t
            derotated_y_mm = -offset_x_mm * sin_t + offset_y_mm * cos_t
            mapped_x_mm, mapped_y_mm = context.image_to_robot_mapping.map(derotated_x_mm, derotated_y_mm)
        else:
            mapped_x_mm, mapped_y_mm = context.image_to_robot_mapping.map(offset_x_mm, offset_y_mm)
        try:
            iterative_position = context.calibration_robot_controller.get_iterative_align_position(
                current_error_mm,
                mapped_x_mm,
                mapped_y_mm,
                context.alignment_threshold_mm,
                preserve_current_orientation=True,
            )
        except RuntimeError as exc:
            context.calibration_error_message = str(exc)
            return None


        if _move_to_pose(context, iterative_position, f"tcp-offset recenter marker {marker_id} iter {iteration}") is None:
            return None

        _raw_wait = adaptive_stability_wait(context, current_error_mm)
        # TCP recenter is a small horizontal move at working Z — settles much faster
        # than the main alignment's large approach moves.  Cap independently.
        _tcp_max_wait = float(getattr(context.camera_tcp_offset_config, "recenter_stability_wait_s", 0.4))
        _scaled_wait = min(_raw_wait, _tcp_max_wait)
        _logger.info(
            "TCP recenter [marker %d iter %d]: error=%.3fmm wait=%.2fs (cap=%.2fs align_max=%.1fs)",
            marker_id, iteration, current_error_mm, _scaled_wait, _tcp_max_wait, context.fast_iteration_wait,
        )
        if context.interruptible_sleep(_scaled_wait):
            context.calibration_error_message = "TCP offset capture cancelled during recenter wait"
            return None

    context.calibration_error_message = (
        f"TCP offset capture failed: could not recenter marker {marker_id} "
        f"after {max_iterations} iterations"
    )
    return None


def _move_to_pose(context, pose, label: str, velocity=None, acceleration=None):
    ok = context.calibration_robot_controller.move_to_position(
        pose, blocking=True, velocity=velocity, acceleration=acceleration
    )
    if not ok:
        context.calibration_error_message = f"TCP offset capture move failed: {label}"
        return None
    return pose


def _restore_reference_pose(context, reference_pose, reason: str) -> None:
    if reference_pose is None:
        return
    cfg = getattr(context, "camera_tcp_offset_config", None)
    _vel = int(getattr(cfg, "velocity", 20)) if cfg is not None else None
    _acc = int(getattr(cfg, "acceleration", 10)) if cfg is not None else None
    restored = _move_to_pose(context, reference_pose, f"restore tcp-offset reference pose {reason}", velocity=_vel, acceleration=_acc)
    if restored is None:
        _logger.warning("Failed to restore TCP offset reference pose %s", reason)


def _solve_local_offset(
    world_dx: float,
    world_dy: float,
    *,
    reference_rz_deg: float,
    sample_rz_deg: float,
) -> tuple[float, float]:
    ref_rad = math.radians(reference_rz_deg)
    sample_rad = math.radians(sample_rz_deg)
    cos_ref = math.cos(ref_rad)
    sin_ref = math.sin(ref_rad)
    cos_sample = math.cos(sample_rad)
    sin_sample = math.sin(sample_rad)

    a = cos_ref - cos_sample
    b = -sin_ref + sin_sample
    c = sin_ref - sin_sample
    d = cos_ref - cos_sample
    det = a * d - b * c
    if math.isclose(det, 0.0, abs_tol=1e-9):
        raise ValueError(
            "TCP offset sample rotation is too small to solve a camera-to-TCP offset"
        )

    local_dx = (d * world_dx - b * world_dy) / det
    local_dy = (-c * world_dx + a * world_dy) / det
    return float(local_dx), float(local_dy)
