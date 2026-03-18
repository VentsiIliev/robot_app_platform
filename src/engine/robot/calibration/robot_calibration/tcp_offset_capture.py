import logging
import math
from dataclasses import dataclass

import numpy as np


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

    required_ids_list = sorted(list(context.required_ids))
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

    if _move_to_pose(context, reference_pose, "restore tcp-offset reference pose") is None:
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

    target_pose = [start_pose[0], start_pose[1], start_pose[2], start_pose[3], start_pose[4], target_rz]
    if _move_to_pose(context, target_pose, f"tcp-offset sample rz={target_rz:.3f}") is None:
        return None

    if context.interruptible_sleep(getattr(context.camera_tcp_offset_config, "settle_time_s", 0.0)):
        context.calibration_error_message = "TCP offset capture cancelled during settle wait"
        return None

    return _align_marker_to_center(
        context,
        marker_id,
        max_iterations=getattr(context.camera_tcp_offset_config, "recenter_max_iterations", context.max_iterations),
    )


def _align_marker_to_center(context, marker_id: int, max_iterations: int):
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
        image_center_px = (
            context.vision_service.get_camera_width() // 2,
            context.vision_service.get_camera_height() // 2,
        )
        marker_top_left_px = context.calibration_vision.marker_top_left_corners[marker_id]
        offset_x_px = marker_top_left_px[0] - image_center_px[0]
        offset_y_px = marker_top_left_px[1] - image_center_px[1]
        current_error_px = float(np.sqrt(offset_x_px ** 2 + offset_y_px ** 2))

        ppm = context.calibration_vision.PPM * context.ppm_scale
        current_error_mm = current_error_px / ppm
        if current_error_mm <= context.alignment_threshold_mm:
            return context.calibration_robot_controller.get_current_position()

        offset_x_mm = offset_x_px / ppm
        offset_y_mm = offset_y_px / ppm
        mapped_x_mm, mapped_y_mm = context.image_to_robot_mapping.map(offset_x_mm, offset_y_mm)
        try:
            iterative_position = context.calibration_robot_controller.get_iterative_align_position(
                current_error_mm,
                mapped_x_mm,
                mapped_y_mm,
                context.alignment_threshold_mm,
            )
        except RuntimeError as exc:
            context.calibration_error_message = str(exc)
            return None

        if _move_to_pose(context, iterative_position, f"tcp-offset recenter marker {marker_id} iter {iteration}") is None:
            return None

        if context.interruptible_sleep(context.fast_iteration_wait):
            context.calibration_error_message = "TCP offset capture cancelled during recenter wait"
            return None

    context.calibration_error_message = (
        f"TCP offset capture failed: could not recenter marker {marker_id} "
        f"after {max_iterations} iterations"
    )
    return None


def _move_to_pose(context, pose, label: str):
    ok = context.calibration_robot_controller.move_to_position(pose, blocking=True)
    if not ok:
        context.calibration_error_message = f"TCP offset capture move failed: {label}"
        return None
    return pose


def _restore_reference_pose(context, reference_pose, reason: str) -> None:
    if reference_pose is None:
        return
    restored = _move_to_pose(context, reference_pose, f"restore tcp-offset reference pose {reason}")
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
