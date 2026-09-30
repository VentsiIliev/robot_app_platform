from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np


def save_matching_diagnostics(
    debug_dump_dir: str,
    captured_contour,
    candidates: list,
    *,
    matched: bool,
) -> Path:
    """Persist machine-readable and visual contour comparisons for one match attempt."""
    output_dir = Path(debug_dump_dir) / "workpiece_matching"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    stem = output_dir / f"match_{stamp}_{'matched' if matched else 'no_match'}"
    captured = _points(captured_contour)
    comparisons = []
    for index, candidate in enumerate(candidates, start=1):
        saved = _points(candidate.get_main_contour())
        comparisons.append(
            {
                "candidate_index": index,
                "storage_id": getattr(candidate, "storage_id", None),
                "workpiece_id": getattr(candidate, "workpieceId", None),
                "name": getattr(candidate, "name", None),
                "captured": _measure(captured),
                "saved": _measure(saved),
                "match_shapes_i1": _match_shapes(saved, captured, cv2.CONTOURS_MATCH_I1),
                "match_shapes_i2": _match_shapes(saved, captured, cv2.CONTOURS_MATCH_I2),
                "match_shapes_i3": _match_shapes(saved, captured, cv2.CONTOURS_MATCH_I3),
                "geometric_similarity_percent": _geometric_similarity(saved, captured),
                "saved_contour": saved.tolist(),
            }
        )
    payload = {
        "matched": bool(matched),
        "captured_contour": captured.tolist(),
        "captured": _measure(captured),
        "candidates": comparisons,
    }
    json_path = stem.with_suffix(".json")
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    cv2.imwrite(str(stem.with_suffix(".png")), _comparison_image(captured, candidates))
    return json_path


def _points(contour) -> np.ndarray:
    points = np.asarray(contour, dtype=np.float32)
    return points.reshape(-1, 2) if points.size else np.empty((0, 2), dtype=np.float32)


def _measure(points: np.ndarray) -> dict:
    contour = points.reshape(-1, 1, 2)
    if len(points) < 3:
        return {"point_count": len(points), "area": 0.0, "perimeter": 0.0}
    x, y, width, height = cv2.boundingRect(contour)
    return {
        "point_count": len(points),
        "area": float(cv2.contourArea(contour)),
        "perimeter": float(cv2.arcLength(contour, True)),
        "bbox": {"x": x, "y": y, "width": width, "height": height},
        "aspect_ratio": float(width / height) if height else None,
    }


def _match_shapes(first: np.ndarray, second: np.ndarray, method: int) -> float | None:
    if len(first) < 3 or len(second) < 3:
        return None
    return float(cv2.matchShapes(first.reshape(-1, 1, 2), second.reshape(-1, 1, 2), method, 0.0))


def _geometric_similarity(first: np.ndarray, second: np.ndarray) -> float | None:
    if len(first) < 5 or len(second) < 5:
        return None
    from src.engine.vision.implementation.VisionSystem.features.contour_matching.matching.strategies.geometric_matching_strategy import (
        GeometricMatchingStrategy,
    )

    return float(GeometricMatchingStrategy()._getSimilarity(first.copy(), second.copy()))


def _comparison_image(captured: np.ndarray, candidates: list) -> np.ndarray:
    panels = [_contour_panel(captured, (0, 180, 255), "CAPTURED")]
    for index, candidate in enumerate(candidates, start=1):
        label = f"SAVED {index}: {getattr(candidate, 'workpieceId', '')}"
        panels.append(_contour_panel(_points(candidate.get_main_contour()), (80, 220, 80), label))
    return np.hstack(panels)


def _contour_panel(points: np.ndarray, color: tuple[int, int, int], label: str) -> np.ndarray:
    size = 420
    margin = 35
    panel = np.full((size, size, 3), 28, dtype=np.uint8)
    cv2.putText(panel, label, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1, cv2.LINE_AA)
    if len(points) < 2:
        return panel
    minimum = points.min(axis=0)
    span = np.maximum(points.max(axis=0) - minimum, 1e-6)
    scale = min((size - 2 * margin) / float(span[0]), (size - 2 * margin) / float(span[1]))
    drawn = (points - minimum) * scale
    drawn += np.asarray([(size - span[0] * scale) / 2.0, (size - span[1] * scale) / 2.0])
    cv2.polylines(panel, [np.rint(drawn).astype(np.int32)], True, color, 2, cv2.LINE_AA)
    return panel
