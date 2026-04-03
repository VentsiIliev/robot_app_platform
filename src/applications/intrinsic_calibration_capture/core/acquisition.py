from __future__ import annotations

import logging
import time
import threading
from typing import Callable, List, Optional, Tuple

import numpy as np

from src.applications.intrinsic_calibration_capture.core.data import (
    BoardDetection,
    BoardType,
    CaptureSample,
    ImageInfo,
    LocalJacobian2D,
    TargetRegion,
    TiltAxis,
)
from src.applications.intrinsic_calibration_capture.core.vision_helpers import (
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
    """
    Grab frames and attempt detection up to max_retries times.
    Returns the first successful detection, or the last failed attempt.
    """
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
    """
    Estimate local mapping from robot XY motion to image UV motion, and
    optionally from roll/pitch/yaw to image UV shift (tilt sensitivity).

    XY probes: two small moves (+X, +Y) to build the 2x2 Jacobian.
    Tilt probes: optional small rotations (+RX, +RY, +RZ) to measure how
    tilting shifts the board center in pixel space (px/deg).  Results are
    stored in LocalJacobian2D.tilt_sensitivity so the acquisition loop can
    choose the sign of each tilt that keeps the board visible.

    move_absolute_fast_fn: if provided, used for repositioning returns-to-base
    (no stabilization delay needed after the detection frame was already grabbed).
    """
    base_pose = get_pose_fn()
    _reposition = move_absolute_fast_fn if move_absolute_fast_fn is not None else move_absolute_fn

    _, det0 = _detect_with_retry(grab_frame_fn, detect_fn, max_detection_retries)
    if not det0.found or det0.center_px is None:
        raise RuntimeError("Cannot estimate Jacobian: board not detected at base pose.")
    u0, v0 = det0.center_px

    # ── XY probes ────────────────────────────────────────────────────────────

    # Probe +X
    if not move_relative_fn(dx=probe_dx_mm):
        raise RuntimeError("Failed X probe move.")
    _, det_x = _detect_with_retry(grab_frame_fn, detect_fn, max_detection_retries)
    _reposition(base_pose)

    if not det_x.found or det_x.center_px is None:
        raise RuntimeError("Board lost during X probe move.")
    ux, vx = det_x.center_px

    # Probe +Y
    if not move_relative_fn(dy=probe_dy_mm):
        raise RuntimeError("Failed Y probe move.")
    _, det_y = _detect_with_retry(grab_frame_fn, detect_fn, max_detection_retries)
    _reposition(base_pose)

    if not det_y.found or det_y.center_px is None:
        raise RuntimeError("Board lost during Y probe move.")
    uy, vy = det_y.center_px

    du_dx = (ux - u0) / probe_dx_mm
    dv_dx = (vx - v0) / probe_dx_mm
    du_dy = (uy - u0) / probe_dy_mm
    dv_dy = (vy - v0) / probe_dy_mm

    J = np.array(
        [[du_dx, du_dy],
         [dv_dx, dv_dy]],
        dtype=float,
    )
    _logger.info("XY Jacobian estimated:\n%s", J)

    # ── Tilt probes ───────────────────────────────────────────────────────────

    tilt_sensitivity: dict = {}

    def _probe_rotation(pose_index: int, angle_deg: float, axis: TiltAxis, label: str) -> None:
        """Probe one rotation axis; on success populate tilt_sensitivity[axis]."""
        if angle_deg == 0.0:
            return
        target = list(base_pose)
        target[pose_index] = base_pose[pose_index] + angle_deg
        if not move_absolute_fn(target):
            _logger.warning("Tilt probe move failed for %s — skipping", label)
            _reposition(base_pose)
            return
        _, det_r = _detect_with_retry(grab_frame_fn, detect_fn, max_detection_retries)
        _reposition(base_pose)  # detection done; return without stabilization delay
        if not det_r.found or det_r.center_px is None:
            _logger.warning("Board lost during %s probe — tilt sensitivity unavailable for %s", label, axis.value)
            return
        ur, vr = det_r.center_px
        sensitivity = np.array([(ur - u0) / angle_deg, (vr - v0) / angle_deg], dtype=float)
        tilt_sensitivity[axis] = sensitivity
        _logger.info(
            "Tilt sensitivity [%s] probed at %+.1f°: du/deg=%.3f  dv/deg=%.3f",
            label, angle_deg, sensitivity[0], sensitivity[1],
        )

    _probe_rotation(3, probe_drx_deg, TiltAxis.ROLL,  "RX/roll")
    _probe_rotation(4, probe_dry_deg, TiltAxis.PITCH, "RY/pitch")
    _probe_rotation(5, probe_drz_deg, TiltAxis.YAW,   "RZ/yaw")

    return LocalJacobian2D(J=J, tilt_sensitivity=tilt_sensitivity or None)


def _inside_target_region(det: BoardDetection, region: TargetRegion) -> bool:
    if not det.found or det.center_px is None:
        return False
    cx, cy = det.center_px
    tx, ty = region.center_px
    tol_x, tol_y = region.tol_px
    return (abs(cx - tx) <= tol_x) and (abs(cy - ty) <= tol_y)


def _board_has_safe_margin(
    det: BoardDetection,
    image: ImageInfo,
    min_margin_px: float = 40.0,
) -> bool:
    if not det.found or det.bbox_px is None:
        return False
    min_x, min_y, max_x, max_y = det.bbox_px
    return (
        min_x >= min_margin_px
        and min_y >= min_margin_px
        and max_x <= image.width - min_margin_px
        and max_y <= image.height - min_margin_px
    )


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
    """
    Move robot so that the board center lands near the target pixel region.
    Uses one Jacobian-predicted jump followed by small refinement steps.
    """
    _, det = _detect_with_retry(grab_frame_fn, detect_fn, max_detection_retries)
    if not det.found or det.center_px is None:
        return False

    if _inside_target_region(det, region):
        return True

    for _ in range(max_refines + 1):
        cx, cy = det.center_px
        tx, ty = region.center_px

        du = tx - cx
        dv = ty - cy

        dx, dy = jacobian.robot_delta_from_pixel_error(du, dv)

        ok = move_relative_fn(dx=gain * dx, dy=gain * dy)
        if not ok:
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
    """
    Choose +1 or -1 for the tilt sign that moves the board center closer to the
    image centre (and away from the nearest edge), using the probed tilt sensitivity.

    Scoring:
      - An out-of-bounds prediction (board centre outside the safe region) is
        penalised by 1e6 so it is always ranked worse than any in-bounds option.
      - Among in-bounds options, prefer the one that minimises the distance from the
        image centre — keeping the board well away from all edges.

    Falls back to +1 if sensitivity data is unavailable for the requested axis.
    """
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
        du = float(sensitivity[0] * tilt_deg * sign)
        dv = float(sensitivity[1] * tilt_deg * sign)
        new_cx = cx + du
        new_cy = cy + dv

        in_bounds = (
            margin_px <= new_cx <= image_info.width - margin_px
            and margin_px <= new_cy <= image_info.height - margin_px
        )
        dist_to_centre = -np.hypot(new_cx - img_cx, new_cy - img_cy)
        score = dist_to_centre if in_bounds else dist_to_centre - 1e6

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
    """
    ChArUco-specific acquisition: sweeps the robot across a grid of absolute poses
    and captures any frame where enough ChArUco corners are visible.

    No Jacobian estimation or servo loop — the robot moves to each pre-computed pose
    directly and detection succeeds even with partial board visibility, giving natural
    coverage of image edges and corners without requiring precise positioning.

    Per-cell variants: neutral, ±RX, ±RY, ±RZ (if rz_deg>0), ±Z (if z_delta_mm>0).
    Robot poses are stored in every CaptureSample for later hand-eye calibration reuse.
    """
    from src.engine.vision.implementation.VisionSystem.features.calibration.charuco import (
        AutoCharucoBoardDetector,
    )

    home_pose = get_pose_fn()

    # Build detector once for the whole session.
    detector = AutoCharucoBoardDetector(
        squares_x=pattern_size[0],
        squares_y=pattern_size[1],
        square_length=square_size_mm,
        marker_length=marker_size_mm,
        dictionary_id=aruco_dict_id,
    )

    def _count_corners(frame: np.ndarray) -> int:
        if frame is None:
            return 0
        result = detector.detect(frame)
        return 0 if result.charuco_ids is None else len(result.charuco_ids)

    def _grab_and_count() -> Tuple[np.ndarray, int]:
        for _ in range(max(1, max_detection_retries)):
            frame = grab_frame_fn()
            n = _count_corners(frame)
            if n >= min_corners:
                return frame, n
            time.sleep(0.05)
        return frame, n

    # ── Verify board visible at home pose ────────────────────────────────────
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
            progress_cb(
                f"  Not enough corners at home ({home_n}, need ≥{min_corners}), "
                f"retrying in {initial_detection_delay_s:.1f}s…"
            )
            time.sleep(initial_detection_delay_s)

    if home_n < min_corners:
        raise RuntimeError(
            f"ChArUco board not detected at home pose ({home_n} corners, need ≥{min_corners}). "
            "Position the board in the camera view."
        )

    # Record board centre at home for J fitting.
    home_result = detector.detect(home_frame)
    home_uv: Optional[np.ndarray] = None
    if home_result.charuco_corners is not None:
        c = home_result.charuco_corners.reshape(-1, 2)
        home_uv = np.array([float(np.mean(c[:, 0])), float(np.mean(c[:, 1]))])
    progress_cb(f"Board detected at home ({home_n} corners). Building sweep poses…")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _detection_result(frame: np.ndarray):
        """Run full detection once; returns (result, n_corners, bbox_or_None, center_or_None)."""
        result = detector.detect(frame)
        n = 0 if result.charuco_ids is None else len(result.charuco_ids)
        if result.charuco_corners is not None and n > 0:
            corners = result.charuco_corners.reshape(-1, 2)
            bbox = (float(np.min(corners[:, 0])), float(np.min(corners[:, 1])),
                    float(np.max(corners[:, 0])), float(np.max(corners[:, 1])))
            center = np.array([float(np.mean(corners[:, 0])), float(np.mean(corners[:, 1]))])
        else:
            bbox, center = None, None
        return result, n, bbox, center

    def _grab_and_detect():
        """Grab with retries; returns (frame, n, bbox, center)."""
        frame = grab_frame_fn()
        for _ in range(max(1, max_detection_retries)):
            _, n, bbox, center = _detection_result(frame)
            if n >= min_corners:
                return frame, n, bbox, center
            time.sleep(0.05)
            frame = grab_frame_fn()
        return frame, n, bbox, center

    # ── Generate candidate poses ──────────────────────────────────────────────
    xs = np.linspace(-sweep_x_mm, sweep_x_mm, grid_cols) if grid_cols > 1 else [0.0]
    ys = np.linspace(-sweep_y_mm, sweep_y_mm, grid_rows) if grid_rows > 1 else [0.0]

    candidates: List[Tuple[str, List[float]]] = []
    for ri, dy in enumerate(ys):
        for ci, dx in enumerate(xs):
            prefix = f"r{ri}_c{ci}"
            base = [home_pose[0]+float(dx), home_pose[1]+float(dy),
                    home_pose[2], home_pose[3], home_pose[4], home_pose[5]]
            candidates.append((f"{prefix}_neutral", base))
            if tilt_deg > 0:
                rx_p = list(base); rx_p[3] += tilt_deg
                rx_n = list(base); rx_n[3] -= tilt_deg
                ry_p = list(base); ry_p[4] += tilt_deg
                ry_n = list(base); ry_n[4] -= tilt_deg
                candidates.append((f"{prefix}_rx+", rx_p))
                candidates.append((f"{prefix}_rx-", rx_n))
                candidates.append((f"{prefix}_ry+", ry_p))
                candidates.append((f"{prefix}_ry-", ry_n))
            if rz_deg > 0:
                rz_p = list(base); rz_p[5] += rz_deg
                rz_n = list(base); rz_n[5] -= rz_deg
                candidates.append((f"{prefix}_rz+", rz_p))
                candidates.append((f"{prefix}_rz-", rz_n))
            if z_delta_mm > 0:
                zp = list(base); zp[2] += z_delta_mm
                zm = list(base); zm[2] -= z_delta_mm
                candidates.append((f"{prefix}_z+", zp))
                candidates.append((f"{prefix}_z-", zm))

    progress_cb(f"Sweep: {len(candidates)} candidate poses "
                f"({grid_rows}×{grid_cols} grid, "
                f"{len(candidates) // (grid_rows * grid_cols)} variants/cell).")

    # ── Execute sweep ─────────────────────────────────────────────────────────
    samples: List[CaptureSample] = []
    # Adaptive J data: (Δrobot_xy, Δboard_uv) pairs from neutral detections.
    j_data: List[Tuple[np.ndarray, np.ndarray]] = []
    saved_bboxes: List[Tuple] = []   # for local coverage computation
    frame_hw: Optional[Tuple[int, int]] = None

    def _record(frame: np.ndarray, tag: str, pose: List[float],
                 n: int, bbox, center) -> None:
        """Save frame, update J data, notify callback."""
        path = save_frame_fn(frame, tag)
        if not path:
            return
        current_pose = get_pose_fn()
        samples.append(CaptureSample(tag.rsplit("_", 1)[0], tag.rsplit("_", 1)[1], current_pose, path))
        progress_cb(f"  Saved ({n} corners) → {path}")
        if bbox is not None:
            saved_bboxes.append(bbox)
            if detection_callback is not None:
                h, w = frame.shape[:2]
                detection_callback(bbox, (w, h))
        # Collect J data only for neutral (no tilt/Z offset) poses.
        if tag.endswith("_neutral") and home_uv is not None and center is not None:
            d_robot = np.array(pose[:2]) - np.array(home_pose[:2])
            d_uv    = center - home_uv
            if np.linalg.norm(d_robot) > 1.0:   # skip near-home point
                j_data.append((d_robot, d_uv))

    for idx, (tag, pose) in enumerate(candidates):
        if stop_event.is_set():
            progress_cb("Acquisition stopped by user.")
            break
        progress_cb(f"[{idx + 1}/{len(candidates)}] → {tag}")
        if not move_absolute_fn(pose):
            progress_cb("  Move failed — skipping.")
            continue
        if stabilization_delay_s > 0:
            time.sleep(stabilization_delay_s)
        frame, n, bbox, center = _grab_and_detect()
        if frame_hw is None and frame is not None:
            frame_hw = frame.shape[:2]
        if n < min_corners:
            progress_cb(f"  Only {n} corners (need ≥{min_corners}) — skipping.")
            continue
        _record(frame, tag, pose, n, bbox, center)

    # ── Gap-filling pass using fitted Jacobian ────────────────────────────────
    if not stop_event.is_set() and len(j_data) >= 3 and frame_hw is not None and home_uv is not None:
        A = np.array([d[0] for d in j_data])
        B = np.array([d[1] for d in j_data])
        J_fit    = np.linalg.lstsq(A, B, rcond=None)[0].T   # 2×2  robot→uv
        J_inv    = np.linalg.pinv(J_fit)                     # 2×2  uv→robot

        # Build local coverage grid (same resolution as the overlay).
        GCOLS, GROWS = 8, 6
        h, w = frame_hw
        cw, ch = w / GCOLS, h / GROWS
        grid = np.zeros((GROWS, GCOLS), dtype=np.float32)
        for (x1, y1, x2, y2) in saved_bboxes:
            for r in range(max(0, int(y1/ch)), min(GROWS, int(y2/ch)+1)):
                for c in range(max(0, int(x1/cw)), min(GCOLS, int(x2/cw)+1)):
                    grid[r, c] += 1

        gap_cells = [(r, c) for r in range(GROWS) for c in range(GCOLS) if grid[r, c] == 0]
        progress_cb(
            f"Jacobian fitted from {len(j_data)} neutral placements. "
            f"Gap-filling {len(gap_cells)} uncovered cells…"
        )

        for gi, (r, c) in enumerate(gap_cells):
            if stop_event.is_set():
                break
            target_uv  = np.array([(c + 0.5) * cw, (r + 0.5) * ch])
            d_uv       = target_uv - home_uv
            d_robot    = J_inv @ d_uv
            gap_pose   = list(home_pose)
            gap_pose[0] += float(d_robot[0])
            gap_pose[1] += float(d_robot[1])
            tag = f"gap_r{r}_c{c}_neutral"
            progress_cb(f"  Gap [{gi+1}/{len(gap_cells)}] cell({r},{c}) → {tag}")
            if not move_absolute_fn(gap_pose):
                progress_cb("  Move failed — skipping.")
                continue
            if stabilization_delay_s > 0:
                time.sleep(stabilization_delay_s)
            frame, n, bbox, center = _grab_and_detect()
            if n < min_corners:
                progress_cb(f"  Only {n} corners — skipping.")
                continue
            _record(frame, tag, gap_pose, n, bbox, center)
            # Update J with this new data point too.
            if center is not None:
                d_r = np.array(gap_pose[:2]) - np.array(home_pose[:2])
                if np.linalg.norm(d_r) > 1.0:
                    j_data.append((d_r, center - home_uv))
    elif len(j_data) < 3:
        progress_cb("Not enough neutral detections to fit Jacobian — gap-fill skipped.")

    # Return to home
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
    # ChArUco sweep parameters (used only when board_type == CHARUCO)
    charuco_sweep_x_mm: float = 100.0,
    charuco_sweep_y_mm: float = 100.0,
    charuco_min_corners: int = 6,
    charuco_rz_deg: float = 0.0,
    detection_callback: Optional[Callable] = None,
) -> List[CaptureSample]:
    """
    Main acquisition dispatcher.

    For CHARUCO boards: delegates to capture_charuco_sweep_dataset() which moves
    the robot across a grid of pre-computed poses and accepts partial board
    visibility — no Jacobian estimation or servo required.

    For CHESSBOARD boards: uses the original Jacobian+servo loop to precisely
    place the board centre at each grid region, with an adaptive Jacobian that
    is re-fitted from real move data after each successful placement.

    detection_callback(bbox_px, image_size) is called for every accepted detection.
    """
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

    # ── Chessboard: original Jacobian+servo loop ──────────────────────────────
    samples: List[CaptureSample] = []

    # Bind board-type-specific params into a single detect callable
    def _detect(frame: np.ndarray) -> BoardDetection:
        return detect_board(
            frame, pattern_size, board_type,
            square_size_mm=square_size_mm,
            marker_size_mm=marker_size_mm,
            aruco_dict_id=aruco_dict_id,
        )

    # Wrap move functions so every move is followed by a stabilization delay
    def _move_relative_stable(**kwargs) -> bool:
        ok = move_relative_fn(**kwargs)
        if ok and stabilization_delay_s > 0:
            time.sleep(stabilization_delay_s)
        return ok

    def _move_absolute_stable(pose: List[float]) -> bool:
        ok = move_absolute_fn(pose)
        if ok and stabilization_delay_s > 0:
            time.sleep(stabilization_delay_s)
        return ok

    board_label = "CharuCo" if board_type == BoardType.CHARUCO else "chessboard"
    progress_cb(f"Detecting {board_label} at start pose...")
    det0 = None
    for _init_attempt in range(initial_detection_attempts):
        if stop_event.is_set():
            break
        frame0, det0 = _detect_with_retry(grab_frame_fn, _detect, max_detection_retries)
        if det0.found:
            break
        # On first failure, save the raw frame so the operator can inspect it
        if _init_attempt == 0 and frame0 is not None:
            import cv2 as _cv2, os as _os, tempfile as _tmp
            _diag_path = _os.path.join(_tmp.gettempdir(), "_diag_initial_frame.png")
            _cv2.imwrite(_diag_path, frame0)
            progress_cb(f"  Diagnostic frame saved → {_diag_path}")
        remaining = initial_detection_attempts - _init_attempt - 1
        if remaining > 0:
            progress_cb(
                f"  Board not detected (attempt {_init_attempt + 1}/{initial_detection_attempts}), "
                f"retrying in {initial_detection_delay_s:.1f}s..."
            )
            time.sleep(initial_detection_delay_s)
    if det0 is None or not det0.found:
        raise RuntimeError(
            f"Initial {board_label} detection failed after {initial_detection_attempts} attempts. "
            "Position the board in the camera view."
        )

    progress_cb(
        f"Board detected: {det0.width_px:.0f}×{det0.height_px:.0f} px, "
        f"center ({det0.center_px[0]:.0f}, {det0.center_px[1]:.0f}), "
        f"image {image_info.width}×{image_info.height} px"
    )
    feasible = compute_feasible_region(image_info, det0, margin_px=margin_px)
    progress_cb(
        f"Feasible center region: x=[{feasible.min_cx:.0f}..{feasible.max_cx:.0f}], "
        f"y=[{feasible.min_cy:.0f}..{feasible.max_cy:.0f}]"
    )
    regions = make_grid_regions(feasible, grid_rows=grid_rows, grid_cols=grid_cols)
    progress_cb(f"Grid: {len(regions)} regions ({grid_rows}x{grid_cols})")

    progress_cb("Estimating XY Jacobian (probing robot motion)...")
    jacobian = estimate_local_xy_jacobian(
        get_pose_fn, _move_relative_stable, _move_absolute_stable, grab_frame_fn,
        _detect, probe_dx_mm, probe_dy_mm,
        probe_drx_deg, probe_dry_deg, probe_drz_deg,
        max_detection_retries,
        move_absolute_fast_fn=move_absolute_fn,  # returns-to-base skip the stabilization wait
    )
    if jacobian.tilt_sensitivity:
        axes_probed = ", ".join(a.value for a in jacobian.tilt_sensitivity)
        progress_cb(f"Jacobian estimated (tilt sensitivity: {axes_probed}).")
    else:
        progress_cb("Jacobian estimated (no tilt sensitivity — tilt signs will alternate).")

    # Save the pose where the board was detected — used as the recovery origin
    # between region attempts so a failed placement doesn't cascade.
    origin_pose = get_pose_fn()
    origin_uv   = np.array(det0.center_px, dtype=float)

    # Adaptive Jacobian: accumulates (Δrobot_xy, Δimage_uv) pairs from real moves.
    # After ≥3 pairs the J is re-fitted and used for all subsequent placements.
    _adapt_data: List[Tuple[np.ndarray, np.ndarray]] = []

    def _maybe_update_jacobian(current_pose: List[float], current_uv: Tuple[float, float]) -> None:
        nonlocal jacobian
        d_robot = np.array(current_pose[:2], dtype=float) - np.array(origin_pose[:2], dtype=float)
        d_uv    = np.array(current_uv, dtype=float) - origin_uv
        if np.linalg.norm(d_robot) < 1.0:   # ignore sub-mm moves (effectively at origin)
            return
        _adapt_data.append((d_robot, d_uv))
        if len(_adapt_data) < 3:
            return
        A = np.array([p[0] for p in _adapt_data])   # Nx2
        B = np.array([p[1] for p in _adapt_data])   # Nx2
        J_fit = np.linalg.lstsq(A, B, rcond=None)[0].T  # 2x2
        jacobian = LocalJacobian2D(J=J_fit, tilt_sensitivity=jacobian.tilt_sensitivity)
        progress_cb(f"  Jacobian refined from {len(_adapt_data)} real placements.")

    def _attempt_placement(region: TargetRegion) -> bool:
        return move_board_center_near_region(
            grab_frame_fn=grab_frame_fn,
            move_relative_fn=_move_relative_stable,
            detect_fn=_detect,
            region=region,
            jacobian=jacobian,
            max_refines=2,   # initial Jacobian jump + 2 corrections
            gain=0.85,
            max_detection_retries=max_detection_retries,
        )

    def _try_recovery_pose(approach_pose: List[float], label: str) -> bool:
        """Move to approach_pose, verify board visible, then attempt placement. Returns True on success."""
        progress_cb(f"  Recovery: {label}...")
        if not _move_absolute_stable(approach_pose):
            return False
        _, det_check = _detect_with_retry(grab_frame_fn, _detect, max_detection_retries)
        if not det_check.found:
            _move_absolute_stable(origin_pose)
            return False
        if _attempt_placement(region):
            progress_cb(f"  Recovery succeeded ({label}).")
            return True
        _move_absolute_stable(origin_pose)
        return False

    def _step_back_recovery(
        region: TargetRegion,
        step_mm: float = 10.0,
        max_reverse_mm: float = 80.0,
    ) -> bool:
        """
        From the current (failed) position, interpolate back toward origin_pose
        in small XYZ steps.  At each step, check if the board is visible.
        Once visible, attempt placement.  Gives up after max_reverse_mm.
        """
        current = get_pose_fn()
        if not current or len(current) < 3:
            return False
        total_dist = float(np.linalg.norm([origin_pose[i] - current[i] for i in range(3)]))
        if total_dist < 1.0:
            return False
        n_steps = max(1, int(min(total_dist, max_reverse_mm) / step_mm))
        progress_cb(
            f"  Step-back recovery: up to {n_steps} step(s) × {step_mm:.0f} mm toward origin..."
        )
        for i in range(1, n_steps + 1):
            if stop_event.is_set():
                return False
            t = min((i * step_mm) / total_dist, 1.0)
            pose = list(current)
            for axis in range(3):
                pose[axis] = current[axis] + t * (origin_pose[axis] - current[axis])
            if not _move_absolute_stable(pose):
                continue
            _, det_check = _detect_with_retry(grab_frame_fn, _detect, max_detection_retries)
            if det_check.found:
                progress_cb(f"  Board found at step {i}/{n_steps} — attempting placement...")
                if _attempt_placement(region):
                    progress_cb("  Step-back recovery succeeded.")
                    return True
                progress_cb("  Placement failed at recovery position — continuing steps...")
        return False

    for idx, region in enumerate(regions):
        if stop_event.is_set():
            progress_cb("Acquisition stopped by user.")
            break

        progress_cb(f"[{idx + 1}/{len(regions)}] Moving to region {region.name}...")

        # Always return to origin before each region so a previous failure
        # does not leave the robot in an unknown position.
        _move_absolute_stable(origin_pose)

        ok = _attempt_placement(region)

        if not ok:
            _logger.warning("Primary placement failed for %s — trying recovery", region.name)

            # Phase 0: step back toward origin until board found, then retry placement
            ok = _step_back_recovery(region)

            # Phase 1: Z-only — changing height shifts the effective XY workspace
            for dz in [20.0, -20.0]:
                if stop_event.is_set() or ok:
                    break
                pose = list(origin_pose)
                pose[2] += dz
                ok = _try_recovery_pose(pose, f"Z{dz:+.0f}mm")

            # Phase 2: Z + lateral XY — for edge/corner cells whose target is laterally
            # unreachable from origin; a shorter approach reduces Jacobian prediction error.
            if not ok:
                for dz in [20.0, -20.0]:
                    for dxy in [40.0, -40.0]:
                        if stop_event.is_set() or ok:
                            break
                        for axis in (0, 1):
                            if stop_event.is_set() or ok:
                                break
                            pose = list(origin_pose)
                            pose[2] += dz
                            pose[axis] += dxy
                            ok = _try_recovery_pose(
                                pose,
                                f"Z{dz:+.0f}mm {'X' if axis == 0 else 'Y'}{dxy:+.0f}mm",
                            )

        if not ok:
            _logger.error("Failed to move board center near region %s (all recovery attempts exhausted)", region.name)
            _move_absolute_stable(origin_pose)
            progress_cb(f"  Placement failed for {region.name} — skipping region.")
            continue

        base_pose = get_pose_fn()

        # 1) Neutral
        frame, det = _detect_with_retry(grab_frame_fn, _detect, max_detection_retries)
        if not det.found:
            progress_cb(f"  No board visible at {region.name}, skipping region.")
            continue

        # Update adaptive Jacobian from this real placement.
        _maybe_update_jacobian(base_pose, det.center_px)

        # Record coverage.
        if detection_callback is not None and det.bbox_px is not None:
            detection_callback(det.bbox_px, (image_info.width, image_info.height))

        path = save_frame_fn(frame, f"{region.name}_neutral")
        if path:
            samples.append(CaptureSample(region.name, "neutral", list(base_pose), path))
            progress_cb(f"  Captured neutral → {path}")

        # 2–3) Roll + pitch tilts — both captured for every cell.
        #      Sign is chosen independently for each axis via tilt-sensitivity prediction
        #      (falls back to alternating pattern when no probe data is available).

        def _capture_tilt_sample(tilt_axis: TiltAxis) -> None:
            """Capture one tilt image; always returns the robot to base_pose on exit."""
            if jacobian.tilt_sensitivity and tilt_axis in jacobian.tilt_sensitivity:
                sign = _predict_tilt_sign(
                    board_center=det.center_px,
                    image_info=image_info,
                    tilt_axis=tilt_axis,
                    tilt_deg=tilt_deg,
                    jacobian=jacobian,
                    margin_px=margin_px,
                )
                progress_cb(
                    f"  [{tilt_axis.value}] sign predicted: {sign:+.0f}  "
                    f"(board centre ({det.center_px[0]:.0f}, {det.center_px[1]:.0f}) px)"
                )
            else:
                sign = 1.0 if ((idx // 2) % 2 == 0) else -1.0
                progress_cb(f"  [{tilt_axis.value}] sign (fallback alternating): {sign:+.0f}")

            angle = sign * tilt_deg
            tilt_target = list(base_pose)
            if tilt_axis == TiltAxis.ROLL:
                tilt_target[3] = base_pose[3] + angle
            else:
                tilt_target[4] = base_pose[4] + angle

            progress_cb(
                f"  [{tilt_axis.value}] {angle:+.1f}°  "
                f"→ RX={tilt_target[3]:.2f}° RY={tilt_target[4]:.2f}°"
            )
            if not _move_absolute_stable(tilt_target):
                progress_cb(f"  [{tilt_axis.value}] move failed — skipping.")
                return

            tilt_pose = get_pose_fn()
            frame_t, det_t = _detect_with_retry(grab_frame_fn, _detect, max_detection_retries)

            # Recovery: try 50% angle if board lost
            if not det_t.found and not stop_event.is_set():
                _move_absolute_stable(base_pose)
                reduced = angle * 0.5
                reduced_target = list(base_pose)
                if tilt_axis == TiltAxis.ROLL:
                    reduced_target[3] = base_pose[3] + reduced
                else:
                    reduced_target[4] = base_pose[4] + reduced
                progress_cb(f"  [{tilt_axis.value}] recovery: {reduced:+.1f}° (50%)...")
                if _move_absolute_stable(reduced_target):
                    tilt_pose = get_pose_fn()
                    frame_t, det_t = _detect_with_retry(grab_frame_fn, _detect, max_detection_retries)
                    if det_t.found:
                        progress_cb(f"  [{tilt_axis.value}] recovery succeeded at {reduced:+.1f}°")

            if det_t.found:
                path = save_frame_fn(frame_t, f"{region.name}_{tilt_axis.value}")
                if path:
                    samples.append(CaptureSample(region.name, tilt_axis.value, list(tilt_pose), path))
                    progress_cb(f"  Captured {tilt_axis.value} → {path}")
            else:
                progress_cb(f"  [{tilt_axis.value}] board not visible — skipping.")

            _move_absolute_stable(base_pose)

        _capture_tilt_sample(TiltAxis.ROLL)
        if stop_event.is_set():
            break

        _capture_tilt_sample(TiltAxis.PITCH)
        if stop_event.is_set():
            break

        # 3) Z change: alternate closer/farther
        z_sign = 1.0 if (idx % 3 == 0) else -1.0
        progress_cb(f"  Applying Z shift: {z_sign * z_delta_mm:+.1f} mm")
        z_ok = _move_relative_stable(dz=z_sign * z_delta_mm)

        if z_ok:
            frame, det = _detect_with_retry(grab_frame_fn, _detect, max_detection_retries)
            if det.found and _board_has_safe_margin(det, image_info):
                path = save_frame_fn(frame, f"{region.name}_z")
                if path:
                    samples.append(CaptureSample(region.name, "z", get_pose_fn(), path))
                    progress_cb(f"  Captured Z-shift → {path}")
            _move_absolute_stable(base_pose)

        # 4) Additional Z capture at +z_delta_mm for diversity
        if stop_event.is_set():
            break
        progress_cb(f"  Applying +Z shift: +{z_delta_mm:.1f} mm")
        z2_ok = _move_relative_stable(dz=z_delta_mm)
        if z2_ok:
            frame, det = _detect_with_retry(grab_frame_fn, _detect, max_detection_retries)
            if det.found and _board_has_safe_margin(det, image_info):
                path = save_frame_fn(frame, f"{region.name}_z2")
                if path:
                    samples.append(CaptureSample(region.name, "z2", get_pose_fn(), path))
                    progress_cb(f"  Captured +Z-shift → {path}")
            _move_absolute_stable(base_pose)

    progress_cb(f"Acquisition complete: {len(samples)} images captured.")
    return samples
