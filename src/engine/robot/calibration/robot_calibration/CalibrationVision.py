import logging
from dataclasses import dataclass

import cv2
import numpy as np

from src.engine.vision.implementation.VisionSystem.features.calibration.charuco.charuco_detector import (
    AutoCharucoBoardDetector,
)

_logger = logging.getLogger(__name__)


@dataclass
class ChessboardDetectionResult:
    found: bool
    ppm: float
    bottom_left_px: tuple
    message: str
    board_kind: str = "unknown"

    def to_dict(self):
        return {
            "found": self.found,
            "ppm": self.ppm,
            "bottom_left_px": (float(self.bottom_left_px[0]), float(self.bottom_left_px[1])) if self.bottom_left_px is not None else None
        }


@dataclass()
class SpecificMarkerDetectionResult:
    found: bool
    aruco_corners: np.ndarray
    aruco_ids: np.ndarray
    frame: np.ndarray


@dataclass
class FindRequiredMarkersResult:
    found: bool
    frame: np.ndarray


class CalibrationVision:
    def __init__(self, vision_service, chessboard_size, square_size_mm, required_ids, debug,
                 use_marker_centre: bool = False, perspective_matrix=None,
                 reference_board_mode: str = "auto", charuco_board_size=None, charuco_marker_size_mm: float | None = None):
        self.bottom_left_chessboard_corner_px = None
        self.chessboard_center_px = None
        self.original_chessboard_corners = None
        self.original_board_object_points = None
        self.detected_reference_board_kind = None
        self.vision_service = vision_service
        self.chessboard_size = chessboard_size  # (cols, rows)
        self.square_size_mm = square_size_mm
        self.reference_board_mode = str(reference_board_mode or "auto").lower()
        self.charuco_board_size = charuco_board_size
        self.charuco_marker_size_mm = charuco_marker_size_mm
        self.debug = debug
        self.required_ids = required_ids
        self.detected_ids = set()
        self.marker_top_left_corners = {}
        self.marker_top_left_corners_mm = {}
        self.PPM = None
        self.use_marker_centre = use_marker_centre
        self.perspective_matrix = None
        if perspective_matrix is not None:
            _logger.info("Robot calibration perspective transform is disabled; using raw vision frames")

    def _filter_detected_markers(self, aruco_corners, aruco_ids):
        if aruco_ids is None or len(aruco_ids) == 0:
            return aruco_corners, aruco_ids, []

        # Robot calibration uses a ChArUco board, so the board dimensions are
        # square counts, not marker counts. Only roughly half the squares carry
        # ArUco markers, with IDs laid out sequentially from 0.
        cols, rows = self.charuco_board_size or self.chessboard_size
        max_valid_marker_id = max(int((int(cols) * int(rows)) // 2) - 1, -1)
        if max_valid_marker_id < 0:
            return aruco_corners, aruco_ids, []

        flat_ids = [int(marker_id) for marker_id in np.array(aruco_ids).flatten()]
        keep_indices = [i for i, marker_id in enumerate(flat_ids) if 0 <= marker_id <= max_valid_marker_id]
        rejected_ids = [marker_id for marker_id in flat_ids if marker_id < 0 or marker_id > max_valid_marker_id]

        if rejected_ids:
            _logger.warning(
                "Discarding out-of-board ChArUco marker IDs: %s (valid range: 0..%d)",
                rejected_ids,
                max_valid_marker_id,
            )

        if not keep_indices:
            return [], np.empty((0, 1), dtype=np.int32), rejected_ids

        filtered_corners = [aruco_corners[i] for i in keep_indices]
        filtered_ids = np.array([[flat_ids[i]] for i in keep_indices], dtype=np.int32)
        return filtered_corners, filtered_ids, rejected_ids

    def _warp_frame(self, frame):
        """Apply perspective correction to the whole image. Returns the frame unchanged when no matrix is set."""
        if self.perspective_matrix is None or frame is None:
            return frame
        h, w = frame.shape[:2]
        return cv2.warpPerspective(frame, self.perspective_matrix, (w, h))

    def _compute_perspective_from_chessboard(self, frame):
        """Detect chessboard on a raw frame and derive a perspective matrix from its 4 outer corners.

        The chessboard is a known physical rectangle, so we map its detected
        (potentially trapezoidal) corners to the ideal rectangular positions,
        preserving scale and centroid.  Returns None when detection fails.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        ret, corners = cv2.findChessboardCorners(gray, self.chessboard_size, None)
        if not ret:
            return None

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

        cols, rows = self.chessboard_size

        tl = corners_refined[0, 0]
        tr = corners_refined[cols - 1, 0]
        br = corners_refined[(rows - 1) * cols + (cols - 1), 0]
        bl = corners_refined[(rows - 1) * cols, 0]

        src = np.array([tl, tr, br, bl], dtype=np.float32)
        cx, cy = src.mean(axis=0)

        phys_w = (cols - 1) * self.square_size_mm
        phys_h = (rows - 1) * self.square_size_mm

        h_span = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2.0
        v_span = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2.0
        avg_ppm = ((h_span / phys_w) + (v_span / phys_h)) / 2.0

        dst_w = phys_w * avg_ppm
        dst_h = phys_h * avg_ppm
        dst = np.array([
            [cx - dst_w / 2, cy - dst_h / 2],
            [cx + dst_w / 2, cy - dst_h / 2],
            [cx + dst_w / 2, cy + dst_h / 2],
            [cx - dst_w / 2, cy + dst_h / 2],
        ], dtype=np.float32)

        matrix = cv2.getPerspectiveTransform(src, dst)
        _logger.info("Perspective matrix derived from chessboard outer corners "
                      "(tl=%s, tr=%s, br=%s, bl=%s)", tl, tr, br, bl)

        tilt_x_rad = np.arctan2(matrix[0, 1], matrix[0, 0])
        tilt_y_rad = np.arctan2(-matrix[1, 0], matrix[1, 1])
        rx_deg = np.degrees(tilt_y_rad)
        ry_deg = -np.degrees(tilt_x_rad)
        _logger.info(
            "📐 Camera tilt from chessboard perspective matrix:\n"
            "  ┌─────────────────────────────────────────┐\n"
            "  │  Axis │    rad    │    deg    │ Workobj  │\n"
            "  ├─────────────────────────────────────────┤\n"
            "  │  RX   │  %+.4f  │  %+.3f°  │  %+.3f°  │\n"
            "  │  RY   │  %+.4f  │  %+.3f°  │  %+.3f°  │\n"
            "  │  RZ   │   0.0000  │   0.000°  │   0.000° │\n"
            "  └─────────────────────────────────────────┘",
            tilt_y_rad, rx_deg, -rx_deg,
            -tilt_x_rad, ry_deg, -ry_deg,
        )

        return matrix

    def find_chessboard_and_compute_ppm(self, frame) -> ChessboardDetectionResult:
        if frame is None:
            _logger.debug("No frame provided for board detection")
            return ChessboardDetectionResult(
                found=False,
                ppm=None,
                bottom_left_px=None,
                message="No frame provided",
                board_kind="none",
            )

        _logger.info(
            "Reference board detection config: mode=%s chessboard_size=%s charuco_board_size=%s square_size_mm=%.3f charuco_marker_size_mm=%s",
            self.reference_board_mode,
            self.chessboard_size,
            self.charuco_board_size,
            float(self.square_size_mm),
            "auto" if not self.charuco_marker_size_mm else f"{float(self.charuco_marker_size_mm):.3f}",
        )
        if self.reference_board_mode == "charuco":
            _logger.info("Reference board detection mode: charuco-only")
            charuco_result = self._find_charuco_board_and_compute_ppm(frame)
            if charuco_result.found:
                return charuco_result
            chessboard_result = ChessboardDetectionResult(
                found=False,
                ppm=None,
                bottom_left_px=None,
                message="Chessboard fallback disabled (charuco-only mode)",
                board_kind="chessboard",
            )
        elif self.reference_board_mode == "chessboard":
            _logger.info("Reference board detection mode: chessboard-only")
            charuco_result = ChessboardDetectionResult(
                found=False,
                ppm=None,
                bottom_left_px=None,
                message="ChArUco detection disabled (chessboard-only mode)",
                board_kind="charuco",
            )
            chessboard_result = self._find_classic_chessboard_and_compute_ppm(frame)
            if chessboard_result.found:
                return chessboard_result
        else:
            _logger.info("Reference board detection mode: auto (ChArUco first, chessboard fallback)")
            charuco_result = self._find_charuco_board_and_compute_ppm(frame)
            if charuco_result.found:
                return charuco_result

            chessboard_result = self._find_classic_chessboard_and_compute_ppm(frame)
            if chessboard_result.found:
                return chessboard_result

        _logger.warning(
            "Reference board detection failed for both modes: charuco_message=%s chessboard_message=%s",
            charuco_result.message,
            chessboard_result.message,
        )

        self.bottom_left_chessboard_corner_px = None
        self.chessboard_center_px = None
        self.original_chessboard_corners = None
        self.original_board_object_points = None
        self.detected_reference_board_kind = None
        return ChessboardDetectionResult(
            found=False,
            ppm=None,
            bottom_left_px=None,
            message=(
                f"Reference board not detected for mode={self.reference_board_mode}"
            ),
            board_kind="none",
        )

    def _find_classic_chessboard_and_compute_ppm(self, frame) -> ChessboardDetectionResult:
        _logger.info("Trying classic chessboard fallback: pattern_size=%s square_size_mm=%.3f", self.chessboard_size, float(self.square_size_mm))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        ret, corners = cv2.findChessboardCorners(gray, self.chessboard_size, None)
        if not ret:
            return ChessboardDetectionResult(
                found=False,
                ppm=None,
                bottom_left_px=None,
                message="Classic chessboard not detected",
                board_kind="chessboard",
            )

        _logger.info(f"Found classic chessboard! Detected {len(corners)} corners")
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        self.original_chessboard_corners = corners_refined
        self.original_board_object_points = None
        self.detected_reference_board_kind = "chessboard"

        cols, rows = self.chessboard_size
        self.bottom_left_chessboard_corner_px = corners_refined[(rows - 1) * cols, 0]
        _logger.debug(f"Bottom-left chessboard corner (px): {self.bottom_left_chessboard_corner_px}")

        self.chessboard_center_px = self._compute_grid_center_from_ordered_corners(corners_refined, cols, rows)
        _logger.debug(f"Chessboard center (px): {self.chessboard_center_px}")

        ppm = self.__compute_ppm_from_corners(corners_refined, cols, rows)
        return ChessboardDetectionResult(
            found=True,
            ppm=ppm,
            bottom_left_px=self.bottom_left_chessboard_corner_px,
            message="Classic chessboard detected successfully",
            board_kind="chessboard",
        )

    def _find_charuco_board_and_compute_ppm(self, frame) -> ChessboardDetectionResult:
        try:
            dictionary_id = self._get_charuco_dictionary_id()
            board_size = self.charuco_board_size or self.chessboard_size
            square_size_mm = float(self.square_size_mm)
            marker_length_mm = float(self.charuco_marker_size_mm or (square_size_mm * 0.75))
            _logger.info(
                "Trying ChArUco reference board: board_size=%s square_size_mm=%.3f marker_size_mm=%.3f dictionary_id=%s",
                board_size,
                square_size_mm,
                marker_length_mm,
                dictionary_id,
            )
            detector = AutoCharucoBoardDetector(
                squares_x=int(board_size[0]),
                squares_y=int(board_size[1]),
                square_length=square_size_mm,
                marker_length=marker_length_mm,
                dictionary_id=dictionary_id,
            )
            detection = detector.detect(frame)
        except Exception as exc:
            _logger.warning("ChArUco reference-board detection failed: %s", exc)
            return ChessboardDetectionResult(
                found=False,
                ppm=None,
                bottom_left_px=None,
                message=f"ChArUco detector error: {exc}",
                board_kind="charuco",
            )

        n_corners = 0 if detection.charuco_ids is None else len(detection.charuco_ids)
        if detection.charuco_corners is None or detection.charuco_ids is None or n_corners < 4:
            _logger.info(
                "ChArUco reference board insufficient corners: markers=%d corners=%d mode=%s",
                0 if detection.marker_ids is None else len(detection.marker_ids),
                n_corners,
                detection.mode,
            )
            return ChessboardDetectionResult(
                found=False,
                ppm=None,
                bottom_left_px=None,
                message=f"ChArUco board not detected (corners={n_corners}, need >=4)",
                board_kind="charuco",
            )

        board = detector.legacy.board if detection.mode == "legacy" else detector.normal.board
        board_corners_3d = np.asarray(board.getChessboardCorners(), dtype=np.float32)
        ids = detection.charuco_ids.reshape(-1).astype(np.int32)
        img_pts = detection.charuco_corners.reshape(-1, 2).astype(np.float32)
        obj_pts = board_corners_3d[ids]
        obj_pts_2d = obj_pts[:, :2].astype(np.float32)

        homography, _ = cv2.findHomography(obj_pts_2d, img_pts, method=0)
        if homography is None:
            return ChessboardDetectionResult(
                found=False,
                ppm=None,
                bottom_left_px=None,
                message="ChArUco board detected, but homography solve failed",
                board_kind="charuco",
            )

        self.original_chessboard_corners = img_pts.reshape(-1, 1, 2)
        self.original_board_object_points = obj_pts.reshape(-1, 3).astype(np.float32)
        self.detected_reference_board_kind = "charuco"

        board_size = self.charuco_board_size or self.chessboard_size
        inner_cols = max(int(board_size[0]) - 1, 1)
        inner_rows = max(int(board_size[1]) - 1, 1)
        all_inner_obj_pts = board_corners_3d[:, :2].astype(np.float32)
        projected_inner_pts = cv2.perspectiveTransform(
            all_inner_obj_pts.reshape(-1, 1, 2),
            homography,
        ).reshape(-1, 2)

        bottom_left_index = (inner_rows - 1) * inner_cols
        self.bottom_left_chessboard_corner_px = projected_inner_pts[bottom_left_index].astype(np.float32)
        self.chessboard_center_px = self._compute_grid_center_from_ordered_corners(
            projected_inner_pts.reshape(-1, 1, 2),
            inner_cols,
            inner_rows,
        )

        ppm = self.__compute_ppm_from_object_points(img_pts, obj_pts_2d)

        _logger.info(
            "Found ChArUco reference board! mode=%s corners=%d dict=%d",
            detection.mode,
            n_corners,
            dictionary_id,
        )
        _logger.debug(f"Bottom-left ChArUco corner (px): {self.bottom_left_chessboard_corner_px}")
        _logger.debug(f"ChArUco board center (px): {self.chessboard_center_px}")

        return ChessboardDetectionResult(
            found=True,
            ppm=ppm,
            bottom_left_px=self.bottom_left_chessboard_corner_px,
            message=(
                f"ChArUco board detected successfully ({n_corners} corners, mode={detection.mode})"
            ),
            board_kind="charuco",
        )

    def _get_charuco_dictionary_id(self) -> int:
        dictionary_name = "DICT_4X4_1000"
        camera_settings = getattr(getattr(self.vision_service, "_vision_system", None), "camera_settings", None)
        if camera_settings is not None and hasattr(camera_settings, "get_aruco_dictionary"):
            dictionary_name = camera_settings.get_aruco_dictionary() or dictionary_name
        return getattr(cv2.aruco, str(dictionary_name), cv2.aruco.DICT_4X4_1000)

    def _compute_grid_center_from_ordered_corners(self, corners_refined, cols, rows):
        _logger.debug(f"Board dimensions: {rows} rows x {cols} cols")
        _logger.debug(f"Row parity: {'even' if rows % 2 == 0 else 'odd'}, Col parity: {'even' if cols % 2 == 0 else 'odd'}")

        if rows % 2 == 0 and cols % 2 == 0:
            center_row1 = rows // 2 - 1
            center_row2 = rows // 2
            center_col1 = cols // 2 - 1
            center_col2 = cols // 2
            idx1 = center_row1 * cols + center_col1
            idx2 = center_row1 * cols + center_col2
            idx3 = center_row2 * cols + center_col1
            idx4 = center_row2 * cols + center_col2
            center_x = (
                corners_refined[idx1, 0, 0] + corners_refined[idx2, 0, 0] +
                corners_refined[idx3, 0, 0] + corners_refined[idx4, 0, 0]
            ) / 4.0
            center_y = (
                corners_refined[idx1, 0, 1] + corners_refined[idx2, 0, 1] +
                corners_refined[idx3, 0, 1] + corners_refined[idx4, 0, 1]
            ) / 4.0
            return (float(center_x), float(center_y))

        center_row = rows // 2
        center_col = cols // 2
        center_corner_index = center_row * cols + center_col
        return (
            float(corners_refined[center_corner_index, 0, 0]),
            float(corners_refined[center_corner_index, 0, 1]),
        )

    def __compute_ppm_from_corners(self, corners_refined, cols=None, rows=None):
        """Compute pixels-per-mm from ordered board corners."""
        cols = int(cols if cols is not None else self.chessboard_size[0])
        rows = int(rows if rows is not None else self.chessboard_size[1])
        horiz, vert = [], []
        # corners_refined has shape (n_corners, 1, 2), so we need to access [i, 0]
        for r in range(rows):  # horizontal neighbors
            base = r * cols
            for c in range(cols - 1):
                i1 = base + c
                i2 = base + c + 1
                pt1 = corners_refined[i1, 0]  # Extract (x, y) coordinates
                pt2 = corners_refined[i2, 0]  # Extract (x, y) coordinates
                horiz.append(np.linalg.norm(pt2 - pt1))

        for r in range(rows - 1):  # vertical neighbors
            for c in range(cols):
                i1 = r * cols + c
                i2 = (r + 1) * cols + c
                pt1 = corners_refined[i1, 0]  # Extract (x, y) coordinates
                pt2 = corners_refined[i2, 0]  # Extract (x, y) coordinates
                vert.append(np.linalg.norm(pt2 - pt1))

        all_d = np.array(horiz + vert, dtype=np.float32)
        if all_d.size == 0:
            return None

        avg_square_px = float(np.mean(all_d))
        ppm = avg_square_px / float(self.square_size_mm)
        _logger.debug(f"PPM calculation debug: avg_square_px={avg_square_px:.3f}, square_size_mm={self.square_size_mm:.2f}, ppm={ppm:.3f}")

        return ppm

    def __compute_ppm_from_object_points(self, image_points, object_points_2d):
        """Compute pixels-per-mm from detected ChArUco corner correspondences."""
        horiz, vert = [], []
        points_by_key = {}
        for img_pt, obj_pt in zip(image_points, object_points_2d):
            key = (round(float(obj_pt[0]), 6), round(float(obj_pt[1]), 6))
            points_by_key[key] = np.asarray(img_pt, dtype=np.float32)

        for (x, y), img_pt in points_by_key.items():
            right_key = (round(x + float(self.square_size_mm), 6), round(y, 6))
            up_key = (round(x, 6), round(y + float(self.square_size_mm), 6))
            if right_key in points_by_key:
                horiz.append(np.linalg.norm(points_by_key[right_key] - img_pt))
            if up_key in points_by_key:
                vert.append(np.linalg.norm(points_by_key[up_key] - img_pt))

        all_d = np.array(horiz + vert, dtype=np.float32)
        if all_d.size == 0:
            return None

        avg_square_px = float(np.mean(all_d))
        ppm = avg_square_px / float(self.square_size_mm)
        _logger.debug(
            "ChArUco PPM calculation debug: avg_square_px=%.3f, square_size_mm=%.2f, ppm=%.3f",
            avg_square_px,
            self.square_size_mm,
            ppm,
        )
        return ppm

    def find_required_aruco_markers(self, frame) -> FindRequiredMarkersResult:
        arucoCorners, arucoIds, image = self.vision_service.detect_aruco_markers(frame)
        arucoCorners, arucoIds, _ = self._filter_detected_markers(arucoCorners, arucoIds)

        if arucoIds is not None:
            _logger.debug(f"Detected {len(arucoIds)} ArUco markers")
            _logger.debug(f"Marker IDs: {arucoIds.flatten()}")

            for i, marker_id in enumerate(arucoIds.flatten()):
                if marker_id in self.required_ids:
                    self.detected_ids.add(marker_id)
                    corners_4 = arucoCorners[i][0]          # shape (4, 2) float32
                    if self.use_marker_centre:
                        ref_pt = corners_4.mean(axis=0)     # rotation-invariant centre
                    else:
                        ref_pt = corners_4[0]               # top-left corner
                    self.marker_top_left_corners[marker_id] = ref_pt.astype(np.float32)

            _logger.debug(f"Currently have: {self.detected_ids}")
            _logger.debug(f"Still missing: {self.required_ids - self.detected_ids}")

            all_found = self.required_ids.issubset(self.detected_ids)
            if all_found:
                _logger.debug("All required ArUco markers found!")

            return FindRequiredMarkersResult(found=all_found, frame=frame)

        return FindRequiredMarkersResult(found=False, frame=frame)

    def update_marker_top_left_corners(self, marker_id, corners, ids):
        for i, iter_marker_id in enumerate(ids.flatten()):
            if iter_marker_id != marker_id:
                continue
            corners_4 = corners[i][0]               # shape (4, 2) float32
            if self.use_marker_centre:
                ref_pt = corners_4.mean(axis=0)     # rotation-invariant centre
            else:
                ref_pt = corners_4[0]               # top-left corner
            self.marker_top_left_corners[marker_id] = ref_pt.astype(np.float32)

            x_mm = (ref_pt[0] - self.bottom_left_chessboard_corner_px[0]) / self.PPM
            y_mm = (ref_pt[1] - self.bottom_left_chessboard_corner_px[1]) / self.PPM
            self.marker_top_left_corners_mm[marker_id] = (x_mm, y_mm)

    # def update_marker_top_left_corners(self, marker_id, corners, ids):
    #     for i, iter_marker_id in enumerate(ids.flatten()):
    #         if iter_marker_id != marker_id:
    #             continue
    #         # update marker top-left corner in pixels
    #         top_left_corner_px = tuple(corners[i][0][0].astype(int))
    #         self.marker_top_left_corners[marker_id] = top_left_corner_px
    #
    #         # Convert to mm relative to bottom-left of chessboard
    #         x_mm = (top_left_corner_px[0] - self.bottom_left_chessboard_corner_px[0]) / self.PPM
    #         y_mm = (self.bottom_left_chessboard_corner_px[1] - top_left_corner_px[1]) / self.PPM
    #
    #         # update marker top-left corner in mm
    #         self.marker_top_left_corners_mm[marker_id] = (x_mm, y_mm)

    def collect_reference_sample(self, frame, allowed_ids=None) -> dict:
        """
        Detect required markers in a single frame and return their corner positions.
        Does NOT update internal state — used exclusively for multi-frame averaging.
        Returns {marker_id: np.ndarray([x, y], float32)} for each detected marker.
        """
        arucoCorners, arucoIds, _ = self.vision_service.detect_aruco_markers(frame)
        arucoCorners, arucoIds, _ = self._filter_detected_markers(arucoCorners, arucoIds)
        sample = {}
        allowed_id_set = None if allowed_ids is None else {int(marker_id) for marker_id in allowed_ids}
        if arucoIds is None:
            return sample
        for i, marker_id in enumerate(arucoIds.flatten()):
            if allowed_id_set is not None and int(marker_id) not in allowed_id_set:
                continue
            corners_4 = arucoCorners[i][0]
            ref_pt = corners_4.mean(axis=0) if self.use_marker_centre else corners_4[0]
            sample[int(marker_id)] = ref_pt.astype(np.float32)
        return sample

    def detect_specific_marker(self, frame, marker_id) -> SpecificMarkerDetectionResult:
        marker_found = False
        arucoCorners, arucoIds, image = self.vision_service.detect_aruco_markers(image=frame)
        arucoCorners, arucoIds, _ = self._filter_detected_markers(arucoCorners, arucoIds)
        if arucoIds is not None and marker_id in arucoIds:
            marker_found = True
        return SpecificMarkerDetectionResult(found=marker_found,
                                             aruco_corners=arucoCorners,
                                             aruco_ids=arucoIds,
                                             frame=frame)
