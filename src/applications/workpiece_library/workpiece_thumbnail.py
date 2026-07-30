import logging
from typing import List, Optional, Tuple

import cv2
import numpy as np

_logger = logging.getLogger(__name__)

_CANVAS = 300
_MARGIN = 20
_BG_FILL = (220, 230, 255)
_OUTLINE = (50, 50, 200)
_SPRAY_LINE = (50, 150, 50)
_FILL_COLOR = (150, 220, 150)


def generate_thumbnail_bytes(raw: dict, size: int = _CANVAS) -> Optional[bytes]:
    try:
        main_pts = _points_from(raw.get("contour", []))
        spray_pat = raw.get("sprayPattern", {})
        spray_c_segs = [
            _points_from(entry.get("contour", []))
            for entry in spray_pat.get("Contour", [])
        ]
        spray_f_segs = [
            _points_from(entry.get("contour", []))
            for entry in spray_pat.get("Fill", [])
        ]

        all_pts = (
            main_pts
            + [point for segment in spray_c_segs for point in segment]
            + [point for segment in spray_f_segs for point in segment]
        )
        if len(all_pts) < 2:
            return None

        canvas = np.full((size, size, 3), 255, dtype=np.uint8)
        xf, yf = _fit_transform(all_pts, size)

        if len(main_pts) >= 3:
            pts = _to_cv(main_pts, xf, yf)
            cv2.fillPoly(canvas, [pts], _BG_FILL)
            cv2.polylines(
                canvas,
                [pts],
                isClosed=True,
                color=_OUTLINE,
                thickness=2,
            )
        elif len(main_pts) == 2:
            pts = _to_cv(main_pts, xf, yf)
            cv2.polylines(
                canvas,
                [pts],
                isClosed=False,
                color=_OUTLINE,
                thickness=2,
            )

        for segment in spray_f_segs:
            if len(segment) >= 3:
                pts = _to_cv(segment, xf, yf)
                cv2.fillPoly(canvas, [pts], _FILL_COLOR)
                cv2.polylines(
                    canvas,
                    [pts],
                    isClosed=True,
                    color=_SPRAY_LINE,
                    thickness=1,
                )

        for segment in spray_c_segs:
            if len(segment) >= 2:
                pts = _to_cv(segment, xf, yf)
                cv2.polylines(
                    canvas,
                    [pts],
                    isClosed=False,
                    color=_SPRAY_LINE,
                    thickness=2,
                )

        ok, buffer = cv2.imencode(".png", canvas)
        return buffer.tobytes() if ok else None
    except Exception as exc:
        _logger.warning(
            "generate_thumbnail_bytes failed: %s",
            exc,
            exc_info=True,
        )
        return None


def _points_from(data) -> List[Tuple[float, float]]:
    if isinstance(data, dict):
        return _extract_points(data.get("contour", []))
    if not isinstance(data, list) or not data:
        return []
    if isinstance(data[0], dict):
        points = []
        for entry in data:
            points.extend(_extract_points(entry.get("contour", [])))
        return points
    return _extract_points(data)


def _extract_points(data) -> List[Tuple[float, float]]:
    points = []
    for item in data:
        point = item
        while isinstance(point, list) and len(point) == 1:
            point = point[0]
        if isinstance(point, (list, tuple)) and len(point) >= 2:
            try:
                points.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError):
                pass
    return points


def _fit_transform(pts: List[Tuple[float, float]], size: int):
    xs = [point[0] for point in pts]
    ys = [point[1] for point in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y)
    scale = (size - 2 * _MARGIN) / span if span > 0 else 1.0
    off_x = (
        _MARGIN
        - min_x * scale
        + (size - 2 * _MARGIN - (max_x - min_x) * scale) / 2
    )
    off_y = (
        _MARGIN
        - min_y * scale
        + (size - 2 * _MARGIN - (max_y - min_y) * scale) / 2
    )
    return (scale, off_x), (scale, off_y)


def _to_cv(pts: List[Tuple[float, float]], xf, yf) -> np.ndarray:
    scale_x, offset_x = xf
    scale_y, offset_y = yf
    return np.array(
        [
            [
                int(x * scale_x + offset_x),
                int(y * scale_y + offset_y),
            ]
            for x, y in pts
        ],
        dtype=np.int32,
    ).reshape(-1, 1, 2)
