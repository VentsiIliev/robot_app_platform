from __future__ import annotations

import copy
import logging
from typing import Callable

import numpy as np

from src.engine.cad import import_dxf_to_workpiece_data
from src.robot_systems.paint.processes.paint.dxf_image_placement import map_raw_workpiece_mm_to_image
from src.robot_systems.paint.processes.paint.workpiece_alignment import (
    DXF_ALIGNMENT_STRATEGY_RIGID,
    align_raw_workpiece_to_contour,
    _normalize_contour_points,
)

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
        dxf_alignment_strategy: str = DXF_ALIGNMENT_STRATEGY_RIGID,
        dxf_max_scale_deviation: float = 0.03,
    ) -> None:
        """Store matching hooks and the transformer needed for DXF placement."""
        self._can_match_fn = can_match_fn
        self._match_workpiece_fn = match_workpiece_fn
        self._transformer = transformer
        self._dxf_alignment_strategy = str(dxf_alignment_strategy or DXF_ALIGNMENT_STRATEGY_RIGID).strip().lower()
        self._dxf_max_scale_deviation = float(dxf_max_scale_deviation)

    def prepare_workpiece(self, captured_contour, frame) -> tuple[dict, str]:
        """Choose between a matched saved workpiece and a raw captured-contour fallback."""
        _logger.info(
            "[PREP] start captured=%s can_match=%s",
            _describe_contour(_normalize_contour_points(captured_contour)),
            bool(self._can_match_fn()),
        )
        if self._can_match_fn():
            ok, payload, _ = self._match_workpiece_fn(captured_contour)
            if ok and payload:
                _logger.info(
                    "[PREP] matched workpiece id=%s name=%s",
                    str(payload.get("workpieceId") or ""),
                    str(payload.get("name") or ""),
                )
                raw = self._build_matched_workpiece_raw(payload, captured_contour, frame)
                if raw is not None:
                    label = payload.get("workpieceId") or payload.get("name") or "matched workpiece"
                    return raw, f"Executed {label}"

        _logger.info("[PREP] fallback to captured contour")
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
            _logger.info(
                "[PREP] branch=dxf workpiece_id=%s dxf_path=%s frame_size=(%.1f, %.1f) strategy=%s max_scale_deviation=%.6f raw=%s",
                str(matched_raw.get("workpieceId") or matched_raw.get("name") or ""),
                dxf_path,
                float(image_w),
                float(image_h),
                self._dxf_alignment_strategy,
                float(self._dxf_max_scale_deviation),
                _describe_contour(_normalize_contour_points(captured_contour)),
            )
            dxf_raw = import_dxf_to_workpiece_data(dxf_path)
            placed = map_raw_workpiece_mm_to_image(
                dxf_raw,
                image_w,
                image_h,
                self._transformer,
            )
            _logger.info(
                "[PREP] dxf placed main=%s",
                _describe_contour(_extract_points_for_log(placed)),
            )
            aligned = align_raw_workpiece_to_contour(
                placed,
                captured_contour,
                strategy=self._dxf_alignment_strategy,
                max_scale_deviation=self._dxf_max_scale_deviation,
            )
            for key, value in matched_raw.items():
                if key in {"contour", "sprayPattern"}:
                    continue
                aligned[key] = copy.deepcopy(value)
            aligned["dxfPath"] = dxf_path
            aligned.setdefault("sprayPattern", {"Contour": [], "Fill": []})
            return aligned

        if matched_raw.get("contour"):
            _logger.info(
                "[PREP] branch=contour workpiece_id=%s source=%s captured=%s",
                str(matched_raw.get("workpieceId") or matched_raw.get("name") or ""),
                _describe_contour(_extract_points_for_log(matched_raw)),
                _describe_contour(_normalize_contour_points(captured_contour)),
            )
            return align_raw_workpiece_to_contour(
                matched_raw,
                captured_contour,
                strategy=self._dxf_alignment_strategy,
                max_scale_deviation=0.0,
                reference_scale_override=1.0,
            )

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


def _extract_points_for_log(raw: dict) -> np.ndarray:
    contour = (raw or {}).get("contour")
    if isinstance(contour, dict):
        contour = contour.get("contour")
    try:
        array = np.asarray(contour if contour is not None else [], dtype=np.float64)
    except Exception:
        return np.empty((0, 2), dtype=np.float64)
    if array.ndim == 3 and array.shape[1] == 1:
        array = array[:, 0, :]
    if array.ndim != 2 or array.shape[1] < 2:
        points: list[list[float]] = []
        iterable = contour if contour is not None else []
        for point in iterable:
            try:
                flat = np.asarray(point, dtype=np.float64).reshape(-1)
            except Exception:
                continue
            if flat.size >= 2:
                points.append([float(flat[0]), float(flat[1])])
        return np.asarray(points, dtype=np.float64) if points else np.empty((0, 2), dtype=np.float64)
    return array[:, :2]


def _describe_contour(points: np.ndarray) -> str:
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[0] == 0 or points.shape[1] < 2:
        return "count=0"
    pts = points[:, :2]
    mins = np.min(pts, axis=0)
    maxs = np.max(pts, axis=0)
    centroid = np.mean(pts, axis=0)
    area = 0.0
    if len(pts) >= 3:
        x = pts[:, 0]
        y = pts[:, 1]
        area = 0.5 * float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))
    return (
        f"count={len(pts)} "
        f"centroid=({float(centroid[0]):.3f}, {float(centroid[1]):.3f}) "
        f"bbox=({float(mins[0]):.3f}, {float(mins[1]):.3f})-({float(maxs[0]):.3f}, {float(maxs[1]):.3f}) "
        f"area={float(area):.3f}"
    )
