from __future__ import annotations

import json
import logging
import os
import threading
from typing import List, Optional, Tuple

import cv2
import numpy as np

from src.applications.intrinsic_calibration_capture.core.acquisition import capture_intrinsic_dataset
from src.applications.intrinsic_calibration_capture.core.data import BoardType, CaptureSample, ImageInfo
from src.applications.intrinsic_calibration_capture.service.i_intrinsic_capture_service import (
    ARUCO_DICT_OPTIONS,
    INTRINSIC_CAPTURE_PROGRESS_TOPIC,
    IntrinsicCaptureConfig,
    IIntrinsicCaptureService,
)

_logger = logging.getLogger(__name__)


class IntrinsicCaptureService(IIntrinsicCaptureService):
    """
    Drives the automated intrinsic calibration dataset capture using the
    platform's IRobotService and IVisionService.
    """

    def __init__(self, robot_service, vision_service, robot_config, messaging=None):
        self._robot = robot_service
        self._vision = vision_service
        self._robot_config = robot_config
        self._messaging = messaging
        self._config = IntrinsicCaptureConfig()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._charuco_detector = None
        self._charuco_detector_key: tuple = ()
        # Coverage tracking (cleared at each start_capture)
        self._coverage_bboxes: list = []        # (x1, y1, x2, y2) px per captured detection
        self._coverage_image_size: Optional[Tuple[int, int]] = None  # (w, h)

    # ── IIntrinsicCaptureService ──────────────────────────────────────────────

    def start_capture(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            _logger.warning("Acquisition already running.")
            return
        self._coverage_bboxes.clear()
        self._coverage_image_size = None
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop_capture(self) -> None:
        self._stop_event.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def get_latest_frame(self) -> Optional[np.ndarray]:
        frame = self._get_raw_frame()
        if frame is None or self.is_running():
            # Don't run detection concurrently with the capture thread.
            return frame
        return self._annotate_frame(frame)

    def _get_raw_frame(self) -> Optional[np.ndarray]:
        """Return the raw (uncorrected, undistorted) frame for calibration capture.
        Falls back to get_latest_frame() for stubs that don't implement get_latest_raw_frame."""
        if self._vision is None:
            return None
        if hasattr(self._vision, "get_latest_raw_frame"):
            raw = self._vision.get_latest_raw_frame()
            if raw is not None:
                return raw
        return self._vision.get_latest_frame()

    def get_config(self) -> IntrinsicCaptureConfig:
        return self._config

    def save_config(self, config: IntrinsicCaptureConfig) -> None:
        self._config = config

    # ── Coverage tracking ─────────────────────────────────────────────────────

    def _record_coverage(self, bbox_px, image_size: Tuple[int, int]) -> None:
        """Called by the acquisition thread for every successful detection."""
        if bbox_px is not None:
            self._coverage_bboxes.append(bbox_px)
        if self._coverage_image_size is None:
            self._coverage_image_size = image_size

    def _draw_coverage_overlay(
        self, frame: np.ndarray, cols: int = 8, rows: int = 6
    ) -> np.ndarray:
        """
        Draws a semi-transparent grid on *frame* coloured by detection density.
        Green = well covered, orange = lightly covered, red = no coverage.
        A yellow crosshair marks the cell that needs the most coverage.
        """
        if not self._coverage_bboxes:
            return frame
        h, w = frame.shape[:2]
        cw = w / cols
        ch = h / rows

        # Build density grid: each captured bbox covers all cells it overlaps.
        grid = np.zeros((rows, cols), dtype=np.float32)
        for (x1, y1, x2, y2) in self._coverage_bboxes:
            c1 = max(0, int(x1 / cw))
            c2 = min(cols - 1, int(x2 / cw))
            r1 = max(0, int(y1 / ch))
            r2 = min(rows - 1, int(y2 / ch))
            for r in range(r1, r2 + 1):
                for c in range(c1, c2 + 1):
                    grid[r, c] += 1

        overlay = frame.copy()
        for r in range(rows):
            for c in range(cols):
                x1 = int(c * cw); y1 = int(r * ch)
                x2 = int((c + 1) * cw); y2 = int((r + 1) * ch)
                count = grid[r, c]
                if count == 0:
                    colour = (0, 0, 180)       # red — uncovered
                elif count < 2:
                    colour = (0, 140, 255)     # orange — light
                else:
                    colour = (0, 180, 0)       # green — good
                cv2.rectangle(overlay, (x1, y1), (x2, y2), colour, -1)

        frame = cv2.addWeighted(overlay, 0.30, frame, 0.70, 0)

        # Grid lines
        for c in range(1, cols):
            cv2.line(frame, (int(c * cw), 0), (int(c * cw), h), (80, 80, 80), 1)
        for r in range(1, rows):
            cv2.line(frame, (0, int(r * ch)), (w, int(r * ch)), (80, 80, 80), 1)

        # Crosshair on the least-covered cell
        min_idx = int(np.argmin(grid))
        min_r, min_c = divmod(min_idx, cols)
        cx = int((min_c + 0.5) * cw)
        cy = int((min_r + 0.5) * ch)
        cv2.drawMarker(frame, (cx, cy), (0, 255, 255),
                       cv2.MARKER_CROSS, 40, 2, cv2.LINE_AA)

        # Caption
        n = len(self._coverage_bboxes)
        covered = int(np.sum(grid > 0))
        cv2.putText(frame, f"cov {covered}/{cols*rows} cells  |  {n} frames",
                    (6, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
        return frame

    def _save_coverage_image(self, output_dir: str) -> None:
        """Render and save a standalone coverage map PNG to output_dir."""
        if not self._coverage_bboxes or self._coverage_image_size is None:
            return
        w, h = self._coverage_image_size
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
        canvas[:] = (30, 30, 30)
        img = self._draw_coverage_overlay(canvas)
        path = os.path.join(output_dir, "coverage_map.png")
        cv2.imwrite(path, img)
        self._publish(f"Coverage map saved → {path}")

    def _save_charuco_coverage_from_corners(
        self,
        corners_list: list,
        image_size: Optional[Tuple[int, int]],
        output_dir: str,
        label: str = "",
    ) -> None:
        """Render and save a coverage PNG from the 2-D positions of accepted ChArUco corners.
        Only corners from images that survived error-filtering are drawn."""
        if not corners_list or image_size is None:
            return
        w, h = image_size
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
        canvas[:] = (30, 30, 30)
        for corners2d in corners_list:
            for pt in corners2d.reshape(-1, 2):
                cv2.circle(canvas, (int(pt[0]), int(pt[1])), 4, (0, 200, 80), -1)
        if label:
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(canvas, (4, h - th - 16), (tw + 12, h - 4), (0, 0, 0), -1)
            cv2.putText(canvas, label, (8, h - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1, cv2.LINE_AA)
        path = os.path.join(output_dir, "coverage_map.png")
        cv2.imwrite(path, canvas)
        self._publish(f"Coverage map saved → {path}")

    # ── Preview annotation ────────────────────────────────────────────────────

    def _annotate_frame(self, frame: np.ndarray) -> np.ndarray:
        try:
            board_type = BoardType(self._config.board_type)
            if board_type == BoardType.CHARUCO:
                return self._annotate_charuco(frame)
            return self._annotate_chessboard(frame)
        except Exception:
            return frame

    def _annotate_charuco(self, frame: np.ndarray) -> np.ndarray:
        from src.engine.vision.implementation.VisionSystem.features.calibration.charuco import (
            AutoCharucoBoardDetector,
        )
        cfg = self._config
        sq = cfg.square_size_mm or 25.0
        mk = cfg.marker_size_mm or sq * 0.75
        dict_id = ARUCO_DICT_OPTIONS.get(cfg.aruco_dict, cv2.aruco.DICT_4X4_250)
        cw = cfg.chessboard_width or 10
        ch = cfg.chessboard_height or 7

        key = (cw, ch, sq, mk, dict_id)
        if self._charuco_detector is None or self._charuco_detector_key != key:
            self._charuco_detector = AutoCharucoBoardDetector(
                squares_x=cw,
                squares_y=ch,
                square_length=sq,
                marker_length=mk,
                dictionary_id=dict_id,
            )
            self._charuco_detector_key = key

        result = self._charuco_detector.detect(frame)
        n_markers = 0 if result.marker_ids is None else len(result.marker_ids)
        n_corners = 0 if result.charuco_ids is None else len(result.charuco_ids)
        label = f"markers={n_markers}  corners={n_corners}  [{result.mode}]"
        colour = (0, 220, 80) if n_corners >= 4 else (80, 80, 80)
        vis = result.vis
        vis = self._draw_coverage_overlay(vis)
        cv2.rectangle(vis, (0, 0), (vis.shape[1], 32), (0, 0, 0), -1)
        cv2.putText(vis, label, (6, 23), cv2.FONT_HERSHEY_SIMPLEX,
                    0.65, colour, 2, cv2.LINE_AA)
        return vis

    def _annotate_chessboard(self, frame: np.ndarray) -> np.ndarray:
        cfg = self._config
        cw, ch = cfg.chessboard_width, cfg.chessboard_height
        if cw == 0 or ch == 0:
            return frame
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        found, corners = cv2.findChessboardCorners(gray, (cw, ch), None)
        vis = frame.copy()
        cv2.drawChessboardCorners(vis, (cw, ch), corners, found)
        vis = self._draw_coverage_overlay(vis)
        label = f"corners={'found' if found else 'not found'}  ({cw}×{ch})"
        colour = (0, 220, 80) if found else (80, 80, 80)
        cv2.rectangle(vis, (0, 0), (vis.shape[1], 32), (0, 0, 0), -1)
        cv2.putText(vis, label, (6, 23), cv2.FONT_HERSHEY_SIMPLEX,
                    0.65, colour, 2, cv2.LINE_AA)
        return vis

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run(self) -> None:
        self._lock_brightness()
        try:
            cfg = self._config
            output_dir = cfg.output_dir or os.path.join(os.getcwd(), "intrinsic_capture_output")
            os.makedirs(output_dir, exist_ok=True)

            cw = cfg.chessboard_width or self._vision.get_chessboard_width()
            ch = cfg.chessboard_height or self._vision.get_chessboard_height()

            # CharuCo pattern_size = (squares_cols, squares_rows) — NOT inner corners.
            # The vision service stores chessboard inner-corner counts (squares - 1).
            # When auto-detecting dimensions for a CharuCo board, add 1 to each axis.
            board_type = BoardType(cfg.board_type)
            if board_type == BoardType.CHARUCO and cfg.chessboard_width == 0:
                _logger.warning(
                    "CharuCo auto-size: vision service reports chessboard inner corners (%d×%d). "
                    "Using (%d×%d) squares for CharuCo (inner_corners + 1). "
                    "Set Board cols/rows manually in the UI if your board has a different square count.",
                    cw, ch, cw + 1, ch + 1,
                )
                cw = cw + 1
                ch = ch + 1

            pattern_size = (cw, ch)
            image_info = ImageInfo(
                width=self._vision.get_camera_width(),
                height=self._vision.get_camera_height(),
            )

            aruco_dict_id = ARUCO_DICT_OPTIONS.get(cfg.aruco_dict, cv2.aruco.DICT_4X4_250)
            sq_mm = cfg.square_size_mm or (
                self._vision.get_square_size_mm() if hasattr(self._vision, "get_square_size_mm") else 25.0
            )
            mk_mm = cfg.marker_size_mm or sq_mm * 0.75

            self._publish(
                f"Starting acquisition: {cfg.grid_rows}x{cfg.grid_cols} grid, "
                f"board={board_type.value}, output → {output_dir}"
            )

            samples = capture_intrinsic_dataset(
                get_pose_fn=self._robot.get_current_position,
                move_relative_fn=self._move_relative,
                move_absolute_fn=self._move_absolute,
                grab_frame_fn=self._get_raw_frame,
                save_frame_fn=lambda frame, tag: self._save_frame(frame, tag, output_dir),
                image_info=image_info,
                pattern_size=pattern_size,
                board_type=board_type,
                square_size_mm=sq_mm,
                marker_size_mm=mk_mm,
                aruco_dict_id=aruco_dict_id,
                grid_rows=cfg.grid_rows,
                grid_cols=cfg.grid_cols,
                margin_px=cfg.margin_px,
                tilt_deg=cfg.tilt_deg,
                z_delta_mm=cfg.z_delta_mm,
                probe_dx_mm=cfg.probe_dx_mm,
                probe_dy_mm=cfg.probe_dy_mm,
                probe_drx_deg=cfg.probe_drx_deg,
                probe_dry_deg=cfg.probe_dry_deg,
                probe_drz_deg=cfg.probe_drz_deg,
                stabilization_delay_s=cfg.stabilization_delay_s,
                stop_event=self._stop_event,
                progress_cb=self._publish,
                max_detection_retries=cfg.max_detection_retries,
                initial_detection_attempts=cfg.initial_detection_attempts,
                initial_detection_delay_s=cfg.initial_detection_delay_s,
                charuco_sweep_x_mm=cfg.charuco_sweep_x_mm,
                charuco_sweep_y_mm=cfg.charuco_sweep_y_mm,
                charuco_min_corners=cfg.charuco_min_corners,
                charuco_rz_deg=cfg.charuco_rz_deg,
                detection_callback=self._record_coverage,
            )

            if samples:
                self._publish(f"Acquisition complete: {len(samples)} images. Starting calibration...")
                self._save_coverage_image(output_dir)
                self._save_poses_json(samples, output_dir)
                storage_path = getattr(self._vision, "storage_path", None) or output_dir
                self._run_calibration(
                    samples, board_type, pattern_size, sq_mm,
                    aruco_dict_id, mk_mm, storage_path,
                )
                if board_type == BoardType.CHARUCO and cfg.charuco_compute_hand_eye:
                    self._compute_and_save_hand_eye(
                        output_dir, storage_path, pattern_size,
                        sq_mm, mk_mm, aruco_dict_id,
                    )
            else:
                self._publish("No images captured — calibration skipped.")

        except Exception as e:
            _logger.exception("Error during intrinsic capture acquisition")
            self._publish(f"ERROR: {e}")
        finally:
            self._unlock_brightness()

    # ── Calibration ───────────────────────────────────────────────────────────

    def _run_calibration(
        self,
        samples: List[CaptureSample],
        board_type: BoardType,
        pattern_size: Tuple[int, int],
        square_size_mm: float,
        aruco_dict_id: int,
        marker_size_mm: float,
        storage_path: str,
    ) -> None:
        # Load unique images (multiple samples may reference the same file)
        seen: set = set()
        images: List[np.ndarray] = []
        for s in samples:
            if s.image_path and s.image_path not in seen:
                seen.add(s.image_path)
                img = cv2.imread(s.image_path)
                if img is not None:
                    images.append(img)

        if not images:
            self._publish("Could not load captured images — calibration skipped.")
            return

        self._publish(f"Calibrating with {len(images)} unique images (board={board_type.value})...")

        if board_type == BoardType.CHESSBOARD:
            self._calibrate_chessboard(images, pattern_size, square_size_mm, storage_path)
        else:
            self._calibrate_charuco(images, pattern_size, square_size_mm, aruco_dict_id, marker_size_mm, storage_path)

    def _calibrate_chessboard(
        self,
        images: List[np.ndarray],
        pattern_size: Tuple[int, int],
        square_size_mm: float,
        storage_path: str,
    ) -> None:
        from src.engine.vision.implementation.VisionSystem.features.calibration.cameraCalibration.CameraCalibrationService import (
            CameraCalibrationService,
        )

        class _Pub:
            def __init__(self, fn):
                self._fn = fn
            def publish_calibration_feedback(self, msg: str) -> None:
                self._fn(msg)

        svc = CameraCalibrationService(
            chessboardWidth=pattern_size[0],
            chessboardHeight=pattern_size[1],
            squareSizeMM=square_size_mm,
            skipFrames=0,
            message_publisher=_Pub(self._publish),
            storagePath=storage_path,
        )
        svc.calibrationImages = images
        result = svc.run(None)
        if not result.success:
            self._publish(f"Calibration failed: {result.message}")

    _MAX_PX_ERROR_THRESHOLD = 1.0  # images with max reprojection error above this are rejected

    def _calibrate_charuco(
        self,
        images: List[np.ndarray],
        pattern_size: Tuple[int, int],
        square_size_mm: float,
        aruco_dict_id: int,
        marker_size_mm: float,
        storage_path: str,
    ) -> None:
        from src.engine.vision.implementation.VisionSystem.features.calibration.charuco import (
            AutoCharucoBoardDetector,
            CharucoCalibrator,
        )

        detector = AutoCharucoBoardDetector(
            squares_x=pattern_size[0],
            squares_y=pattern_size[1],
            square_length=square_size_mm,
            marker_length=marker_size_mm,
            dictionary_id=aruco_dict_id,
        )

        # ── First pass: determine dominant convention (normal vs legacy) ──────
        normal_count = legacy_count = 0
        for img in images:
            result = detector.detect(img)
            n = 0 if result.charuco_ids is None else len(result.charuco_ids)
            if n >= 4:
                if result.mode == "legacy":
                    legacy_count += 1
                else:
                    normal_count += 1

        use_legacy = legacy_count > normal_count
        board_det = detector.legacy if use_legacy else detector.normal
        mode_name = "legacy" if use_legacy else "normal"
        self._publish(
            f"ChArUco convention: '{mode_name}' "
            f"({normal_count} normal frames, {legacy_count} legacy frames)."
        )

        # ── Second pass: accumulate calibration data ──────────────────────────
        calibrator = CharucoCalibrator(board_det.board)
        accepted_corners: list = []
        accepted_ids: list = []
        accepted_images: list = []
        image_size: Optional[Tuple[int, int]] = None

        for idx, img in enumerate(images):
            if image_size is None:
                h, w = img.shape[:2]
                image_size = (w, h)
            charuco_corners, charuco_ids, _, _ = board_det.detect_raw(img)
            ok = calibrator.add_frame(img, charuco_corners, charuco_ids)
            n = 0 if charuco_ids is None else len(charuco_ids)
            if ok:
                accepted_corners.append(charuco_corners)
                accepted_ids.append(charuco_ids)
                accepted_images.append(img)
                self._publish(f"  ✅ ChArUco detected in image {idx} ({n} corners)")
            else:
                self._publish(f"  ❌ ChArUco not found in image {idx} (n={n})")

        if calibrator.frame_count < CharucoCalibrator.MIN_FRAMES:
            self._publish(
                f"Insufficient valid images ({calibrator.frame_count}, "
                f"need ≥{CharucoCalibrator.MIN_FRAMES})."
            )
            return

        total_before_filter = calibrator.frame_count
        self._publish(f"Running ChArUco calibration with {total_before_filter} images...")
        try:
            rms, camera_matrix, dist_coeffs, rvecs, tvecs = calibrator.calibrate()
        except RuntimeError as e:
            self._publish(f"ChArUco calibration failed: {e}")
            _logger.exception("ChArUco calibration error")
            return

        # ── Iterative max-px-error filtering ─────────────────────────────────
        board_corners_3d = board_det.board.getChessboardCorners()
        filtered_out: list = []
        keep_corners: list = []
        keep_ids: list = []
        keep_images: list = []

        for i, (corners2d, ids, rvec, tvec) in enumerate(
            zip(accepted_corners, accepted_ids, rvecs, tvecs)
        ):
            obj_pts = board_corners_3d[ids.flatten()]
            projected, _ = cv2.projectPoints(obj_pts, rvec, tvec, camera_matrix, dist_coeffs)
            diff = corners2d.reshape(-1, 2) - projected.reshape(-1, 2)
            max_err = float(np.linalg.norm(diff, axis=1).max())
            if max_err > self._MAX_PX_ERROR_THRESHOLD:
                filtered_out.append((i, max_err))
            else:
                keep_corners.append(corners2d)
                keep_ids.append(ids)
                keep_images.append(accepted_images[i])

        if filtered_out:
            names = ", ".join(
                f"img{i}(max={e:.3f}px)" for i, e in filtered_out[:5]
            )
            suffix = "..." if len(filtered_out) > 5 else ""
            self._publish(
                f"Filtered {len(filtered_out)} images "
                f"(max_px_error>{self._MAX_PX_ERROR_THRESHOLD}): {names}{suffix}"
            )
            n_kept = len(keep_corners)
            self._publish(
                f"Calibrated with {n_kept}/{total_before_filter} images. Recalibrating..."
            )
            if n_kept < CharucoCalibrator.MIN_FRAMES:
                self._publish(
                    f"Too few images remain after filtering ({n_kept}). Keeping original result."
                )
            else:
                calibrator2 = CharucoCalibrator(board_det.board)
                for img_arr, c2d, ids in zip(keep_images, keep_corners, keep_ids):
                    calibrator2.add_frame(img_arr, c2d, ids)
                try:
                    rms, camera_matrix, dist_coeffs, rvecs, tvecs = calibrator2.calibrate()
                    accepted_corners = keep_corners
                    accepted_ids = keep_ids
                except RuntimeError as e:
                    self._publish(
                        f"Re-calibration after filtering failed: {e}. Keeping original result."
                    )
                    _logger.exception("ChArUco re-calibration error")

        # ── Save results to VisionSystem storage ──────────────────────────────
        os.makedirs(storage_path, exist_ok=True)
        np.savez(os.path.join(storage_path, "calibration_data.npz"),
                 camera_matrix=camera_matrix, dist_coeffs=dist_coeffs,
                 rvecs=rvecs, tvecs=tvecs)
        np.savez(os.path.join(storage_path, "camera_calibration.npz"),
                 mtx=camera_matrix, dist=dist_coeffs)
        self._publish(f"ChArUco calibration saved to {storage_path}  (RMS={rms:.4f} px)")

        self._log_calibration_report(
            camera_matrix, dist_coeffs,
            accepted_corners, accepted_ids,
            rvecs, tvecs, board_det.board, image_size,
        )

        # ── Coverage image — only accepted (post-filter) corners ──────────────
        n_used = len(accepted_corners)
        self._save_charuco_coverage_from_corners(
            accepted_corners,
            image_size,
            storage_path,
            label=f"{n_used}/{total_before_filter} images used  |  RMS={rms:.4f}px",
        )

    # ── Pose saving & hand-eye calibration ───────────────────────────────────

    def _save_poses_json(self, samples: List[CaptureSample], output_dir: str) -> None:
        """Save {filename: robot_pose} mapping for every captured sample."""
        pose_map = {}
        for s in samples:
            if s.image_path:
                pose_map[os.path.basename(s.image_path)] = s.pose
        path = os.path.join(output_dir, "capture_poses.json")
        with open(path, "w") as f:
            json.dump(pose_map, f, indent=2)
        self._publish(f"Robot poses saved → {path}")

    def _compute_and_save_hand_eye(
        self,
        output_dir: str,
        storage_path: str,
        pattern_size: Tuple[int, int],
        square_size_mm: float,
        marker_size_mm: float,
        aruco_dict_id: int,
    ) -> None:
        """
        Load captured images + pose JSON, detect ChArUco in each, run solvePnP,
        then call cv2.calibrateHandEye and save the resulting T_cam_to_flange matrix.
        """
        import cv2

        poses_file = os.path.join(output_dir, "capture_poses.json")
        if not os.path.isfile(poses_file):
            self._publish("Hand-eye: capture_poses.json not found — skipping.")
            return

        # Load intrinsics (just written by _calibrate_charuco)
        calib_file = os.path.join(storage_path, "camera_calibration.npz")
        if not os.path.isfile(calib_file):
            self._publish("Hand-eye: camera_calibration.npz not found — skipping.")
            return

        data = np.load(calib_file)
        K = data["mtx"]
        dist = data["dist"]

        with open(poses_file) as f:
            pose_map: dict = json.load(f)

        from src.engine.vision.implementation.VisionSystem.features.calibration.charuco import (
            AutoCharucoBoardDetector,
        )

        detector = AutoCharucoBoardDetector(
            squares_x=pattern_size[0],
            squares_y=pattern_size[1],
            square_length=square_size_mm,
            marker_length=marker_size_mm,
            dictionary_id=aruco_dict_id,
        )

        # Determine dominant convention from first-pass detections
        normal_count = legacy_count = 0
        img_cache: dict = {}
        for fname in pose_map:
            img_path = os.path.join(output_dir, fname)
            img = cv2.imread(img_path)
            if img is None:
                continue
            img_cache[fname] = img
            result = detector.detect(img)
            n = 0 if result.charuco_ids is None else len(result.charuco_ids)
            if n >= 4:
                if result.mode == "legacy":
                    legacy_count += 1
                else:
                    normal_count += 1

        use_legacy = legacy_count > normal_count
        board_det = detector.legacy if use_legacy else detector.normal

        R_robot_list: list = []
        t_robot_list: list = []
        R_cam_list: list = []
        t_cam_list: list = []

        def _euler_to_rotmat(rx_deg: float, ry_deg: float, rz_deg: float) -> np.ndarray:
            """ZYX convention: Rz @ Ry @ Rx (Fairino TCP format)."""
            rx = np.radians(rx_deg)
            ry = np.radians(ry_deg)
            rz = np.radians(rz_deg)
            Rx = np.array([[1, 0, 0],
                           [0, np.cos(rx), -np.sin(rx)],
                           [0, np.sin(rx),  np.cos(rx)]])
            Ry = np.array([[ np.cos(ry), 0, np.sin(ry)],
                           [0, 1, 0],
                           [-np.sin(ry), 0, np.cos(ry)]])
            Rz = np.array([[np.cos(rz), -np.sin(rz), 0],
                           [np.sin(rz),  np.cos(rz), 0],
                           [0, 0, 1]])
            return Rz @ Ry @ Rx

        for fname, robot_pose in pose_map.items():
            img = img_cache.get(fname)
            if img is None:
                continue
            charuco_corners, charuco_ids, _, _ = board_det.detect_raw(img)
            if charuco_corners is None or charuco_ids is None or len(charuco_ids) < 6:
                continue
            obj_pts = board_det.board.getChessboardCorners()[charuco_ids.flatten()].astype(np.float32)
            ret, rvec, tvec = cv2.solvePnP(obj_pts, charuco_corners, K, dist)
            if not ret:
                continue
            R_cam, _ = cv2.Rodrigues(rvec)
            R_cam_list.append(R_cam)
            t_cam_list.append(tvec.reshape(3, 1))

            # Robot end-effector pose → rotation matrix + translation
            x, y, z, rx, ry, rz = robot_pose[:6]
            R_robot = _euler_to_rotmat(rx, ry, rz)
            t_robot = np.array([[x], [y], [z]], dtype=np.float64)
            R_robot_list.append(R_robot)
            t_robot_list.append(t_robot)

        if len(R_cam_list) < 4:
            self._publish(
                f"Hand-eye: only {len(R_cam_list)} usable image-pose pairs (need ≥4) — skipping."
            )
            return

        self._publish(f"Computing hand-eye calibration from {len(R_cam_list)} samples…")
        try:
            R_he, t_he = cv2.calibrateHandEye(
                R_robot_list, t_robot_list, R_cam_list, t_cam_list,
                method=cv2.CALIB_HAND_EYE_TSAI,
            )
        except cv2.error as e:
            self._publish(f"Hand-eye cv2.calibrateHandEye failed: {e}")
            return

        T_he = np.eye(4)
        T_he[:3, :3] = R_he
        T_he[:3, 3] = t_he.ravel()

        he_path = os.path.join(storage_path, "camera_to_robot.npy")
        np.save(he_path, T_he)
        self._publish(f"Hand-eye result saved → {he_path}")
        self._publish(f"T_cam_to_flange:\n{np.array2string(T_he, precision=4, suppress_small=True)}")

    def _log_calibration_report(
        self,
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray,
        all_charuco_corners: list,
        all_charuco_ids: list,
        rvecs: list,
        tvecs: list,
        board: cv2.aruco.CharucoBoard,
        image_size: Tuple[int, int],
    ) -> None:
        width, height = image_size
        fx = camera_matrix[0, 0]
        fy = camera_matrix[1, 1]
        cx = camera_matrix[0, 2]
        cy = camera_matrix[1, 2]
        skew = camera_matrix[0, 1]
        aspect = fx / fy if fy != 0 else float("nan")
        hfov = np.degrees(2.0 * np.arctan2(width / 2.0, fx))
        vfov = np.degrees(2.0 * np.arctan2(height / 2.0, fy))

        d = dist_coeffs.ravel()
        dist_labels = ["k1", "k2", "p1", "p2", "k3", "k4", "k5", "k6"]
        dist_parts = "  ".join(f"{dist_labels[i]}={d[i]:+.6f}" for i in range(len(d)))

        # ── Extrinsic summary ─────────────────────────────────────────────────
        txs = [float(t.ravel()[0]) for t in tvecs]
        tys = [float(t.ravel()[1]) for t in tvecs]
        tzs = [float(t.ravel()[2]) for t in tvecs]
        rot_mags = [float(np.linalg.norm(r)) * 180.0 / np.pi for r in rvecs]

        tx_min, tx_max = min(txs), max(txs)
        ty_min, ty_max = min(tys), max(tys)
        tz_min, tz_max = min(tzs), max(tzs)
        rot_min, rot_max = min(rot_mags), max(rot_mags)

        _logger.info(
            "\n"
            "╔══════════════════════════════════════════════════════════════╗\n"
            "║          CHARUCO CAMERA CALIBRATION REPORT                   ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  fx=%10.4f px   fy=%10.4f px                        ║\n"
            "║  cx=%10.4f px   cy=%10.4f px                        ║\n"
            "║  skew=%10.6f      fx/fy=%.6f                         ║\n"
            "║  image: %d × %d px                                       ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  DISTORTION: %s\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  H-FOV=%.2f°   V-FOV=%.2f°                              ║\n"
            "╠══════════════════════════════════════════════════════════════╣\n"
            "║  POSE COVERAGE  (board → camera, %d images)                ║\n"
            "║    tx  [%+8.2f … %+8.2f] mm                             ║\n"
            "║    ty  [%+8.2f … %+8.2f] mm                             ║\n"
            "║    tz  [%+8.2f … %+8.2f] mm  (depth range)              ║\n"
            "║    tilt [%6.2f … %6.2f] °   (rotation magnitude)        ║\n"
            "╚══════════════════════════════════════════════════════════════╝",
            fx, fy, cx, cy, skew, aspect, width, height, dist_parts, hfov, vfov,
            len(rvecs),
            tx_min, tx_max, ty_min, ty_max, tz_min, tz_max, rot_min, rot_max,
        )

        # Per-image reprojection errors using charuco 3D corner positions
        per_image_mean: list = []
        per_image_max_err: list = []
        for corners2d, ids, rvec, tvec in zip(all_charuco_corners, all_charuco_ids, rvecs, tvecs):
            obj_pts = board.getChessboardCorners()[ids.flatten()]
            projected, _ = cv2.projectPoints(obj_pts, rvec, tvec, camera_matrix, dist_coeffs)
            diff = corners2d.reshape(-1, 2) - projected.reshape(-1, 2)
            errs = np.linalg.norm(diff, axis=1)
            per_image_mean.append(float(errs.mean()))
            per_image_max_err.append(float(errs.max()))

        overall_mean = float(np.mean(per_image_mean))
        overall_max = float(np.max(per_image_max_err))
        overall_min = float(np.min(per_image_mean))
        overall_std = float(np.std(per_image_mean))
        best_idx = int(np.argmin(per_image_mean))
        worst_idx = int(np.argmax(per_image_mean))

        lines = ["\n  PER-IMAGE REPROJECTION ERRORS (CharuCo)"]
        lines.append(f"  {'Img':>4}  {'Mean (px)':>10}  {'Max (px)':>10}")
        lines.append(f"  {'---':>4}  {'---------':>10}  {'--------':>10}")
        for i, (m, mx) in enumerate(zip(per_image_mean, per_image_max_err)):
            tag = " ◄ worst" if i == worst_idx else (" ◄ best" if i == best_idx else "")
            lines.append(f"  {i:>4}  {m:>10.4f}  {mx:>10.4f}{tag}")
        lines.append("")
        lines.append(
            f"  SUMMARY  mean={overall_mean:.4f}px  max={overall_max:.4f}px  "
            f"min={overall_min:.4f}px  std={overall_std:.4f}px"
        )
        _logger.info("\n".join(lines))

        # Per-image extrinsics
        ext_lines = ["\n  PER-IMAGE EXTRINSICS  (board→camera)"]
        ext_lines.append(
            f"  {'Img':>4}  {'tx (mm)':>9}  {'ty (mm)':>9}  {'tz (mm)':>9}  {'tilt (°)':>9}"
        )
        ext_lines.append(
            f"  {'---':>4}  {'-------':>9}  {'-------':>9}  {'-------':>9}  {'--------':>9}"
        )
        for i, (rvec, tvec) in enumerate(zip(rvecs, tvecs)):
            t = tvec.ravel()
            rot_deg = float(np.linalg.norm(rvec)) * 180.0 / np.pi
            ext_lines.append(
                f"  {i:>4}  {t[0]:>+9.2f}  {t[1]:>+9.2f}  {t[2]:>+9.2f}  {rot_deg:>9.2f}"
            )
        _logger.info("\n".join(ext_lines))

        self._publish(
            f"[CharuCo Calib] mean_err={overall_mean:.4f}px  max_err={overall_max:.4f}px  "
            f"fx={fx:.1f} fy={fy:.1f} HFOV={hfov:.1f}° VFOV={vfov:.1f}°  "
            f"tz=[{tz_min:.1f}…{tz_max:.1f}]mm  tilt=[{rot_min:.1f}…{rot_max:.1f}]°"
        )

    # ── Brightness ────────────────────────────────────────────────────────────

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

    # ── Robot helpers ─────────────────────────────────────────────────────────

    def _move_relative(
        self,
        dx: float = 0.0,
        dy: float = 0.0,
        dz: float = 0.0,
        drx: float = 0.0,
        dry: float = 0.0,
        drz: float = 0.0,
    ) -> bool:
        pos = self._robot.get_current_position()
        target = [
            pos[0] + dx,
            pos[1] + dy,
            pos[2] + dz,
            pos[3] + drx,
            pos[4] + dry,
            pos[5] + drz,
        ]
        return self._robot.move_ptp(
            position=target,
            tool=self._robot_config.robot_tool,
            user=self._robot_config.robot_user,
            velocity=self._config.velocity,
            acceleration=self._config.acceleration,
            wait_to_reach=True,
        )

    def _move_absolute(self, pose: List[float]) -> bool:
        return self._robot.move_ptp(
            position=pose,
            tool=self._robot_config.robot_tool,
            user=self._robot_config.robot_user,
            velocity=self._config.velocity,
            acceleration=self._config.acceleration,
            wait_to_reach=True,
        )



    def _save_frame(self, frame: np.ndarray, tag: str, output_dir: str) -> Optional[str]:
        path = os.path.join(output_dir, f"{tag}.png")
        ok = cv2.imwrite(path, frame)
        if not ok:
            _logger.error("Failed to save frame to %s", path)
            return None
        return path

    def _publish(self, message: str) -> None:
        _logger.info("[IntrinsicCapture] %s", message)
        if self._messaging is not None:
            try:
                self._messaging.publish(INTRINSIC_CAPTURE_PROGRESS_TOPIC, message)
            except Exception:
                pass
