from __future__ import annotations

import logging
import threading
import time
from typing import Callable, List, Optional, Tuple

import numpy as np

from src.engine.robot.calibration.intrinsic_capture.types import (
    BoardDetection,
    BoardType,
    CaptureSample,
    ImageInfo,
    LocalJacobian2D,
    TargetRegion,
    TiltAxis,
)
from src.engine.robot.calibration.intrinsic_capture.vision_helpers import (
    compute_feasible_region,
    detect_board,
    make_grid_regions,
)

_logger = logging.getLogger(__name__)


def _detect_with_retry(
    grab_frame_fn: Callable[[], np.ndarray],
    detect_fn: Callable[[np.ndarray], BoardDetection],
    max_retries: int = 1,
) -> Tuple[np.ndarray, BoardDetection]:
    frame = grab_frame_fn()
    det = detect_fn(frame)
    for attempt in range(1, max_retries):
        if det.found:
            break
        _logger.debug("Detection failed (attempt %d/%d), retrying...", attempt, max_retries)
        time.sleep(0.05)
        frame = grab_frame_fn()
        det = detect_fn(frame)
    return frame, det


def estimate_local_xy_jacobian(
    get_pose_fn: Callable[[], List[float]],
    move_relative_fn: Callable[..., bool],
    move_absolute_fn: Callable[[List[float]], bool],
    grab_frame_fn: Callable[[], np.ndarray],
    detect_fn: Callable[[np.ndarray], BoardDetection],
    probe_dx_mm: float = 20.0,
    probe_dy_mm: float = 20.0,
    probe_drx_deg: float = 3.0,
    probe_dry_deg: float = 3.0,
    probe_drz_deg: float = 0.0,
    max_detection_retries: int = 1,
    move_absolute_fast_fn: Optional[Callable[[List[float]], bool]] = None,
) -> LocalJacobian2D:
    base_pose = get_pose_fn()
    reposition = move_absolute_fast_fn if move_absolute_fast_fn is not None else move_absolute_fn
    _, det0 = _detect_with_retry(grab_frame_fn, detect_fn, max_detection_retries)
    if not det0.found or det0.center_px is None:
        raise RuntimeError("Cannot estimate Jacobian: board not detected at base pose.")
    u0, v0 = det0.center_px

    if not move_relative_fn(dx=probe_dx_mm):
        raise RuntimeError("Failed X probe move.")
    _, det_x = _detect_with_retry(grab_frame_fn, detect_fn, max_detection_retries)
    reposition(base_pose)
    if not det_x.found or det_x.center_px is None:
        raise RuntimeError("Board lost during X probe move.")
    ux, vx = det_x.center_px

    if not move_relative_fn(dy=probe_dy_mm):
        raise RuntimeError("Failed Y probe move.")
    _, det_y = _detect_with_retry(grab_frame_fn, detect_fn, max_detection_retries)
    reposition(base_pose)
    if not det_y.found or det_y.center_px is None:
        raise RuntimeError("Board lost during Y probe move.")
    uy, vy = det_y.center_px

    J = np.array(
        [[(ux - u0) / probe_dx_mm, (uy - u0) / probe_dy_mm],
         [(vx - v0) / probe_dx_mm, (vy - v0) / probe_dy_mm]],
        dtype=float,
    )
    tilt_sensitivity: dict = {}

    def _probe_rotation(pose_index: int, angle_deg: float, axis: TiltAxis, label: str) -> None:
        if angle_deg == 0.0:
            return
        target = list(base_pose)
        target[pose_index] = base_pose[pose_index] + angle_deg
        if not move_absolute_fn(target):
            _logger.warning("Tilt probe move failed for %s", label)
            reposition(base_pose)
            return
        _, det_r = _detect_with_retry(grab_frame_fn, detect_fn, max_detection_retries)
        reposition(base_pose)
        if not det_r.found or det_r.center_px is None:
            return
        ur, vr = det_r.center_px
        tilt_sensitivity[axis] = np.array([(ur - u0) / angle_deg, (vr - v0) / angle_deg], dtype=float)

    _probe_rotation(3, probe_drx_deg, TiltAxis.ROLL, "RX/roll")
    _probe_rotation(4, probe_dry_deg, TiltAxis.PITCH, "RY/pitch")
    _probe_rotation(5, probe_drz_deg, TiltAxis.YAW, "RZ/yaw")
    return LocalJacobian2D(J=J, tilt_sensitivity=tilt_sensitivity or None)


