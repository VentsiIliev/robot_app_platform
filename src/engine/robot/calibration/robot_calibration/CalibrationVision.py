import logging
from dataclasses import dataclass

import cv2
import numpy as np

_logger = logging.getLogger(__name__)


@dataclass
class ChessboardDetectionResult:
    found: bool
    ppm: float
    bottom_left_px: tuple
    message: str

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
    def __init__(self, vision_service, chessboard_size, square_size_mm, required_ids, debug_draw, debug,
                 use_marker_centre: bool = False, perspective_matrix=None):
        self.bottom_left_chessboard_corner_px = None
        self.chessboard_center_px = None
        self.original_chessboard_corners = None
        self.vision_service = vision_service
        self.chessboard_size = chessboard_size  # (cols, rows)
        self.square_size_mm = square_size_mm
        self.debug_draw = debug_draw
        self.debug = debug
        self.required_ids = required_ids
        self.detected_ids = set()
        self.marker_top_left_corners = {}
        self.marker_top_left_corners_mm = {}
        self.PPM = None
        self.use_marker_centre = use_marker_centre
        self.perspective_matrix = perspective_matrix

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
            _logger.debug("No frame provided for chessboard detection")
            return ChessboardDetectionResult(found=False, ppm=None, bottom_left_px=None, message="No frame provided")

        # If no perspective matrix exists yet, try to derive one from the chessboard
        if self.perspective_matrix is None:
            matrix = self._compute_perspective_from_chessboard(frame)
            if matrix is not None:
                self.perspective_matrix = matrix

        # Warp the frame so all detection and coordinate extraction happen in corrected space
        frame = self._warp_frame(frame)

        _logger.debug(f"Looking for chessboard of size: {self.chessboard_size}")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        ret, corners = cv2.findChessboardCorners(gray, self.chessboard_size, None)
        cv2.imwrite("robot_calibration_chessboard_detection_debug.png", frame)

        if ret:
            _logger.info(f"Found chessboard! Detected {len(corners)} corners")
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            self.original_chessboard_corners = corners_refined

            cols, rows = self.chessboard_size
            self.bottom_left_chessboard_corner_px = corners_refined[(rows - 1) * cols, 0]

            _logger.debug(f"Bottom-left chessboard corner (px): {self.bottom_left_chessboard_corner_px}")
            # Draw bottom-left corner marker
            bottom_left_px = tuple(self.bottom_left_chessboard_corner_px.astype(int))
            cv2.circle(frame, bottom_left_px, 8, (0, 0, 255), -1)  # Red circle
            cv2.putText(frame, "BL", (bottom_left_px[0] + 10, bottom_left_px[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            # --- Compute chessboard center ---
            _logger.debug(f"Chessboard dimensions: {rows} rows x {cols} cols")
            _logger.debug(f"Row parity: {'even' if rows % 2 == 0 else 'odd'}, Col parity: {'even' if cols % 2 == 0 else 'odd'}")

            # For even-dimensioned chessboards, calculate center as average of 4 central corners
            if rows % 2 == 0 and cols % 2 == 0:
                _logger.debug("Using 4-corner averaging method for even dimensions")
                # Even dimensions - use 4 central corners
                center_row1 = rows // 2 - 1
                center_row2 = rows // 2
                center_col1 = cols // 2 - 1
                center_col2 = cols // 2

                # Get the 4 central corner indices
                idx1 = center_row1 * cols + center_col1  # top-left of center
                idx2 = center_row1 * cols + center_col2  # top-right of center
                idx3 = center_row2 * cols + center_col1  # bottom-left of center
                idx4 = center_row2 * cols + center_col2  # bottom-right of center

                _logger.debug(f"Central corner indices: {idx1}, {idx2}, {idx3}, {idx4}")

                # Average the 4 central corners
                center_x = (corners_refined[idx1, 0, 0] + corners_refined[idx2, 0, 0] +
                            corners_refined[idx3, 0, 0] + corners_refined[idx4, 0, 0]) / 4.0
                center_y = (corners_refined[idx1, 0, 1] + corners_refined[idx2, 0, 1] +
                            corners_refined[idx3, 0, 1] + corners_refined[idx4, 0, 1]) / 4.0

                self.chessboard_center_px = (float(center_x), float(center_y))
            else:
                _logger.debug("Using single center corner method for odd dimensions")

                # Odd dimensions - use single center corner
                center_row = rows // 2
                center_col = cols // 2
                center_corner_index = center_row * cols + center_col

                _logger.debug(f"Center corner: row {center_row}, col {center_col}, index {center_corner_index}")

                self.chessboard_center_px = (
                    float(corners_refined[center_corner_index, 0, 0]),
                    float(corners_refined[center_corner_index, 0, 1])
                )
            _logger.debug(f"Chessboard center (px): {self.chessboard_center_px}")

            if self.debug:
                self.debug_draw.draw_image_center(frame)

            ppm = self.__compute_ppm_from_corners(corners_refined)

            cv2.drawChessboardCorners(frame, self.chessboard_size, corners_refined, ret)
            return ChessboardDetectionResult(found=True, ppm=ppm, bottom_left_px=self.bottom_left_chessboard_corner_px, message="Chessboard detected successfully")
        else:
            cv2.putText(frame, "No chessboard detected", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            self.bottom_left_chessboard_corner_px = None
            return ChessboardDetectionResult(found=False, ppm=None, bottom_left_px=None, message="Chessboard not detected")

    def __compute_ppm_from_corners(self, corners_refined):
        """Compute pixels-per-mm from chessboard corners"""
        cols, rows = self.chessboard_size
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

    def find_required_aruco_markers(self, frame) -> FindRequiredMarkersResult:
        frame = self._warp_frame(frame)
        arucoCorners, arucoIds, image = self.vision_service.detect_aruco_markers(frame)

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
                    cv2.circle(frame, tuple(ref_pt.astype(int)), 2, (0, 255, 0), -1)

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

    def collect_reference_sample(self, frame) -> dict:
        """
        Detect required markers in a single frame and return their corner positions.
        Does NOT update internal state — used exclusively for multi-frame averaging.
        Returns {marker_id: np.ndarray([x, y], float32)} for each detected required marker.
        """
        frame = self._warp_frame(frame)
        arucoCorners, arucoIds, _ = self.vision_service.detect_aruco_markers(frame)
        sample = {}
        if arucoIds is None:
            return sample
        for i, marker_id in enumerate(arucoIds.flatten()):
            if marker_id in self.required_ids:
                corners_4 = arucoCorners[i][0]
                ref_pt = corners_4.mean(axis=0) if self.use_marker_centre else corners_4[0]
                sample[marker_id] = ref_pt.astype(np.float32)
        return sample

    def detect_specific_marker(self, frame, marker_id) -> SpecificMarkerDetectionResult:
        frame = self._warp_frame(frame)
        marker_found = False
        arucoCorners, arucoIds, image = self.vision_service.detect_aruco_markers(image=frame)
        if arucoIds is not None and marker_id in arucoIds:
            marker_found = True
        return SpecificMarkerDetectionResult(found=marker_found,
                                             aruco_corners=arucoCorners,
                                             aruco_ids=arucoIds,
                                             frame=frame)


