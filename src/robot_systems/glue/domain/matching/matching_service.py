import logging
import numpy as np
from typing import List, Tuple

from src.engine.vision.i_vision_service import IVisionService
from src.robot_systems.glue.domain.matching.i_matching_service import IMatchingService
from src.robot_systems.glue.domain.workpieces.service.i_workpiece_service import IWorkpieceService

_logger = logging.getLogger(__name__)


def _close_contour(contour: np.ndarray) -> np.ndarray:
    # np.array (not np.asarray) — forces a copy even when dtype already matches float32,
    # so callers cannot accidentally mutate _latest_contours through a shared-memory view.
    pts = np.array(contour, dtype=np.float32).reshape(-1, 2)
    if len(pts) >= 2 and not np.allclose(pts[0], pts[-1], atol=0.5):
        pts = np.vstack([pts, pts[0:1]])
    return pts.reshape(-1, 1, 2)


class MatchingService(IMatchingService):

    def __init__(self, vision_service: IVisionService, workpiece_service: IWorkpieceService):
        self._vision_service    = vision_service
        self._workpiece_service = workpiece_service

    def run_matching(self) -> Tuple[dict, int, List, List]:
        contours   = self._get_contours()
        # if no contours return early because the is nothing to match
        if len(contours) == 0:
            _logger.debug("No contours found -> Skipping matching")
            return {}, 0, [], []

        # no workpieces return early because there will be nothing to match against
        workpieces = self._load_workpieces()
        if len(workpieces) == 0:
            _logger.debug("No workpieces found -> Skipping matching")
            return {}, 0, [], []

        return self._vision_service.run_matching(workpieces, contours)

    def _load_workpieces(self) -> list:
        workpieces = []
        for meta in self._workpiece_service.list_all():
            wp = self._workpiece_service.load(meta["id"])
            if wp is not None:
                workpieces.append(wp)
        _logger.debug("_load_workpieces: %d loaded", len(workpieces))
        return workpieces

    def _get_contours(self) -> list:
        raw = self._vision_service.get_latest_contours()
        closed = [_close_contour(c) for c in raw]
        _logger.debug("_get_contours: %d contours", len(closed))
        return closed
