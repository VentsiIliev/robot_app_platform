import logging
import cv2
import numpy as np
from typing import Callable, List, Optional, Tuple

from src.engine.vision.implementation.plvision.PLVision import Contouring
from src.engine.vision.implementation.VisionSystem.core.settings.CameraSettings import CameraSettings

_logger = logging.getLogger(__name__)

_THRESHOLD_TYPES = {
    "binary":     cv2.THRESH_BINARY,
    "binary_inv": cv2.THRESH_BINARY_INV,
    "trunc":      cv2.THRESH_TRUNC,
    "tozero":     cv2.THRESH_TOZERO,
    "tozero_inv": cv2.THRESH_TOZERO_INV,
}

_SUBPIX_CRITERIA = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.001)


class ContourDetectionService:

    def __init__(self, camera_settings: CameraSettings, message_publisher=None):
        self._settings  = camera_settings
        self._publisher = message_publisher

    def detect(
        self,
        image: np.ndarray,
        threshold: int,
        is_calibrated: bool,
        correct_image_fn: Callable[[np.ndarray], np.ndarray],
        spray_area_points: Optional[np.ndarray],
        sort: bool = False,
    ) -> Tuple[Optional[List], Optional[np.ndarray], None]:
        corrected = correct_image_fn(image.copy()) if is_calibrated else self._stamp_uncalibrated(image.copy())

        raw, gray  = self._find_contours(corrected, threshold)
        approxed   = self._approx_contours(raw)
        refined    = self._refine_subpixel(approxed, gray)
        filtered   = self._filter_by_area(refined)

        inside = filtered if spray_area_points is None else [
            c for c in filtered if self._all_inside(spray_area_points, c)
        ]
        if not inside:
            if self._publisher:
                self._publisher.publish_latest_image(corrected)
            return None, corrected, None

        final = self._sort_by_proximity(inside) if sort else inside

        if self._settings.get_draw_contours():
            cv2.drawContours(corrected, [c.astype(np.int32) for c in final], -1, (0, 255, 0), 1)

        if self._publisher:
            self._publisher.publish_latest_image(corrected)

        return final, corrected, None

    # ── private ───────────────────────────────────────────────────────

    def _find_contours(self, image: np.ndarray, threshold: int) -> Tuple[list, np.ndarray]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        if self._settings.get_gaussian_blur():
            k = self._settings.get_blur_kernel_size()
            k = k + 1 if k % 2 == 0 else k
            blur = cv2.GaussianBlur(gray, (k, k), 0)
        else:
            blur = gray

        thresh_type = _THRESHOLD_TYPES.get(self._settings.get_threshold_type(), cv2.THRESH_BINARY_INV)
        _, thresh = cv2.threshold(blur, threshold, 255, thresh_type)

        if self._publisher:
            self._publisher.publish_thresh_image(thresh)

        if self._settings.get_dilate_enabled():
            k = self._settings.get_dilate_kernel_size()
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
            thresh = cv2.dilate(thresh, kernel, iterations=self._settings.get_dilate_iterations())

        if self._settings.get_erode_enabled():
            k = self._settings.get_erode_kernel_size()
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (k, k))
            thresh = cv2.erode(thresh, kernel, iterations=self._settings.get_erode_iterations())

        contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        return list(contours), gray  # gray is pre-blur — sharper gradients for sub-pixel

    def _approx_contours(self, contours: list) -> list:
        return contours
        eps = self._settings.get_epsilon()
        return [
            cv2.approxPolyDP(c, eps * cv2.arcLength(c, True), True)
            for c in contours
        ]

    @staticmethod
    def _refine_subpixel(contours: list, gray: np.ndarray) -> list:
        refined = []
        for contour in contours:
            pts = contour.reshape(-1, 1, 2).astype(np.float32)
            pts_refined = cv2.cornerSubPix(gray, pts, (5, 5), (-1, -1), _SUBPIX_CRITERIA)
            refined.append(pts_refined.reshape(-1, 1, 2))
        return refined

    def _filter_by_area(self, contours: list) -> list:
        lo = self._settings.get_min_contour_area()
        hi = self._settings.get_max_contour_area()
        return [c for c in contours if lo < cv2.contourArea(c) < hi]

    @staticmethod
    def _all_inside(spray_area_points: np.ndarray, contour) -> bool:
        pts = spray_area_points.astype(np.float32)
        return all(
            cv2.pointPolygonTest(pts, (float(p[0][0]), float(p[0][1])), False) >= 0
            for p in contour
        )

    @staticmethod
    def _sort_by_proximity(contours: list) -> list:
        result, current, remaining = [], (0, 0), contours.copy()
        while remaining:
            nearest = min(remaining, key=lambda c: (
                (Contouring.calculateCentroid(c)[0] - current[0]) ** 2 +
                (Contouring.calculateCentroid(c)[1] - current[1]) ** 2
            ))
            result.append(nearest)
            current = Contouring.calculateCentroid(nearest)
            remaining.remove(nearest)
        return result

    @staticmethod
    def _stamp_uncalibrated(image: np.ndarray) -> np.ndarray:
        cv2.putText(image, "System is not calibrated", (10, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        return image
