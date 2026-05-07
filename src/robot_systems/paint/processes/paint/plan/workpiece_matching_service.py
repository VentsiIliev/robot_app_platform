from __future__ import annotations

import copy
import logging
from typing import Callable, Optional, Iterable

import cv2
import numpy as np

from src.engine.vision.i_capture_snapshot_service import VisionCaptureSnapshot
from src.robot_systems.glue.domain.matching.i_matching_service import IMatchingService

_logger = logging.getLogger(__name__)

def pick_largest_contour(contours: Iterable) -> np.ndarray | None:
    """Return the contour with the largest valid area from a captured contour set."""
    best = None
    best_area = -1.0
    for contour in contours or []:
        try:
            arr = np.asarray(contour, dtype=np.float32)
            area = float(cv2.contourArea(arr))
        except Exception:
            continue
        if area > best_area:
            best_area = area
            best = arr
    return best

class PaintWorkpieceMatchingService(IMatchingService):
    """Adapt paint workpiece storage to the shared contour-matching interface."""
    def __init__(
        self,
        *,
        list_saved_workpieces_fn: Optional[Callable[[], list[dict]]] = None,
        load_saved_workpiece_fn: Optional[Callable[[str], Optional[dict]]] = None,
        run_matching_fn: Optional[Callable[[list, list], tuple]] = None,
        capture_snapshot_service=None,
    ) -> None:
        """Store repository, matching, and snapshot dependencies for paint matching."""
        self._list_saved_workpieces_fn = list_saved_workpieces_fn
        self._load_saved_workpiece_fn = load_saved_workpiece_fn
        self._run_matching_fn = run_matching_fn
        self._capture_snapshot_service = capture_snapshot_service
        self._last_snapshot: VisionCaptureSnapshot | None = None

    def can_match_saved_workpieces(self) -> bool:
        """Report whether all dependencies needed for saved-workpiece matching are available."""
        return (
            callable(self._list_saved_workpieces_fn)
            and callable(self._load_saved_workpiece_fn)
            and callable(self._run_matching_fn)
        )

    def match_saved_workpieces(self, contour) -> tuple[bool, dict | None, str]:
        """Match one captured contour against saved paint workpieces and return raw payload metadata."""
        if not self.can_match_saved_workpieces():
            return False, None, "Matching is not available in this editor."

        try:
            candidates = self._load_candidates()
            if not candidates:
                return False, None, "No saved workpieces available."

            result, no_match_count, _matched_contours, _unmatched_contours = self._run_matching_fn(
                candidates,
                [contour],
            )
            workpieces = list((result or {}).get("workpieces", []))
            confidences = list((result or {}).get("mlConfidences", []))
            if not workpieces:
                return False, None, f"No match found. Saved workpieces checked: {len(candidates)}"

            best = workpieces[0]
            raw = best.to_raw() if hasattr(best, "to_raw") else None
            if raw is None:
                return False, None, "Matched workpiece could not be converted."

            confidence = None
            if confidences:
                try:
                    confidence = float(confidences[0])
                except Exception:
                    confidence = None

            return True, {
                "raw": raw,
                "storage_id": getattr(best, "storage_id", None),
                "workpieceId": getattr(best, "workpieceId", "") or raw.get("workpieceId", ""),
                "name": getattr(best, "name", "") or raw.get("name", ""),
                "candidate_count": len(candidates),
                "no_match_count": int(no_match_count),
                "confidence": confidence,
            }, "Matched workpiece."
        except Exception as exc:
            _logger.exception("Paint workpiece matching failed")
            return False, None, str(exc)

    def run_matching(self):
        """Run full-scene matching using a fresh snapshot, mirroring the shared matching workflow."""
        if self._capture_snapshot_service is None:
            return {}, 0, [], []
        snapshot = self._capture_snapshot_service.capture_snapshot(source="matching")
        self._last_snapshot = snapshot
        contours = list(snapshot.contours or [])
        if len(contours) == 0:
            _logger.debug("No contours found -> Skipping matching")
            return {}, 0, [], []

        candidates = self._load_candidates()
        if len(candidates) == 0:
            _logger.debug("No workpieces found -> Skipping matching")
            return {}, 0, [], []

        return self._run_matching_fn(candidates, contours)

    def get_last_capture_snapshot(self):
        """Return the most recent snapshot captured during a matching run."""
        return self._last_snapshot

    def _load_candidates(self) -> list:
        """Load saved workpieces and wrap them in the contour-matcher adapter shape."""
        class _MatchableWorkpiece:
            def __init__(self, raw: dict, storage_id: str | None = None):
                self._raw = copy.deepcopy(raw or {})
                self.storage_id = storage_id
                self.workpieceId = self._raw.get("workpieceId", "")
                self.name = self._raw.get("name", "")
                self.contour = copy.deepcopy(self._raw.get("contour", []))
                self.sprayPattern = copy.deepcopy(self._raw.get("sprayPattern", {"Contour": [], "Fill": []}))
                self.pickupPoint = self._raw.get("pickupPoint")

            def get_main_contour(self):
                contour_entry = self.contour
                if isinstance(contour_entry, dict):
                    contour_points = contour_entry.get("contour", [])
                else:
                    contour_points = contour_entry or []
                return np.asarray(contour_points, dtype=np.float32)

            def get_spray_pattern_contours(self):
                return list((self.sprayPattern or {}).get("Contour", []))

            def get_spray_pattern_fills(self):
                return list((self.sprayPattern or {}).get("Fill", []))

            def to_raw(self) -> dict:
                raw = copy.deepcopy(self._raw)
                raw["contour"] = copy.deepcopy(self.contour)
                raw["sprayPattern"] = copy.deepcopy(self.sprayPattern)
                if self.pickupPoint is not None:
                    raw["pickupPoint"] = self.pickupPoint
                return raw

        stored = self._list_saved_workpieces_fn() or []
        candidates: list[_MatchableWorkpiece] = []
        for item in stored:
            storage_id = item.get("id")
            if not storage_id:
                continue
            raw = self._load_saved_workpiece_fn(storage_id)
            if not raw or not raw.get("contour"):
                continue
            candidates.append(_MatchableWorkpiece(raw, storage_id=storage_id))
        return candidates
