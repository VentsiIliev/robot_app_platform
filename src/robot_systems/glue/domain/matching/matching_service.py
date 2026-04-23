import logging
import numpy as np
from typing import List, Tuple

from src.engine.vision.i_capture_snapshot_service import ICaptureSnapshotService, VisionCaptureSnapshot
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

    def __init__(
        self,
        vision_service: IVisionService,
        workpiece_service: IWorkpieceService,
        capture_snapshot_service: ICaptureSnapshotService,
    ):
        self._vision_service    = vision_service
        self._workpiece_service = workpiece_service
        self._capture_snapshot_service = capture_snapshot_service
        self._last_snapshot: VisionCaptureSnapshot | None = None

    def can_match_saved_workpieces(self) -> bool:
        return (
            self._vision_service is not None
            and self._workpiece_service is not None
            and self._capture_snapshot_service is not None
        )

    def match_saved_workpieces(self, contour) -> Tuple[bool, dict | None, str]:
        if not self.can_match_saved_workpieces():
            return False, None, "Matching is not available."

        workpieces = self._load_workpieces()
        if len(workpieces) == 0:
            return False, None, "No saved workpieces available."

        try:
            result, no_match_count, _matched, _unmatched = self._vision_service.run_matching(
                workpieces,
                [contour],
            )
        except Exception as exc:
            _logger.exception("match_saved_workpieces failed")
            return False, None, str(exc)

        matched_workpieces = list((result or {}).get("workpieces", []))
        confidences = list((result or {}).get("mlConfidences", []))
        if not matched_workpieces:
            return False, None, f"No match found. Saved workpieces checked: {len(workpieces)}"

        best = matched_workpieces[0]
        confidence = None
        if confidences:
            try:
                confidence = float(confidences[0])
            except Exception:
                confidence = None

        raw = None
        serializer = getattr(type(best), "serialize", None)
        if callable(serializer):
            try:
                raw = serializer(best)
            except Exception:
                raw = None
        if raw is None and hasattr(best, "to_dict"):
            try:
                raw = best.to_dict()
            except Exception:
                raw = None

        payload = {
            "raw": raw,
            "storage_id": getattr(best, "storage_id", None),
            "workpieceId": getattr(best, "workpieceId", ""),
            "name": getattr(best, "name", ""),
            "candidate_count": len(workpieces),
            "no_match_count": int(no_match_count),
            "confidence": confidence,
        }
        return True, payload, "Matched workpiece."

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
                try:
                    setattr(wp, "storage_id", meta.get("id"))
                except Exception:
                    pass
                workpieces.append(wp)
        _logger.debug("_load_workpieces: %d loaded", len(workpieces))
        return workpieces

    def _get_contours(self) -> list:
        snapshot = self._capture_snapshot_service.capture_snapshot(source="matching")
        self._last_snapshot = snapshot
        raw = snapshot.contours
        closed = [_close_contour(c) for c in raw]
        _logger.debug("_get_contours: %d contours", len(closed))
        return closed

    def get_last_capture_snapshot(self) -> VisionCaptureSnapshot | None:
        return self._last_snapshot
