from typing import List, Optional, Tuple
import logging

import numpy as np

from src.applications.contour_matching_tester.service.i_contour_matching_tester_service import IContourMatchingTesterService

_logger = logging.getLogger(__name__)


def _close_contour(contour: np.ndarray) -> np.ndarray:
    pts = np.asarray(contour, dtype=np.float32).reshape(-1, 2)
    if len(pts) >= 2 and not np.allclose(pts[0], pts[-1], atol=0.5):
        pts = np.vstack([pts, pts[0:1]])
    return pts.reshape(-1, 1, 2)


class ContourMatchingTesterService(IContourMatchingTesterService):

    def __init__(self, vision_service=None, workpiece_service=None):
        self._vision_service    = vision_service
        self._workpiece_service = workpiece_service
        self._metadata:         List[dict] = []   # parallel to the list returned by get_workpieces()

    def get_workpieces(self) -> list:
        if self._workpiece_service is None:
            return []
        all_meta   = self._workpiece_service.list_all()
        workpieces = []
        kept_meta  = []
        for meta in all_meta:
            wp = self._workpiece_service.load(meta["id"])
            if wp is not None:
                workpieces.append(wp)
                kept_meta.append(meta)
        self._metadata = kept_meta          # same order as returned workpieces
        _logger.info("Found %d workpieces", len(workpieces))
        return workpieces

    def get_latest_contours(self) -> list:
        if self._vision_service is None:
            return []
        raw    = self._vision_service.get_latest_contours()
        closed = [_close_contour(c) for c in raw]
        _logger.debug("get_latest_contours: %d contours (ensured closed)", len(closed))
        return closed

    def run_matching(self, workpieces: list, contours: list) -> Tuple[dict, int, List, List]:
        from src.engine.vision.implementation.VisionSystem.features.contour_matching import find_matching_workpieces
        result, no_matches, matched_contours = find_matching_workpieces(workpieces, contours)
        return (
            result,
            len(no_matches),
            [c.get() for c in matched_contours],
            [c.get() for c in no_matches],
        )

    def get_thumbnail(self, workpiece_index: int) -> Optional[bytes]:
        if workpiece_index < 0 or workpiece_index >= len(self._metadata):
            return None
        thumb_path = self._metadata[workpiece_index].get("thumbnail_path")
        if not thumb_path:
            return None
        try:
            with open(thumb_path, "rb") as f:
                return f.read()
        except Exception as exc:
            _logger.warning("Could not read thumbnail at %s: %s", thumb_path, exc)
            return None