def _inside_target_region(det: BoardDetection, region: TargetRegion) -> bool:
    if not det.found or det.center_px is None:
        return False
    cx, cy = det.center_px
    tx, ty = region.center_px
    tol_x, tol_y = region.tol_px
    return abs(cx - tx) <= tol_x and abs(cy - ty) <= tol_y


def move_board_center_near_region(
    grab_frame_fn: Callable[[], np.ndarray],
    move_relative_fn: Callable[..., bool],
    detect_fn: Callable[[np.ndarray], BoardDetection],
    region: TargetRegion,
    jacobian: LocalJacobian2D,
    max_refines: int = 2,
    gain: float = 0.9,
    max_detection_retries: int = 1,
) -> bool:
    _, det = _detect_with_retry(grab_frame_fn, detect_fn, max_detection_retries)
    if not det.found or det.center_px is None:
        return False
    if _inside_target_region(det, region):
        return True
    for _ in range(max_refines + 1):
        cx, cy = det.center_px
        tx, ty = region.center_px
        dx, dy = jacobian.robot_delta_from_pixel_error(tx - cx, ty - cy)
        if not move_relative_fn(dx=gain * dx, dy=gain * dy):
            return False
        _, det = _detect_with_retry(grab_frame_fn, detect_fn, max_detection_retries)
        if not det.found or det.center_px is None:
            return False
        if _inside_target_region(det, region):
            return True
    return False


def _predict_tilt_sign(
    board_center: Tuple[float, float],
    image_info: ImageInfo,
    tilt_axis: TiltAxis,
    tilt_deg: float,
    jacobian: LocalJacobian2D,
    margin_px: float = 40.0,
) -> float:
    if jacobian.tilt_sensitivity is None:
        return 1.0
    sensitivity = jacobian.tilt_sensitivity.get(tilt_axis)
    if sensitivity is None:
        return 1.0
    cx, cy = board_center
    img_cx = image_info.width / 2.0
    img_cy = image_info.height / 2.0
    best_sign = 1.0
    best_score = float("-inf")
    for sign in (1.0, -1.0):
        new_cx = cx + float(sensitivity[0] * tilt_deg * sign)
        new_cy = cy + float(sensitivity[1] * tilt_deg * sign)
        in_bounds = margin_px <= new_cx <= image_info.width - margin_px and margin_px <= new_cy <= image_info.height - margin_px
        dist_to_center = -np.hypot(new_cx - img_cx, new_cy - img_cy)
        score = dist_to_center if in_bounds else dist_to_center - 1e6
        if score > best_score:
            best_score = score
            best_sign = sign
    return best_sign


