from __future__ import annotations

import logging
import math
import threading
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np

from src.applications.hand_eye_calibration.core.hand_eye_core import (
    compute_hand_eye,
    detect_board_center,
    detect_board_info,
    detect_chessboard_pose,
    generate_diverse_poses,
    tcp_to_matrix,
)
from src.applications.hand_eye_calibration.service.i_hand_eye_service import (
    HAND_EYE_COMPLETE_TOPIC,
    HAND_EYE_PROGRESS_TOPIC,
    HAND_EYE_SAMPLE_COUNT_TOPIC,
    HandEyeConfig,
    IHandEyeCalibrationService,
)
from src.engine.vision.i_capture_snapshot_service import ICaptureSnapshotService

_logger = logging.getLogger(__name__)


class HandEyeCalibrationService(IHandEyeCalibrationService):
    """
    Automated hand-eye calibration service.

    Moves the robot through a set of diverse poses, captures a chessboard
    detection at each, and runs cv2.calibrateHandEye() to produce the
    camera-to-flange transform.
    """

    def __init__(
        self,
        snapshot_service: ICaptureSnapshotService,
        robot_service,
        vision_service,
        robot_config,
        messaging=None,
    ):
        self._snapshot = snapshot_service
        self._robot = robot_service
        self._vision = vision_service
        self._robot_config = robot_config
        self._messaging = messaging
        self._config = HandEyeConfig()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── IHandEyeCalibrationService ────────────────────────────────────────────

    def start_capture(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            _logger.warning("Hand-eye calibration already running.")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop_capture(self) -> None:
        self._stop_event.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_latest_annotated_frame(self) -> Optional[np.ndarray]:
        frame = self._get_frame()
        if frame is None:
            return None
        # Skip detection while calibration thread is running — concurrent
        # cv2.findChessboardCorners calls from Qt main thread and the
        # calibration thread are not safe and cause random crashes/interrupts.
        if self.is_running():
            return frame
        cfg = self._config
        K, dist = self._camera_params()
        if K is None:
            return frame
        _, _, annotated = detect_chessboard_pose(
            frame, (cfg.chessboard_width, cfg.chessboard_height), cfg.square_size_mm, K, dist
        )
        return annotated

    def get_config(self) -> HandEyeConfig:
        return self._config

    def save_config(self, config: HandEyeConfig) -> None:
        self._config = config

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run(self) -> None:
        self._lock_brightness()
        try:
            self._collect_and_calibrate()
        except Exception as exc:
            _logger.exception("Hand-eye calibration failed: %s", exc)
            self._publish(f"ERROR: {exc}")
        finally:
            self._unlock_brightness()

    def _collect_and_calibrate(self) -> None:
        cfg = self._config
        K, dist = self._camera_params()
        if K is None:
            self._publish("ERROR: Camera matrix not available. Run intrinsic calibration first.")
            return

        # --- Verify board visible at home pose ---
        home_pose = self._robot.get_current_position()
        self._publish(f"Home pose: {[f'{v:.1f}' for v in home_pose]}")
        self._publish("Checking chessboard visibility at home pose...")

        raw_frame = self._get_frame()
        if raw_frame is None:
            self._publish("ERROR: No raw camera frame at home pose.")
            return

        R_c, t_c, _ = detect_chessboard_pose(
            raw_frame, (cfg.chessboard_width, cfg.chessboard_height), cfg.square_size_mm, K, dist
        )
        if R_c is None:
            self._publish(
                f"ERROR: Chessboard ({cfg.chessboard_width}×{cfg.chessboard_height} inner corners, "
                f"{cfg.square_size_mm} mm squares) not detected at home pose. "
                "Ensure the board is fully in frame and settings match the physical board."
            )
            return

        # Compute home pixels-per-mm from the board's bounding box.
        # Used later to dynamically re-scale the Jacobian at each pose.
        _phys_board_w = (cfg.chessboard_width - 1) * cfg.square_size_mm
        _home_info = detect_board_info(raw_frame, (cfg.chessboard_width, cfg.chessboard_height))
        _home_ppm = (_home_info.bbox_w / _phys_board_w) if (_home_info and _phys_board_w > 0) else None

        # Home board centre in pixels — used for feedforward and blind recovery.
        _home_center = (
            np.array([_home_info.cx, _home_info.cy]) if _home_info is not None else None
        )
        # Conservative FOV safety margin: half board diagonal + 80 px buffer.
        _board_half_diag = (
            0.5 * math.hypot(_home_info.bbox_w, _home_info.bbox_h)
            if _home_info is not None else 0.0
        )

        self._publish("Chessboard detected at home pose.")

        # --- Estimate Jacobian via probe moves ---
        self._publish(
            f"Estimating {'2×6' if cfg.probe_rotations else '2×3'} Jacobian "
            f"(probe dx={cfg.probe_dx_mm} dy={cfg.probe_dy_mm} dz={cfg.probe_dz_mm} mm"
            + (f" drx/dry/drz={cfg.probe_drx_deg}°" if cfg.probe_rotations else "")
            + ")..."
        )
        jacobian = self._estimate_jacobian(home_pose, cfg, K, dist)
        if jacobian is None:
            self._publish("WARNING: Jacobian estimation failed — visual servo disabled.")
        else:
            self._publish(f"Jacobian:\n{np.array2string(jacobian, precision=3)}")

        # --- Generate diverse candidate poses ---
        candidates = generate_diverse_poses(
            home_pose,
            n_poses=cfg.n_poses,
            rx_range_deg=cfg.rx_range_deg,
            ry_range_deg=cfg.ry_range_deg,
            rz_range_deg=cfg.rz_range_deg,
            xy_range_mm=cfg.xy_range_mm,
            z_range_mm=cfg.z_range_mm,
        )

        # Pre-adjust candidate XY so J predicts the board stays within the FOV.
        # This converts the problem from reactive (servo to recover) to proactive
        # (arrive with board already near centre).  Rotation/Z are kept as-is.
        image_h, image_w = raw_frame.shape[:2]
        if jacobian is not None and _home_center is not None:
            candidates = self._adjust_candidates_for_visibility(
                candidates, home_pose, _home_center,
                jacobian, image_w, image_h, _board_half_diag,
            )
            self._publish(
                f"Generated {len(candidates)} visibility-adjusted candidate poses."
            )
        else:
            self._publish(f"Generated {len(candidates)} candidate poses (no visibility adjustment).")

        R_robot_list: List[np.ndarray] = []
        t_robot_list: List[np.ndarray] = []
        R_cam_list: List[np.ndarray] = []
        t_cam_list: List[np.ndarray] = []

        for i, pose in enumerate(candidates):
            if self._stop_event.is_set():
                self._publish("Stopped by user.")
                break

            self._publish(f"Pose {i + 1}/{len(candidates)}: {[f'{v:.1f}' for v in pose]}")

            # For large rotations the linear J breaks down over a single big
            # step.  Instead, walk to the target orientation in ≤10° increments,
            # applying a servo correction after each step.  This lets the J
            # stay accurate (small delta per step) and builds up the XY offset
            # needed to track the board all the way to extreme orientations.
            max_rot_delta = max(
                abs(pose[i] - home_pose[i]) for i in range(3, 6)
            ) if jacobian is not None else 0.0
            if max_rot_delta > 15.0 and jacobian is not None:
                pose = self._approach_pose_incrementally(
                    pose, home_pose, jacobian, cfg, image_w, image_h
                )
                if cfg.stabilization_delay_s > 0:
                    time.sleep(cfg.stabilization_delay_s)
            else:
                ok = self._move_absolute(pose)
                if not ok:
                    # Exact pose unreachable — drop XY, keep rotation/Z diversity.
                    safer = [home_pose[0], home_pose[1], pose[2],
                             pose[3], pose[4], pose[5]]
                    self._publish("  Move failed — trying home XY + candidate orientation.")
                    if not self._move_absolute(safer):
                        self._publish("  Safer pose also unreachable — skipping.")
                        continue
                    pose = safer
                if cfg.stabilization_delay_s > 0:
                    time.sleep(cfg.stabilization_delay_s)

            # Visual servo to fine-correct the residual drift.
            if jacobian is not None:
                R_c, t_c = self._servo_board_into_view(
                    jacobian, image_w, image_h, cfg, K, dist, _home_ppm, _phys_board_w
                )
                if R_c is None and _home_center is not None:
                    self._publish("  Servo failed — applying J-predicted blind recovery.")
                    recovered = self._jacobian_blind_recovery(
                        pose, home_pose, _home_center, jacobian,
                        image_w, image_h, cfg,
                    )
                    if recovered:
                        R_c, t_c = self._servo_board_into_view(
                            jacobian, image_w, image_h, cfg, K, dist, _home_ppm, _phys_board_w
                        )
            else:
                raw_frame = self._get_frame()
                R_c, t_c, _ = detect_chessboard_pose(
                    raw_frame,
                    (cfg.chessboard_width, cfg.chessboard_height),
                    cfg.square_size_mm, K, dist,
                ) if raw_frame is not None else (None, None, None)

            if R_c is None:
                # Both servo passes and J-recovery failed.
                # The board is almost certainly outside FOV due to orientation,
                # not translation — a 72-move XYZ grid search won't help and
                # wastes ~60 s.  Skip this pose and move on.
                self._publish("  Board not visible after servo + J-recovery — skipping pose.")
                continue

            # Snapshot for atomic robot pose (servo may have adjusted XY)
            snap = self._snapshot.capture_snapshot("hand_eye")
            if snap.robot_pose is None:
                self._publish("  No robot pose — skipping.")
                continue

            T_r = tcp_to_matrix(snap.robot_pose)
            R_robot_list.append(T_r[:3, :3])
            t_robot_list.append(T_r[:3, 3].reshape(3, 1))
            R_cam_list.append(R_c)
            t_cam_list.append(t_c)
            n = len(R_cam_list)
            self._publish(f"  Sample {n} captured.")
            self._publish_topic(HAND_EYE_SAMPLE_COUNT_TOPIC, n)

        # --- Return to home ---
        self._move_absolute(home_pose)
        self._publish("Returned to home pose.")

        if len(R_cam_list) < 4:
            self._publish(
                f"ERROR: Only {len(R_cam_list)} valid sample(s) collected — need at least 4. "
                "Increase n_poses or enlarge the ranges so more poses see the board."
            )
            return

        # --- Compute hand-eye ---
        self._publish(f"Computing hand-eye calibration from {len(R_cam_list)} samples...")
        try:
            T = compute_hand_eye(R_robot_list, t_robot_list, R_cam_list, t_cam_list)
        except cv2.error as exc:
            self._publish(f"ERROR: calibrateHandEye failed: {exc}")
            return

        # --- Save result ---
        # Save to a dedicated file — NOT camera_to_robot_matrix_path, which stores
        # a 3×3 homography for the standard calibration pipeline (incompatible format).
        save_path = self._hand_eye_save_path()
        if save_path:
            np.save(save_path, T)
            self._publish(f"Result saved → {save_path}")
        else:
            self._publish("WARNING: Could not determine save path — matrix NOT saved.")

        result_str = (
            f"Hand-eye calibration complete ({len(R_cam_list)} samples).\n"
            f"T_cam_to_flange =\n{np.array2string(T, precision=4, suppress_small=True)}"
        )
        # Log via progress topic; COMPLETE topic is for controller state only (not logged again).
        self._publish(result_str)
        self._publish_topic(HAND_EYE_COMPLETE_TOPIC, "")

    # ── Robot helpers ─────────────────────────────────────────────────────────

    def _move_relative(
        self,
        dx: float = 0.0, dy: float = 0.0, dz: float = 0.0,
        drx: float = 0.0, dry: float = 0.0, drz: float = 0.0,
    ) -> bool:
        pos = self._robot.get_current_position()
        target = [
            pos[0] + dx, pos[1] + dy, pos[2] + dz,
            pos[3] + drx, pos[4] + dry, pos[5] + drz,
        ]
        return self._robot.move_ptp(
            target,
            getattr(self._robot_config, "robot_tool", 1),
            getattr(self._robot_config, "robot_user", 1),
            self._config.velocity,
            self._config.acceleration,
            wait_to_reach=True,
        )

    def _move_absolute(self, pose: List[float]) -> bool:
        return self._robot.move_ptp(
            pose,
            getattr(self._robot_config, "robot_tool", 1),
            getattr(self._robot_config, "robot_user", 1),
            self._config.velocity,
            self._config.acceleration,
            wait_to_reach=True,
        )

    # ── Jacobian & visual servo ────────────────────────────────────────────────

    # ── Visibility-aware candidate adjustment ─────────────────────────────────

    def _adjust_candidates_for_visibility(
        self,
        candidates: List[List[float]],
        home_pose: List[float],
        home_center: np.ndarray,
        jacobian: np.ndarray,
        image_w: int,
        image_h: int,
        board_half_diag: float,
    ) -> List[List[float]]:
        """
        For each candidate pose, predict where the board centre will appear in
        the image using the Jacobian:

            predicted_pixel = home_center + J @ (candidate - home_pose)

        If the predicted centre falls outside a safe inner rectangle (image
        bounds shrunk by the board's half-diagonal + 80 px buffer), solve for
        the XY correction that brings it back to the image centre and apply it
        to the candidate.  Rotation and Z are left unchanged — rotation
        diversity drives calibration quality; only XY is adjusted.

        Because J is estimated at home (linear model), this pre-flight step is
        approximate.  The servo loop handles the residual nonlinear error after
        arrival.
        """
        margin = board_half_diag + 80.0
        safe_x_lo, safe_x_hi = margin, image_w - margin
        safe_y_lo, safe_y_hi = margin, image_h - margin
        target_px = np.array([image_w / 2.0, image_h / 2.0])

        J_xy = jacobian[:, :2]
        J_xy_pinv = np.linalg.pinv(J_xy)

        adjusted: List[List[float]] = []
        n_fixed = 0
        for pose in candidates:
            delta = np.array(pose) - np.array(home_pose)
            # Only use the DOF columns J actually has
            predicted = home_center + jacobian @ delta[:jacobian.shape[1]]

            in_safe = (
                safe_x_lo < predicted[0] < safe_x_hi
                and safe_y_lo < predicted[1] < safe_y_hi
            )
            if not in_safe:
                # Compute XY correction so predicted lands at image centre
                pixel_error = target_px - predicted
                correction = J_xy_pinv @ pixel_error          # mm in robot XY
                new_pose = list(pose)
                new_pose[0] += float(correction[0])
                new_pose[1] += float(correction[1])
                adjusted.append(new_pose)
                n_fixed += 1
            else:
                adjusted.append(pose)

        if n_fixed:
            self._publish(
                f"  Visibility adjustment: {n_fixed}/{len(candidates)} candidate XYs corrected."
            )
        return adjusted

    def _jacobian_blind_recovery(
        self,
        candidate_pose: List[float],
        home_pose: List[float],
        home_center: np.ndarray,
        jacobian: np.ndarray,
        image_w: int,
        image_h: int,
        cfg: "HandEyeConfig",
    ) -> bool:
        """
        When the board is not visible, compute a corrective XY move analytically.

        Uses the ACTUAL current robot position (not the pre-flight candidate) so
        that Z recovery moves made inside the servo loop are accounted for.

        Two scenarios:
        A) J predicts board is NOT at image centre → translation drift dominates.
           Apply the J-computed XY correction.
        B) J predicts board IS already at image centre (correction ≈ 0) but it's
           still not visible → rotation drift dominates (J too small or 2×3 without
           rotation columns).  In this case fall back to home XY with the current
           orientation, which strips translation and gives the servo the best chance
           of finding the board in the rotated frame.
        """
        # Use actual robot position — servo Z moves may have shifted it from candidate_pose
        actual_pose = self._robot.get_current_position()
        delta = np.array(actual_pose) - np.array(home_pose)
        predicted = home_center + jacobian @ delta[:jacobian.shape[1]]

        target = np.array([image_w / 2.0, image_h / 2.0])
        pixel_error = target - predicted
        dist_px = float(np.linalg.norm(pixel_error))

        J_xy_pinv = np.linalg.pinv(jacobian[:, :2])
        correction = J_xy_pinv @ pixel_error              # (2,) mm
        step = float(np.linalg.norm(correction))

        if step < 5.0:
            # Scenario B: J already predicts board at image centre — rotation
            # drift is the likely cause.  Reset to home XY while keeping the
            # current orientation so the board is at least in the camera's forward
            # direction.
            self._publish(
                f"  J-recovery: predicted at ({predicted[0]:.0f}, {predicted[1]:.0f}) px — "
                "correction negligible, rotation dominant → home XY fallback."
            )
            fallback = [home_pose[0], home_pose[1], actual_pose[2],
                        actual_pose[3], actual_pose[4], actual_pose[5]]
            ok = self._move_absolute(fallback)
        else:
            # Scenario A: meaningful translation correction available.
            if step > cfg.search_radius_mm:
                correction = correction * cfg.search_radius_mm / step
                step = cfg.search_radius_mm
            self._publish(
                f"  J-recovery: predicted at ({predicted[0]:.0f}, {predicted[1]:.0f}) px "
                f"(err={dist_px:.0f} px) → moving ({correction[0]:.1f}, {correction[1]:.1f}) mm"
            )
            ok = self._move_relative(dx=float(correction[0]), dy=float(correction[1]))

        if ok and cfg.servo_stabilization_delay_s > 0:
            time.sleep(cfg.servo_stabilization_delay_s)
        return ok

    def _estimate_jacobian(
        self,
        home_pose: List[float],
        cfg: "HandEyeConfig",
        K: np.ndarray,
        dist: np.ndarray,
    ) -> Optional[np.ndarray]:
        """
        Estimate the image-space Jacobian via central-difference probing.

        Each DOF is probed in both +δ and −δ directions and the column is
        computed as (center+ − center−) / (2δ).  Central differences cancel
        first-order errors and are typically 10–100× more accurate than the
        one-sided approach for the same probe distance.

        Translation probes (always): X, Y, Z  → 2×3 matrix at minimum.
        Rotation probes (optional, cfg.probe_rotations): RX, RY, RZ
            → extends to a 2×6 full Jacobian so the feedforward can also
               predict image drift caused by orientation changes, not just
               translation.

        Returns the Jacobian matrix or None if any probe fails.
        """
        pattern_size = (cfg.chessboard_width, cfg.chessboard_height)

        frame0 = self._get_frame()
        center0 = detect_board_center(frame0, pattern_size) if frame0 is not None else None
        if center0 is None:
            return None

        # probes: (pose_axis_index, delta, label)
        probes: List[Tuple[int, float, str]] = [
            (0, cfg.probe_dx_mm,  "X"),
            (1, cfg.probe_dy_mm,  "Y"),
            (2, cfg.probe_dz_mm,  "Z"),
        ]
        if cfg.probe_rotations:
            probes += [
                (3, cfg.probe_drx_deg, "RX"),
                (4, cfg.probe_dry_deg, "RY"),
                (5, cfg.probe_drz_deg, "RZ"),
            ]

        cols = []
        for axis, delta, label in probes:
            fwd_pose = list(home_pose)
            rev_pose = list(home_pose)
            fwd_pose[axis] += delta
            rev_pose[axis] -= delta

            # Forward probe
            self._move_absolute(fwd_pose)
            if cfg.servo_stabilization_delay_s > 0:
                time.sleep(cfg.servo_stabilization_delay_s)
            frame_fwd = self._get_frame()
            c_fwd = detect_board_center(frame_fwd, pattern_size) if frame_fwd is not None else None

            # Reverse probe
            self._move_absolute(rev_pose)
            if cfg.servo_stabilization_delay_s > 0:
                time.sleep(cfg.servo_stabilization_delay_s)
            frame_rev = self._get_frame()
            c_rev = detect_board_center(frame_rev, pattern_size) if frame_rev is not None else None

            # Return to home between probes
            self._move_absolute(home_pose)
            if cfg.servo_stabilization_delay_s > 0:
                time.sleep(cfg.servo_stabilization_delay_s)

            if c_fwd is not None and c_rev is not None:
                # Central difference — most accurate
                col = (np.array(c_fwd) - np.array(c_rev)) / (2.0 * delta)
            elif c_fwd is not None:
                # Fall back to one-sided forward
                col = (np.array(c_fwd) - np.array(center0)) / delta
                self._publish(f"  Jacobian probe {label}: reverse failed — using one-sided.")
            elif c_rev is not None:
                # Fall back to one-sided reverse
                col = (np.array(center0) - np.array(c_rev)) / delta
                self._publish(f"  Jacobian probe {label}: forward failed — using one-sided.")
            else:
                self._publish(f"  Jacobian probe {label}: board lost in both directions — aborting.")
                return None

            cols.append(col)

        return np.column_stack(cols)  # (2, 3) or (2, 6)

    def _approach_pose_incrementally(
        self,
        target_pose: List[float],
        home_pose: List[float],
        jacobian: np.ndarray,
        cfg: "HandEyeConfig",
        image_w: int,
        image_h: int,
        max_rot_step_deg: float = 10.0,
    ) -> List[float]:
        """
        Walk from home toward target_pose in rotation increments of at most
        max_rot_step_deg.  After each step, detect the board and apply one
        XY servo correction so the board stays near image centre.

        The accumulated XY offset means the final pose has different XY than
        the target — that's intentional and fine for calibration purposes.
        Returns the actual pose reached (XY may differ from target).
        """
        pattern_size = (cfg.chessboard_width, cfg.chessboard_height)
        J_xy_pinv = np.linalg.pinv(jacobian[:, :2])

        max_rot_delta = max(abs(target_pose[i] - home_pose[i]) for i in range(3, 6))
        n_steps = max(1, math.ceil(max_rot_delta / max_rot_step_deg))
        self._publish(
            f"  Large rotation ({max_rot_delta:.1f}°) — "
            f"approaching in {n_steps} steps of ≤{max_rot_step_deg:.0f}°"
        )

        current_xy = [home_pose[0], home_pose[1]]

        for step in range(1, n_steps + 1):
            if self._stop_event.is_set():
                break
            frac = step / n_steps
            intermediate = [
                current_xy[0],
                current_xy[1],
                home_pose[2] + frac * (target_pose[2] - home_pose[2]),
                home_pose[3] + frac * (target_pose[3] - home_pose[3]),
                home_pose[4] + frac * (target_pose[4] - home_pose[4]),
                home_pose[5] + frac * (target_pose[5] - home_pose[5]),
            ]

            ok = self._move_absolute(intermediate)
            if not ok:
                self._publish(f"  Incremental step {step}/{n_steps} unreachable — stopping here.")
                break

            if cfg.servo_stabilization_delay_s > 0:
                time.sleep(cfg.servo_stabilization_delay_s)

            frame = self._get_frame()
            info = detect_board_info(frame, pattern_size) if frame is not None else None

            if info is not None:
                px_err = np.array([image_w / 2.0 - info.cx, image_h / 2.0 - info.cy])
                correction = J_xy_pinv @ px_err
                step_size = float(np.linalg.norm(correction))
                if step_size > cfg.servo_max_step_mm:
                    correction = correction * cfg.servo_max_step_mm / step_size
                if step_size > 1.0:
                    self._move_relative(dx=float(correction[0]), dy=float(correction[1]))
                    if cfg.servo_stabilization_delay_s > 0:
                        time.sleep(cfg.servo_stabilization_delay_s)
                    current_xy[0] += float(correction[0])
                    current_xy[1] += float(correction[1])
                self._publish(
                    f"  Step {step}/{n_steps}: rot≈{intermediate[4]:.1f}° "
                    f"board err={float(np.linalg.norm(px_err)):.0f} px "
                    f"XY adj=({correction[0]:.1f},{correction[1]:.1f}) mm"
                )
            else:
                self._publish(f"  Step {step}/{n_steps}: board not visible — continuing.")

        return [
            current_xy[0], current_xy[1],
            target_pose[2], target_pose[3], target_pose[4], target_pose[5],
        ]

    def _servo_board_into_view(
        self,
        jacobian: np.ndarray,
        image_w: int,
        image_h: int,
        cfg: "HandEyeConfig",
        K: np.ndarray,
        dist: np.ndarray,
        home_ppm: Optional[float] = None,
        phys_board_w: Optional[float] = None,
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Iteratively correct XY (+ Z when error is large) position to bring the
        chessboard bounding-box centre toward the image centre.

        The Jacobian is re-scaled each iteration using the board's current apparent
        size (pixels/mm) relative to home — this corrects for Z-height changes
        where the same mm robot move produces different pixel shifts.
        """
        pattern_size = (cfg.chessboard_width, cfg.chessboard_height)

        for iteration in range(cfg.servo_max_iter):
            frame = self._get_frame()
            if frame is None:
                break

            info = detect_board_info(frame, pattern_size)

            # Z recovery when board disappears
            if info is None:
                self._publish(f"  [servo {iteration + 1}] board lost → recovery (+Z)")
                self._move_relative(dz=+20)
                if cfg.servo_stabilization_delay_s > 0:
                    time.sleep(cfg.servo_stabilization_delay_s)
                frame = self._get_frame()
                info = detect_board_info(frame, pattern_size) if frame is not None else None

                if info is None:
                    self._publish(f"  [servo {iteration + 1}] still lost → try -Z")
                    self._move_relative(dz=-40)
                    if cfg.servo_stabilization_delay_s > 0:
                        time.sleep(cfg.servo_stabilization_delay_s)
                    frame = self._get_frame()
                    info = detect_board_info(frame, pattern_size) if frame is not None else None

                if info is None:
                    return None, None

            # ── Dynamic Jacobian scaling ──────────────────────────────────────
            # Rescale XY columns by current pixels/mm vs home pixels/mm.
            # At a different Z the board appears larger/smaller, so the same
            # robot mm step causes a proportionally different pixel shift.
            if home_ppm is not None and phys_board_w and info.bbox_w > 10:
                current_ppm = info.bbox_w / phys_board_w
                scale = current_ppm / home_ppm
                J_scaled = jacobian.copy()
                J_scaled[:, :2] = jacobian[:, :2] * scale
            else:
                J_scaled = jacobian

            J_xy_pinv = np.linalg.pinv(J_scaled[:, :2])

            # Bbox-aware target: clamp image centre so the full board fits in frame
            half_w = info.bbox_w / 2.0
            half_h = info.bbox_h / 2.0
            target_cx = float(np.clip(image_w / 2.0, half_w, image_w - half_w))
            target_cy = float(np.clip(image_h / 2.0, half_h, image_h - half_h))

            px_err = np.array([target_cx - info.cx, target_cy - info.cy])
            dist_px = float(np.linalg.norm(px_err))
            self._publish(
                f"  [servo {iteration + 1}] "
                f"board {info.bbox_w:.0f}×{info.bbox_h:.0f} px  "
                f"err={dist_px:.0f} px"
            )
            if dist_px < cfg.servo_tol_px:
                self._publish(f"  [servo {iteration + 1}] centred.")
                break

            # Primary correction: XY from the 2×2 submatrix.
            # Using the full 2×6 pseudoinverse would let the high-gain rotation
            # columns (~12 px/°) absorb nearly all pixel error leaving XY
            # corrections tiny (~1 mm).  So we always solve XY first.
            correction = J_xy_pinv @ px_err
            dz = 0.0
            drx = dry = drz = 0.0

            # Rotation assist: when XY correction is larger than the step cap
            # (meaning we can't fully correct with translation alone), compute
            # the residual pixel error after the capped XY move and use the
            # rotation columns (if available) to absorb what's left.
            # This is capped at ±5° so it doesn't destroy orientation diversity.
            step = float(np.linalg.norm(correction))
            if step > cfg.servo_max_step_mm and J_scaled.shape[1] == 6:
                capped = correction * cfg.servo_max_step_mm / step
                px_residual = px_err - J_scaled[:, :2] @ capped
                if float(np.linalg.norm(px_residual)) > cfg.servo_tol_px:
                    J_rot = J_scaled[:, 3:]          # (2, 3) — RX, RY, RZ columns
                    J_rot_pinv = np.linalg.pinv(J_rot)
                    rot_corr = J_rot_pinv @ px_residual
                    drx = float(np.clip(rot_corr[0], -5.0, 5.0))
                    dry = float(np.clip(rot_corr[1], -5.0, 5.0))
                    drz = float(np.clip(rot_corr[2], -5.0, 5.0))

            if step > cfg.servo_max_step_mm:
                correction = correction * cfg.servo_max_step_mm / step
            rot_str = (
                f"  Δrx/ry/rz=({drx:.1f}, {dry:.1f}, {drz:.1f})°"
                if (drx or dry or drz) else ""
            )
            self._publish(
                f"  [servo {iteration + 1}] "
                f"Δxy=({correction[0]:.1f}, {correction[1]:.1f}) mm  Δz={dz:.1f} mm"
                + rot_str
            )
            moved = self._move_relative(
                dx=float(correction[0]), dy=float(correction[1]), dz=dz,
                drx=drx, dry=dry, drz=drz,
            )
            if not moved:
                # Move rejected (joint limit / unreachable) — robot didn't move.
                # Continuing would recompute the same correction indefinitely.
                # Try again with XY-only (drop Z) at half the step size.
                half_correction = correction * 0.5
                half_step = float(np.linalg.norm(half_correction))
                self._publish(
                    f"  [servo {iteration + 1}] move failed — retrying XY-only "
                    f"at ({half_correction[0]:.1f}, {half_correction[1]:.1f}) mm"
                )
                moved = self._move_relative(
                    dx=float(half_correction[0]), dy=float(half_correction[1])
                )
                if not moved:
                    self._publish(f"  [servo {iteration + 1}] XY-only also failed — breaking servo loop.")
                    break
            if cfg.servo_stabilization_delay_s > 0:
                time.sleep(cfg.servo_stabilization_delay_s)

        # Final PnP at the settled position
        frame = self._get_frame()
        if frame is None:
            return None, None
        R_c, t_c, _ = detect_chessboard_pose(frame, pattern_size, cfg.square_size_mm, K, dist)
        return R_c, t_c

    def _search_nearby_for_board(
        self,
        cfg: "HandEyeConfig",
        K: np.ndarray,
        dist: np.ndarray,
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Try small XY and Z offsets from the current robot position to find a
        nearby pose where the chessboard is visible.  Moves are attempted in
        order of increasing distance from the current pose so we use the
        closest viable pose.  Returns (R_cam, t_cam) on success, (None, None)
        if the board cannot be found within the search volume.
        """
        pattern_size = (cfg.chessboard_width, cfg.chessboard_height)
        base_pose = self._robot.get_current_position()
        half_delay = cfg.servo_stabilization_delay_s * 0.5

        # Compass spiral: 8 directions × 3 radii × 3 Z levels = 72 candidates
        # sorted nearest-first — far faster than the old 244-position dense grid.
        r = cfg.search_radius_mm
        radii = [r * 0.3, r * 0.6, r]
        angles_deg = [0, 45, 90, 135, 180, 225, 270, 315]
        z_steps = [0.0, 20.0, -20.0]

        offsets: List[Tuple[float, float, float]] = []
        for dz in z_steps:
            for radius in radii:
                for angle in angles_deg:
                    rad = math.radians(angle)
                    dx = round(radius * math.cos(rad), 1)
                    dy = round(radius * math.sin(rad), 1)
                    offsets.append((dx, dy, float(dz)))
        offsets.sort(key=lambda o: o[0] ** 2 + o[1] ** 2 + o[2] ** 2)

        for dx, dy, dz in offsets:
            if self._stop_event.is_set():
                break
            search_pose = [
                base_pose[0] + dx, base_pose[1] + dy, base_pose[2] + dz,
                base_pose[3], base_pose[4], base_pose[5],
            ]
            if not self._move_absolute(search_pose):
                continue
            if half_delay > 0:
                time.sleep(half_delay)
            frame = self._get_frame()
            if frame is None:
                continue
            R_c, t_c, _ = detect_chessboard_pose(
                frame, pattern_size, cfg.square_size_mm, K, dist
            )
            if R_c is not None:
                self._publish(
                    f"  Board found at nearby offset "
                    f"({dx:+.0f}, {dy:+.0f}, {dz:+.0f}) mm."
                )
                return R_c, t_c

        # ── Phase 2: orientation sweep ────────────────────────────────────────
        # XYZ search failed — try small rotation adjustments from the current
        # pose.  Eye-in-hand cameras shift their FOV when the wrist tilts, so
        # ±5° / ±10° tweaks on each axis can bring the board into frame when
        # translation alone cannot.  We return to base_pose before each probe
        # so we don't accumulate drift.
        self._publish("  XYZ search exhausted — trying orientation adjustments...")
        rot_steps = [5.0, -5.0, 10.0, -10.0]
        rot_axes  = [3, 4, 5]   # indices into pose: rx, ry, rz

        for axis in rot_axes:
            for delta_deg in rot_steps:
                if self._stop_event.is_set():
                    break
                rot_pose = list(base_pose)
                rot_pose[axis] = base_pose[axis] + delta_deg
                if not self._move_absolute(rot_pose):
                    continue
                if half_delay > 0:
                    time.sleep(half_delay)
                frame = self._get_frame()
                if frame is None:
                    continue
                R_c, t_c, _ = detect_chessboard_pose(
                    frame, pattern_size, cfg.square_size_mm, K, dist
                )
                if R_c is not None:
                    axis_name = {3: "RX", 4: "RY", 5: "RZ"}[axis]
                    self._publish(
                        f"  Board found with {axis_name} {delta_deg:+.0f}° orientation tweak."
                    )
                    return R_c, t_c

        # Return to the starting pose so the caller's home-return logic is
        # relative to a known position.
        self._move_absolute(list(base_pose))
        return None, None

    def _lock_brightness(self) -> None:
        if hasattr(self._vision, "lock_auto_brightness_adjustment"):
            self._vision.lock_auto_brightness_adjustment()
            self._publish("Auto-brightness locked — exposure frozen for capture.")
        else:
            _logger.debug("Vision service does not support brightness locking.")

    def _unlock_brightness(self) -> None:
        if hasattr(self._vision, "unlock_auto_brightness_adjustment"):
            self._vision.unlock_auto_brightness_adjustment()
            self._publish("Auto-brightness restored.")
        else:
            _logger.debug("Vision service does not support brightness unlocking.")

    def _get_frame(self) -> Optional[np.ndarray]:
        if self._vision is None:
            return None
        return self._vision.get_latest_raw_frame()

    def _camera_params(self):
        # VisionService wraps VisionSystem — cameraMatrix/cameraDist live on the
        # underlying VisionSystem, not on VisionService itself. Try the direct
        # attributes first (mock / old API), then go through the wrapped system.
        K = getattr(self._vision, "cameraMatrix", None)
        if K is None and hasattr(self._vision, "_vision_system"):
            K = getattr(self._vision._vision_system, "cameraMatrix", None)

        dist = getattr(self._vision, "cameraDist", None)
        if dist is None and hasattr(self._vision, "_vision_system"):
            dist = getattr(self._vision._vision_system, "cameraDist", None)

        if dist is None:
            dist = np.zeros((1, 5), dtype=np.float64)
        return K, dist

    def _hand_eye_save_path(self):
        """
        Return path for the 4×4 hand-eye result, derived from the vision system's
        storage directory.  Saves as hand_eye_T_cam_to_flange.npy — separate from
        cameraToRobotMatrix_camera_center.npy (homography, different format/purpose).
        """
        import os
        # Path: VisionService._vision_system → VisionSystem.service → Service.data_manager → storage_path
        vs = getattr(self._vision, "_vision_system", None)
        if vs is not None:
            svc = getattr(vs, "service", None)
            dm = getattr(svc, "data_manager", None) if svc is not None else None
            storage = getattr(dm, "storage_path", None) if dm is not None else None
            if storage:
                return os.path.join(storage, "hand_eye_T_cam_to_flange.npy")
        return None

    def _publish(self, msg: str) -> None:
        _logger.info(msg)
        self._publish_topic(HAND_EYE_PROGRESS_TOPIC, msg)

    def _publish_topic(self, topic: str, payload) -> None:
        if self._messaging is not None:
            try:
                self._messaging.publish(topic, payload)
            except Exception:
                pass

