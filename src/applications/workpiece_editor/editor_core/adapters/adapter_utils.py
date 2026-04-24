from __future__ import annotations

import logging
import math
from typing import Any, Dict, Optional

import numpy as np
from contour_editor import LayerConfigRegistry
from contour_editor.models.segment import Segment
from contour_editor.persistence.data.editor_data_model import ContourEditorData

_logger = logging.getLogger(__name__)


def workpiece_layer_name() -> str:
    return LayerConfigRegistry.get_instance().get_config().name_for_role("workpiece")


def contour_layer_name() -> str:
    return LayerConfigRegistry.get_instance().get_config().name_for_role("contour")


def fill_layer_name() -> str:
    return LayerConfigRegistry.get_instance().get_config().name_for_role("fill")


def ensure_complete_settings(
    segment_settings: Optional[Dict[str, Any]],
    defaults: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    base = dict(defaults) if defaults else {}
    if segment_settings:
        base.update({k: v for k, v in segment_settings.items() if v is not None})
    return base


def unwrap_raw_contour_entry(raw_contour):
    if isinstance(raw_contour, dict):
        return raw_contour.get("contour", [])
    return raw_contour


def segments_to_contour_array(segments) -> np.ndarray:
    if not segments:
        return np.zeros((0, 1, 2), dtype=np.float32)

    pts = []
    for i, seg in enumerate(segments):
        sampled = sample_segment_points(seg)
        if not sampled:
            continue
        start = 1 if (i > 0 and pts) else 0
        pts.extend(sampled[start:])

    return (
        np.array(pts, dtype=np.float32).reshape(-1, 1, 2)
        if pts else np.zeros((0, 1, 2), dtype=np.float32)
    )


def normalize_layer_data(layer_data):
    normalized = {}
    for layer_name, entries in layer_data.items():
        contours, settings_list = [], []
        if not isinstance(entries, list):
            entries = [entries]
        for item in entries:
            if not isinstance(item, dict):
                continue
            raw_contour = unwrap_raw_contour_entry(item.get("contour", []))
            if isinstance(raw_contour, str):
                _logger.warning("normalize_layer_data: skipping string contour in layer '%s'", layer_name)
                continue
            try:
                contour = np.array(raw_contour, dtype=np.float32)
            except (ValueError, TypeError) as exc:
                _logger.warning("normalize_layer_data: failed to parse contour in layer '%s': %s", layer_name, exc)
                continue
            if contour.size == 0:
                continue
            if contour.ndim == 2 and contour.shape[1] == 2:
                contour = contour.reshape(-1, 1, 2)
            elif not (contour.ndim == 3 and contour.shape[1] == 1):
                contour = contour.reshape(-1, 1, 2)
            contours.append(contour)
            settings_list.append(item.get("settings", {}))
        normalized[layer_name] = {"contours": contours, "settings": settings_list}
    return normalized


def segment_to_contour_array(segment: Segment) -> Optional[np.ndarray]:
    sampled = sample_segment_points(segment)
    if not sampled:
        return None
    return np.array(sampled, dtype=np.float32).reshape(-1, 1, 2)


def sample_segment_points(segment: Segment, samples_per_curve: int = 12) -> list[list[float]]:
    points = getattr(segment, "points", None) or []
    controls = getattr(segment, "controls", None) or []
    if not points:
        return []

    sampled: list[list[float]] = [[float(points[0].x()), float(points[0].y())]]

    for i in range(1, len(points)):
        p0, p1 = points[i - 1], points[i]
        cp = controls[i - 1] if i - 1 < len(controls) else None
        if is_effective_control_point(p0, cp, p1):
            for j in range(1, samples_per_curve + 1):
                t = j / samples_per_curve
                x = (1 - t) ** 2 * p0.x() + 2 * (1 - t) * t * cp.x() + t ** 2 * p1.x()
                y = (1 - t) ** 2 * p0.y() + 2 * (1 - t) * t * cp.y() + t ** 2 * p1.y()
                sampled.append([float(x), float(y)])
        else:
            sampled.append([float(p1.x()), float(p1.y())])

    return sampled


def is_effective_control_point(p0, cp, p1, threshold: float = 1.0) -> bool:
    if cp is None:
        return False
    dx, dy = p1.x() - p0.x(), p1.y() - p0.y()
    if dx == 0 and dy == 0:
        return False
    distance = abs(dy * cp.x() - dx * cp.y() + p1.x() * p0.y() - p1.y() * p0.x()) / math.hypot(dx, dy)
    return distance > threshold


def print_summary(editor_data: ContourEditorData) -> None:
    stats = editor_data.get_statistics()
    _logger.debug(
        "WorkpieceAdapter — layers=%d segments=%d points=%d",
        stats["total_layers"],
        stats["total_segments"],
        stats["total_points"],
    )