def capture_charuco_sweep_dataset(
    get_pose_fn: Callable[[], List[float]],
    move_absolute_fn: Callable[[List[float]], bool],
    grab_frame_fn: Callable[[], np.ndarray],
    save_frame_fn: Callable[[np.ndarray, str], Optional[str]],
    pattern_size: Tuple[int, int],
    square_size_mm: float,
    marker_size_mm: float,
    aruco_dict_id: int,
    grid_rows: int,
    grid_cols: int,
    sweep_x_mm: float,
    sweep_y_mm: float,
    tilt_deg: float,
    z_delta_mm: float,
    min_corners: int,
    stabilization_delay_s: float,
    stop_event: threading.Event,
    progress_cb: Callable[[str], None],
    initial_detection_attempts: int = 5,
    initial_detection_delay_s: float = 1.0,
    max_detection_retries: int = 1,
    detection_callback: Optional[Callable] = None,
    rz_deg: float = 0.0,
) -> List[CaptureSample]:
    from src.engine.vision.implementation.VisionSystem.features.calibration.charuco import AutoCharucoBoardDetector

    home_pose = get_pose_fn()
    detector = AutoCharucoBoardDetector(
        squares_x=pattern_size[0],
        squares_y=pattern_size[1],
        square_length=square_size_mm,
        marker_length=marker_size_mm,
        dictionary_id=aruco_dict_id,
    )

    def _count_corners(frame: np.ndarray) -> int:
        result = detector.detect(frame)
        return 0 if result.charuco_ids is None else len(result.charuco_ids)

    def _grab_and_count() -> Tuple[np.ndarray, int]:
        frame = grab_frame_fn()
        n = _count_corners(frame)
        for _ in range(max(1, max_detection_retries) - 1):
            if n >= min_corners:
                break
            time.sleep(0.05)
            frame = grab_frame_fn()
            n = _count_corners(frame)
        return frame, n

    progress_cb("Detecting ChArUco board at home pose...")
    home_frame, home_n = None, 0
    for attempt in range(initial_detection_attempts):
        if stop_event.is_set():
            break
        home_frame, home_n = _grab_and_count()
        if home_n >= min_corners:
            break
        remaining = initial_detection_attempts - attempt - 1
        if remaining > 0:
            progress_cb(f"  Not enough corners at home ({home_n}, need >={min_corners}), retrying in {initial_detection_delay_s:.1f}s...")
            time.sleep(initial_detection_delay_s)
    if home_n < min_corners:
        raise RuntimeError(f"ChArUco board not detected at home pose ({home_n} corners, need >={min_corners}).")

    home_result = detector.detect(home_frame)
    home_uv = None
    if home_result.charuco_corners is not None:
        c = home_result.charuco_corners.reshape(-1, 2)
        home_uv = np.array([float(np.mean(c[:, 0])), float(np.mean(c[:, 1]))])

    def _detection_result(frame: np.ndarray):
        result = detector.detect(frame)
        n = 0 if result.charuco_ids is None else len(result.charuco_ids)
        if result.charuco_corners is not None and n > 0:
            corners = result.charuco_corners.reshape(-1, 2)
            bbox = (float(np.min(corners[:, 0])), float(np.min(corners[:, 1])), float(np.max(corners[:, 0])), float(np.max(corners[:, 1])))
            center = np.array([float(np.mean(corners[:, 0])), float(np.mean(corners[:, 1]))])
        else:
            bbox, center = None, None
        return result, n, bbox, center

    def _grab_and_detect():
        frame = grab_frame_fn()
        _, n, bbox, center = _detection_result(frame)
        for _ in range(max(1, max_detection_retries) - 1):
            if n >= min_corners:
                break
            time.sleep(0.05)
            frame = grab_frame_fn()
            _, n, bbox, center = _detection_result(frame)
        return frame, n, bbox, center

    xs = np.linspace(-sweep_x_mm, sweep_x_mm, grid_cols) if grid_cols > 1 else [0.0]
    ys = np.linspace(-sweep_y_mm, sweep_y_mm, grid_rows) if grid_rows > 1 else [0.0]
    candidates: List[Tuple[str, List[float]]] = []
    for ri, dy in enumerate(ys):
        for ci, dx in enumerate(xs):
            prefix = f"r{ri}_c{ci}"
            base = [home_pose[0] + float(dx), home_pose[1] + float(dy), home_pose[2], home_pose[3], home_pose[4], home_pose[5]]
            candidates.append((f"{prefix}_neutral", base))
            if tilt_deg > 0:
                for axis_index, axis_prefix in ((3, "rx"), (4, "ry")):
                    pos = list(base)
                    neg = list(base)
                    pos[axis_index] += tilt_deg
                    neg[axis_index] -= tilt_deg
                    candidates.append((f"{prefix}_{axis_prefix}+", pos))
                    candidates.append((f"{prefix}_{axis_prefix}-", neg))
            if rz_deg > 0:
                pos = list(base)
                neg = list(base)
                pos[5] += rz_deg
                neg[5] -= rz_deg
                candidates.append((f"{prefix}_rz+", pos))
                candidates.append((f"{prefix}_rz-", neg))
            if z_delta_mm > 0:
                pos = list(base)
                neg = list(base)
                pos[2] += z_delta_mm
                neg[2] -= z_delta_mm
                candidates.append((f"{prefix}_z+", pos))
                candidates.append((f"{prefix}_z-", neg))

    samples: List[CaptureSample] = []
    j_data: List[Tuple[np.ndarray, np.ndarray]] = []
    saved_bboxes: List[Tuple] = []
    frame_hw: Optional[Tuple[int, int]] = None

    def _record(frame: np.ndarray, tag: str, pose: List[float], n: int, bbox, center) -> None:
        path = save_frame_fn(frame, tag)
        if not path:
            return
        current_pose = get_pose_fn()
        samples.append(CaptureSample(tag.rsplit("_", 1)[0], tag.rsplit("_", 1)[1], current_pose, path))
        progress_cb(f"  Saved ({n} corners) -> {path}")
        if bbox is not None:
            saved_bboxes.append(bbox)
            if detection_callback is not None:
                h, w = frame.shape[:2]
                detection_callback(bbox, (w, h))
        if tag.endswith("_neutral") and home_uv is not None and center is not None:
            d_robot = np.array(pose[:2]) - np.array(home_pose[:2])
            d_uv = center - home_uv
            if np.linalg.norm(d_robot) > 1.0:
                j_data.append((d_robot, d_uv))

    for idx, (tag, pose) in enumerate(candidates):
        if stop_event.is_set():
            progress_cb("Acquisition stopped by user.")
            break
        progress_cb(f"[{idx + 1}/{len(candidates)}] -> {tag}")
        if not move_absolute_fn(pose):
            progress_cb("  Move failed - skipping.")
            continue
        if stabilization_delay_s > 0:
            time.sleep(stabilization_delay_s)
        frame, n, bbox, center = _grab_and_detect()
        if frame_hw is None and frame is not None:
            frame_hw = frame.shape[:2]
        if n < min_corners:
            progress_cb(f"  Only {n} corners (need >={min_corners}) - skipping.")
            continue
        _record(frame, tag, pose, n, bbox, center)

    if not stop_event.is_set() and len(j_data) >= 3 and frame_hw is not None and home_uv is not None:
        A = np.array([d[0] for d in j_data])
        B = np.array([d[1] for d in j_data])
        J_inv = np.linalg.pinv(np.linalg.lstsq(A, B, rcond=None)[0].T)
        gcols, grows = 8, 6
        h, w = frame_hw
        cw, ch = w / gcols, h / grows
        grid = np.zeros((grows, gcols), dtype=np.float32)
        for (x1, y1, x2, y2) in saved_bboxes:
            for r in range(max(0, int(y1 / ch)), min(grows, int(y2 / ch) + 1)):
                for c in range(max(0, int(x1 / cw)), min(gcols, int(x2 / cw) + 1)):
                    grid[r, c] += 1
        gap_cells = [(r, c) for r in range(grows) for c in range(gcols) if grid[r, c] == 0]
        for r, c in gap_cells:
            if stop_event.is_set():
                break
            target_uv = np.array([(c + 0.5) * cw, (r + 0.5) * ch])
            d_robot = J_inv @ (target_uv - home_uv)
            gap_pose = list(home_pose)
            gap_pose[0] += float(d_robot[0])
            gap_pose[1] += float(d_robot[1])
            tag = f"gap_r{r}_c{c}_neutral"
            if not move_absolute_fn(gap_pose):
                continue
            if stabilization_delay_s > 0:
                time.sleep(stabilization_delay_s)
            frame, n, bbox, center = _grab_and_detect()
            if n < min_corners:
                continue
            _record(frame, tag, gap_pose, n, bbox, center)

    move_absolute_fn(home_pose)
    progress_cb(f"Sweep complete: {len(samples)} frames captured.")
    return samples


