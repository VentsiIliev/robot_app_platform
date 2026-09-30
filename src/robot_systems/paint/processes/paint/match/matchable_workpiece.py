from __future__ import annotations

import copy

import numpy as np


class MatchableWorkpiece:
    """Adapter shape expected by the shared contour matching service."""

    def __init__(self, raw: dict, storage_id: str | None = None):
        self._raw = copy.deepcopy(raw or {})
        self.storage_id = storage_id
        self.workpieceId = self._raw.get("workpieceId", "")
        self.name = self._raw.get("name", "")
        self.contour = copy.deepcopy(self._raw.get("contour", []))
        matching_contour = self._raw.get("matchingContour")
        self.matchingContour = copy.deepcopy(
            self.contour if matching_contour is None else matching_contour
        )
        self.sprayPattern = copy.deepcopy(self._raw.get("sprayPattern", {"Contour": [], "Fill": []}))
        self.pickupPoint = self._raw.get("pickupPoint")

    def get_main_contour(self):
        # New workpieces preserve the untouched camera contour explicitly.
        # Legacy payloads fall back to the editable Workpiece contour.
        contour_entry = self.matchingContour
        if isinstance(contour_entry, dict):
            contour_points = contour_entry.get("contour", [])
        else:
            contour_points = contour_entry
        if contour_points is None:
            contour_points = []
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
