from __future__ import annotations

import copy
import logging
from typing import Callable

import numpy as np

from src.engine.cad import import_dxf_to_workpiece_data
from src.robot_systems.paint.processes.paint.dxf_image_placement import map_raw_workpiece_mm_to_image
from src.robot_systems.paint.processes.paint.workpiece_alignment import (
    align_raw_workpiece_to_contour, _normalize_contour_points)

_logger = logging.getLogger(__name__)

def contour_to_workpiece_raw(
    contour: np.ndarray,
    *,
    workpiece_id: str = "captured",
    name: str = "Captured contour",
    height_mm: float = 0.0,
) -> dict:
    """Wrap a captured contour into the raw workpiece payload shape used by paint execution."""
    normalized = _normalize_contour_points(contour)
    return {
        "workpieceId": str(workpiece_id),
        "name": str(name),
        "height_mm": float(height_mm),
        "contour": [
            [[float(point[0]), float(point[1])]]
            for point in normalized
        ],
        "sprayPattern": {"Contour": [], "Fill": []},
    }

class PaintWorkpiecePreparationService:
    """Prepare the raw workpiece payload that paint production should execute."""
    def __init__(
        self,
        *,
        can_match_fn: Callable[[], bool],
        match_workpiece_fn: Callable,
        transformer=None,
    ) -> None:
        """Store matching hooks and the transformer needed for DXF placement."""
        self._can_match_fn = can_match_fn
        self._match_workpiece_fn = match_workpiece_fn
        self._transformer = transformer

    def prepare_workpiece(self, captured_contour, frame) -> tuple[dict, str]:
        """Choose between a matched saved workpiece and a raw captured-contour fallback."""
        if self._can_match_fn():
            ok, payload, _ = self._match_workpiece_fn(captured_contour)
            if ok and payload:
                raw = self._build_matched_workpiece_raw(payload, captured_contour, frame)
                if raw is not None:
                    label = payload.get("workpieceId") or payload.get("name") or "matched workpiece"
                    return raw, f"Executed {label}"

        return (
            contour_to_workpiece_raw(captured_contour, workpiece_id="captured", name="Captured contour"),
            "Executed captured contour",
        )

    def _build_matched_workpiece_raw(self, payload: dict, captured_contour, frame) -> dict | None:
        """Build an executable raw workpiece from matched storage data and the live contour."""
        matched_raw = copy.deepcopy(payload.get("raw") or {})
        if not matched_raw:
            return None

        dxf_path = str(matched_raw.get("dxfPath", "") or "").strip()
        if dxf_path:
            image_h, image_w = self._resolve_frame_size(frame)
            dxf_raw = import_dxf_to_workpiece_data(dxf_path)
            placed = map_raw_workpiece_mm_to_image(
                dxf_raw,
                image_w,
                image_h,
                self._transformer,
            )
            aligned = align_raw_workpiece_to_contour(placed, captured_contour)
            for key, value in matched_raw.items():
                if key in {"contour", "sprayPattern"}:
                    continue
                aligned[key] = copy.deepcopy(value)
            aligned["dxfPath"] = dxf_path
            aligned.setdefault("sprayPattern", {"Contour": [], "Fill": []})
            return aligned

        if matched_raw.get("contour"):
            return align_raw_workpiece_to_contour(matched_raw, captured_contour)

        return None

    @staticmethod
    def _resolve_frame_size(frame) -> tuple[float, float]:
        """Extract image height and width from a captured frame with safe defaults."""
        if frame is None:
            return 720.0, 1280.0
        try:
            return float(frame.shape[0]), float(frame.shape[1])
        except Exception:
            _logger.debug("Failed to read frame shape for DXF placement", exc_info=True)
            return 720.0, 1280.0