def capture_intrinsic_dataset(
    get_pose_fn: Callable[[], List[float]],
    move_relative_fn: Callable[..., bool],
    move_absolute_fn: Callable[[List[float]], bool],
    grab_frame_fn: Callable[[], np.ndarray],
    save_frame_fn: Callable[[np.ndarray, str], Optional[str]],
    image_info: ImageInfo,
    pattern_size: Tuple[int, int],
    board_type: BoardType,
    square_size_mm: float,
    marker_size_mm: float,
    aruco_dict_id: int,
    grid_rows: int,
    grid_cols: int,
    margin_px: float,
    tilt_deg: float,
    z_delta_mm: float,
    probe_dx_mm: float,
    probe_dy_mm: float,
    probe_drx_deg: float,
    probe_dry_deg: float,
    probe_drz_deg: float,
    stabilization_delay_s: float,
    stop_event: threading.Event,
    progress_cb: Callable[[str], None],
    max_detection_retries: int = 1,
    initial_detection_attempts: int = 5,
    initial_detection_delay_s: float = 1.0,
    charuco_sweep_x_mm: float = 100.0,
    charuco_sweep_y_mm: float = 100.0,
    charuco_min_corners: int = 6,
    charuco_rz_deg: float = 0.0,
    detection_callback: Optional[Callable] = None,
) -> List[CaptureSample]:
    if board_type == BoardType.CHARUCO:
        return capture_charuco_sweep_dataset(
            get_pose_fn=get_pose_fn,
            move_absolute_fn=move_absolute_fn,
            grab_frame_fn=grab_frame_fn,
            save_frame_fn=save_frame_fn,
            pattern_size=pattern_size,
            square_size_mm=square_size_mm,
            marker_size_mm=marker_size_mm,
            aruco_dict_id=aruco_dict_id,
            grid_rows=grid_rows,
            grid_cols=grid_cols,
            sweep_x_mm=charuco_sweep_x_mm,
            sweep_y_mm=charuco_sweep_y_mm,
            tilt_deg=tilt_deg,
            z_delta_mm=z_delta_mm,
            min_corners=charuco_min_corners,
            stabilization_delay_s=stabilization_delay_s,
            stop_event=stop_event,
            progress_cb=progress_cb,
            initial_detection_attempts=initial_detection_attempts,
            initial_detection_delay_s=initial_detection_delay_s,
            max_detection_retries=max_detection_retries,
            detection_callback=detection_callback,
            rz_deg=charuco_rz_deg,
        )

    samples: List[CaptureSample] = []

    def detect(frame: np.ndarray) -> BoardDetection:
        return detect_board(
            frame,
            pattern_size,
            board_type,
            square_size_mm=square_size_mm,
            marker_size_mm=marker_size_mm,
            aruco_dict_id=aruco_dict_id,
        )

    def move_relative_stable(**kwargs) -> bool:
        ok = move_relative_fn(**kwargs)
        if ok and stabilization_delay_s > 0:
            time.sleep(stabilization_delay_s)
        return ok

    def move_absolute_stable(pose: List[float]) -> bool:
        ok = move_absolute_fn(pose)
        if ok and stabilization_delay_s > 0:
            time.sleep(stabilization_delay_s)
        return ok

    det0 = None
    for _ in range(initial_detection_attempts):
        if stop_event.is_set():
            break
        _, det0 = _detect_with_retry(grab_frame_fn, detect, max_detection_retries)
        if det0.found:
            break
        time.sleep(initial_detection_delay_s)
    if det0 is None or not det0.found:
        raise RuntimeError("Initial board detection failed.")

    feasible = compute_feasible_region(image_info, det0, margin_px=margin_px)
    regions = make_grid_regions(feasible, grid_rows=grid_rows, grid_cols=grid_cols)
    jacobian = estimate_local_xy_jacobian(
        get_pose_fn,
        move_relative_stable,
        move_absolute_stable,
        grab_frame_fn,
        detect,
        probe_dx_mm,
        probe_dy_mm,
        probe_drx_deg,
        probe_dry_deg,
        probe_drz_deg,
        max_detection_retries,
        move_absolute_fast_fn=move_absolute_fn,
    )
    origin_pose = get_pose_fn()
    origin_uv = np.array(det0.center_px, dtype=float)
    adapt_data: List[Tuple[np.ndarray, np.ndarray]] = []

    def maybe_update_jacobian(current_pose: List[float], current_uv: Tuple[float, float]) -> LocalJacobian2D:
        nonlocal jacobian
        d_robot = np.array(current_pose[:2], dtype=float) - np.array(origin_pose[:2], dtype=float)
        d_uv = np.array(current_uv, dtype=float) - origin_uv
        if np.linalg.norm(d_robot) < 1.0:
            return jacobian
        adapt_data.append((d_robot, d_uv))
        if len(adapt_data) >= 3:
            A = np.array([p[0] for p in adapt_data])
            B = np.array([p[1] for p in adapt_data])
            J_fit = np.linalg.lstsq(A, B, rcond=None)[0].T
            jacobian = LocalJacobian2D(J=J_fit, tilt_sensitivity=jacobian.tilt_sensitivity)
        return jacobian

    def attempt_placement(region: TargetRegion) -> bool:
        return move_board_center_near_region(
            grab_frame_fn=grab_frame_fn,
            move_relative_fn=move_relative_stable,
            detect_fn=detect,
            region=region,
            jacobian=jacobian,
            max_refines=2,
            gain=0.85,
            max_detection_retries=max_detection_retries,
        )

    for idx, region in enumerate(regions):
        if stop_event.is_set():
            break
        progress_cb(f"[{idx + 1}/{len(regions)}] Moving to region {region.name}...")
        move_absolute_stable(origin_pose)
        if not attempt_placement(region):
            progress_cb(f"  Placement failed for {region.name} - skipping region.")
            continue
        base_pose = get_pose_fn()
        frame, det = _detect_with_retry(grab_frame_fn, detect, max_detection_retries)
        if not det.found:
            continue
        maybe_update_jacobian(base_pose, det.center_px)
        if detection_callback is not None and det.bbox_px is not None:
            detection_callback(det.bbox_px, (image_info.width, image_info.height))
        path = save_frame_fn(frame, f"{region.name}_neutral")
        if path:
            samples.append(CaptureSample(region.name, "neutral", list(base_pose), path))
            progress_cb(f"  Captured neutral -> {path}")

        def capture_tilt_sample(tilt_axis: TiltAxis) -> None:
            sign = _predict_tilt_sign(det.center_px, image_info, tilt_axis, tilt_deg, jacobian)
            axis_idx = {TiltAxis.ROLL: 3, TiltAxis.PITCH: 4, TiltAxis.YAW: 5}[tilt_axis]
            tilted_pose = list(base_pose)
            tilted_pose[axis_idx] += sign * tilt_deg
            if not move_absolute_stable(tilted_pose):
                return
            tilted_frame, tilted_det = _detect_with_retry(grab_frame_fn, detect, max_detection_retries)
            if tilted_det.found:
                tilted_path = save_frame_fn(tilted_frame, f"{region.name}_{tilt_axis.value}")
                if tilted_path:
                    samples.append(CaptureSample(region.name, tilt_axis.value, list(get_pose_fn()), tilted_path))
                    progress_cb(f"  Captured {tilt_axis.value} -> {tilted_path}")
            move_absolute_stable(base_pose)

        if tilt_deg > 0:
            capture_tilt_sample(TiltAxis.ROLL)
            capture_tilt_sample(TiltAxis.PITCH)
        if z_delta_mm > 0:
            for label, delta in (("z_plus", z_delta_mm), ("z_minus", -z_delta_mm)):
                z_pose = list(base_pose)
                z_pose[2] += delta
                if not move_absolute_stable(z_pose):
                    continue
                z_frame, z_det = _detect_with_retry(grab_frame_fn, detect, max_detection_retries)
                if z_det.found:
                    z_path = save_frame_fn(z_frame, f"{region.name}_{label}")
                    if z_path:
                        samples.append(CaptureSample(region.name, label, list(get_pose_fn()), z_path))
                        progress_cb(f"  Captured {label} -> {z_path}")
                move_absolute_stable(base_pose)

    move_absolute_stable(origin_pose)
    return samples
