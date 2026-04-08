import logging
from typing import Dict, Any, Optional

import cv2
import math
import numpy as np

from contour_editor.persistence.data.editor_data_model import ContourEditorData
from contour_editor.models.segment import Segment

_KEY_CONTOUR       = "contour"
_KEY_SPRAY_PATTERN = "sprayPattern"

_logger = logging.getLogger(__name__)


class WorkpieceAdapter:
    LAYER_MAIN = "Main"  # ← contour_editor's actual name for the boundary layer
    LAYER_WORKPIECE = "Workpiece"
    LAYER_CONTOUR   = "Contour"
    LAYER_FILL      = "Fill"

    @classmethod
    def _ensure_complete_settings(cls, segment_settings: Optional[Dict[str, Any]],
                                  defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        base = dict(defaults) if defaults else {}
        if segment_settings:
            base.update({k: v for k, v in segment_settings.items() if v is not None})
        return base

    @classmethod
    def from_workpiece(cls, workpiece) -> ContourEditorData:
        main_contour   = workpiece.get_main_contour()
        main_settings  = workpiece.get_main_contour_settings()
        spray_contours = workpiece.get_spray_pattern_contours()
        spray_fills    = workpiece.get_spray_pattern_fills()
        layer_data = {
            cls.LAYER_WORKPIECE: [{"contour": main_contour, "settings": main_settings}],
            cls.LAYER_CONTOUR:   spray_contours,
            cls.LAYER_FILL:      spray_fills,
        }
        return ContourEditorData.from_legacy_format(cls._normalize_layer_data(layer_data))

    @classmethod
    def to_workpiece_data(cls, editor_data: ContourEditorData,
                          default_settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        result = {}

        workpiece_layer = (
                editor_data.get_layer(cls.LAYER_WORKPIECE)
                or editor_data.get_layer(cls.LAYER_MAIN)
        )
        contour_layer = editor_data.get_layer(cls.LAYER_CONTOUR)
        fill_layer = editor_data.get_layer(cls.LAYER_FILL)

        _logger.debug(
            "to_workpiece_data — Workpiece/Main segs=%d  Contour segs=%d  Fill segs=%d",
            len(workpiece_layer.segments) if workpiece_layer else 0,
            len(contour_layer.segments) if contour_layer else 0,
            len(fill_layer.segments) if fill_layer else 0,
        )

        if workpiece_layer and len(workpiece_layer.segments) > 0:
            # Explicit workpiece boundary drawn — use it directly
            result[_KEY_CONTOUR] = cls._segments_to_contour_array(workpiece_layer.segments)
            result.update(cls._ensure_complete_settings(
                workpiece_layer.segments[0].settings
                if hasattr(workpiece_layer.segments[0], "settings") else None
            ))
        else:
            # No Workpiece layer drawn — caller must validate this is not empty before saving
            result[_KEY_CONTOUR] = []

        spray_pattern = {"Contour": [], "Fill": []}

        if contour_layer:
            for seg in contour_layer.segments:
                arr = cls._segment_to_contour_array(seg)
                if arr is not None and len(arr) > 0:
                    spray_pattern["Contour"].append({
                        "contour": arr,
                        "settings": cls._ensure_complete_settings(
                            seg.settings if hasattr(seg, "settings") else None,
                            default_settings,
                        ),
                    })

        if fill_layer:
            for seg in fill_layer.segments:
                arr = cls._segment_to_contour_array(seg)
                if arr is not None and len(arr) > 0:
                    spray_pattern["Fill"].append({
                        "contour": arr,
                        "settings": cls._ensure_complete_settings(
                            seg.settings if hasattr(seg, "settings") else None,
                            default_settings,
                        ),
                    })

        result[_KEY_SPRAY_PATTERN] = spray_pattern
        return result

    @staticmethod
    def _segments_to_contour_array(segments) -> np.ndarray:
        if not segments:
            return np.zeros((0, 1, 2), dtype=np.float32)

        pts = []
        for i, seg in enumerate(segments):
            sampled = WorkpieceAdapter._sample_segment_points(seg)
            if not sampled:
                continue
            start = 1 if (i > 0 and pts) else 0
            pts.extend(sampled[start:])

        return (
            np.array(pts, dtype=np.float32).reshape(-1, 1, 2)
            if pts else np.zeros((0, 1, 2), dtype=np.float32)
        )

    @staticmethod
    def _normalize_layer_data(layer_data):
        normalized = {}
        for layer_name, entries in layer_data.items():
            contours, settings_list = [], []
            if not isinstance(entries, list):
                entries = [entries]
            for item in entries:
                if not isinstance(item, dict):
                    continue
                raw_contour = item.get("contour", [])
                if isinstance(raw_contour, str):
                    _logger.warning("_normalize_layer_data: skipping string contour in layer '%s'", layer_name)
                    continue
                try:
                    contour = np.array(raw_contour, dtype=np.float32)
                except (ValueError, TypeError) as exc:
                    _logger.warning("_normalize_layer_data: failed to parse contour in layer '%s': %s", layer_name, exc)
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
    @staticmethod
    def _segment_to_contour_array(segment: Segment) -> Optional[np.ndarray]:
        sampled = WorkpieceAdapter._sample_segment_points(segment)
        if not sampled:
            return None
        return np.array(sampled, dtype=np.float32).reshape(-1, 1, 2)

    @staticmethod
    def _sample_segment_points(segment: Segment, samples_per_curve: int = 12) -> list[list[float]]:
        points = getattr(segment, "points", None) or []
        controls = getattr(segment, "controls", None) or []
        if not points:
            return []

        sampled: list[list[float]] = [[float(points[0].x()), float(points[0].y())]]

        for i in range(1, len(points)):
            p0, p1 = points[i - 1], points[i]
            cp = controls[i - 1] if i - 1 < len(controls) else None
            if WorkpieceAdapter._is_effective_control_point(p0, cp, p1):
                for j in range(1, samples_per_curve + 1):
                    t = j / samples_per_curve
                    x = (1 - t) ** 2 * p0.x() + 2 * (1 - t) * t * cp.x() + t ** 2 * p1.x()
                    y = (1 - t) ** 2 * p0.y() + 2 * (1 - t) * t * cp.y() + t ** 2 * p1.y()
                    sampled.append([float(x), float(y)])
            else:
                sampled.append([float(p1.x()), float(p1.y())])

        return sampled

    @staticmethod
    def _is_effective_control_point(p0, cp, p1, threshold: float = 1.0) -> bool:
        if cp is None:
            return False
        dx, dy = p1.x() - p0.x(), p1.y() - p0.y()
        if dx == 0 and dy == 0:
            return False
        distance = abs(dy * cp.x() - dx * cp.y() + p1.x() * p0.y() - p1.y() * p0.x()) / math.hypot(dx, dy)
        return distance > threshold

    @classmethod
    def print_summary(cls, editor_data: ContourEditorData) -> None:
        stats = editor_data.get_statistics()
        _logger.debug("WorkpieceAdapter — layers=%d segments=%d points=%d",
                      stats["total_layers"], stats["total_segments"], stats["total_points"])

    @classmethod
    def from_raw(cls, raw: dict) -> ContourEditorData:
        raw_contour = raw.get("contour", [])

        layer_data = {
            cls.LAYER_MAIN: [{"contour": raw_contour, "settings": {}}],
            cls.LAYER_CONTOUR: raw.get("sprayPattern", {}).get("Contour", []),
            cls.LAYER_FILL: raw.get("sprayPattern", {}).get("Fill", []),
        }

        return ContourEditorData.from_legacy_format(cls._normalize_layer_data(layer_data))
