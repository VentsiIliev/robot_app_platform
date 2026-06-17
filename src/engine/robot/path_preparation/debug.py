import os
from datetime import datetime

import cv2
import numpy as np
import logging

from src.engine.robot.path_preparation.geometry import _orient_contour_like_original

_logger = logging.getLogger(__name__)

def _save_contour_canonicalization_steps_debug_plot(
        original_points: np.ndarray,
        pickup_point: tuple[float, float] | None = None,
        *,
        debug_dir: str = "/home/ilv/Desktop/robot_app_platform/src/bootstrap/debug_plots",
) -> None:
    """Save each contour canonicalization step used before pixel-to-mm conversion."""
    try:
        original = np.asarray(original_points, dtype=np.float64)
        if original.ndim != 2 or original.shape[1] < 2 or len(original) < 2:
            return

        stages: list[tuple[str, np.ndarray]] = [("0 raw input", original[:, :2].copy())]
        contour = original[:, :2].copy()

        removed_close = False
        if len(contour) >= 2 and np.linalg.norm(contour[0] - contour[-1]) <= 1e-6:
            contour = contour[:-1]
            removed_close = True
        stages.append(("1 remove duplicate close" if removed_close else "1 no duplicate close", contour.copy()))

        if len(contour) < 3:
            return

        original_open = contour.copy()
        signed_area = 0.5 * float(
            np.dot(contour[:, 0], np.roll(contour[:, 1], -1))
            - np.dot(contour[:, 1], np.roll(contour[:, 0], -1))
        )
        reversed_winding = signed_area > 0.0
        if reversed_winding:
            contour = contour[::-1].copy()
        stages.append(("2 reverse winding" if reversed_winding else "2 keep winding", contour.copy()))

        start_index = int(np.lexsort((contour[:, 0], contour[:, 1]))[0])
        contour = np.roll(contour, -start_index, axis=0)
        stages.append((f"3 roll start idx {start_index}", contour.copy()))

        oriented = _orient_contour_like_original(contour, original_open)
        orientation_changed = (
                len(oriented) == len(contour)
                and np.linalg.norm(oriented[1] - contour[1]) > 1e-6
        )
        contour = oriented
        stages.append(("4 orient like original" if orientation_changed else "4 keep orientation", contour.copy()))

        closed = False
        if len(contour) >= 3 and np.linalg.norm(contour[0] - contour[-1]) > 1e-9:
            contour = np.vstack([contour, contour[:1]])
            closed = True
        stages.append(("5 explicit close" if closed else "5 already closed", contour.copy()))

        all_points = np.vstack([stage[:, :2] for _, stage in stages if len(stage)])
        min_xy = np.min(all_points, axis=0)
        max_xy = np.max(all_points, axis=0)
        span = np.maximum(max_xy - min_xy, np.array([1.0, 1.0], dtype=np.float64))

        cols = 3
        rows = int(np.ceil(len(stages) / cols))
        cell_w = 420
        cell_h = 340
        pad = 34.0
        canvas = np.full((rows * cell_h, cols * cell_w, 3), 255, dtype=np.uint8)

        def _to_canvas(points: np.ndarray, col: int, row: int) -> np.ndarray:
            pts = np.asarray(points[:, :2], dtype=np.float64)
            scale = min((cell_w - 2.0 * pad) / float(span[0]), (cell_h - 2.0 * pad) / float(span[1]))
            mapped = (pts - min_xy) * scale + pad
            mapped[:, 1] = (span[1] * scale + 2.0 * pad) - mapped[:, 1]
            mapped[:, 0] += col * cell_w
            mapped[:, 1] += row * cell_h
            return np.rint(mapped).astype(np.int32).reshape(-1, 1, 2)

        colors = [
            (190, 30, 30),
            (30, 130, 30),
            (30, 80, 200),
            (200, 110, 20),
            (150, 40, 180),
            (30, 160, 180),
        ]
        for index, (title, points) in enumerate(stages):
            row = index // cols
            col = index % cols
            x0 = col * cell_w
            y0 = row * cell_h
            cv2.rectangle(canvas, (x0, y0), (x0 + cell_w - 1, y0 + cell_h - 1), (220, 220, 220), 1)
            cv2.putText(canvas, title, (x0 + 12, y0 + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (20, 20, 20), 1, cv2.LINE_AA)
            cv2.putText(
                canvas,
                f"pts={len(points)} bbox=({float(np.ptp(points[:, 0])):.1f}, {float(np.ptp(points[:, 1])):.1f})",
                (x0 + 12, y0 + 48),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (80, 80, 80),
                1,
                cv2.LINE_AA,
            )
            if len(points) < 2:
                continue
            canvas_points = _to_canvas(points, col, row)
            cv2.polylines(canvas, [canvas_points], False, colors[index % len(colors)], 2)
            cv2.circle(canvas, tuple(canvas_points[0, 0]), 6, (0, 160, 0), -1)
            cv2.circle(canvas, tuple(canvas_points[-1, 0]), 6, (0, 0, 220), -1)
            if pickup_point is not None:
                pickup_canvas = _to_canvas(
                    np.asarray([[float(pickup_point[0]), float(pickup_point[1])]], dtype=np.float64), col, row)
                cv2.drawMarker(canvas, tuple(pickup_canvas[0, 0]), (200, 0, 200), cv2.MARKER_CROSS, 15, 2)

        os.makedirs(debug_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(debug_dir, f"contour_canonicalization_steps_{timestamp}.png")
        cv2.imwrite(path, canvas)
        _logger.info("[EXECUTE] Saved contour canonicalization step plot to: %s", path)
    except Exception:
        _logger.debug("[EXECUTE] Failed to save contour canonicalization step plot", exc_info=True)


def _save_contour_reordering_debug_plot(
        original_points: np.ndarray,
        reordered_points: np.ndarray,
        pickup_point: tuple[float, float] | None = None,
        *,
        debug_dir: str = "/home/ilv/Desktop/robot_app_platform/src/bootstrap/debug_plots",
) -> None:
    """Save an overlay image showing original vs canonicalized contour ordering."""
    try:
        original = np.asarray(original_points, dtype=np.float64)
        reordered = np.asarray(reordered_points, dtype=np.float64)
        if original.ndim != 2 or reordered.ndim != 2 or len(original) < 2 or len(reordered) < 2:
            return

        all_points = np.vstack([original[:, :2], reordered[:, :2]])
        min_xy = np.min(all_points, axis=0)
        max_xy = np.max(all_points, axis=0)
        pad = 30.0
        span = np.maximum(max_xy - min_xy, np.array([1.0, 1.0], dtype=np.float64))
        scale = min(900.0 / float(span[0]), 700.0 / float(span[1]))

        def _to_canvas(points: np.ndarray) -> np.ndarray:
            pts = np.asarray(points[:, :2], dtype=np.float64)
            pts = (pts - min_xy) * scale + pad
            pts[:, 1] = (span[1] * scale + 2.0 * pad) - pts[:, 1]
            return np.rint(pts).astype(np.int32).reshape(-1, 1, 2)

        canvas_w = int(np.ceil(span[0] * scale + 2.0 * pad))
        canvas_h = int(np.ceil(span[1] * scale + 2.0 * pad))
        canvas = np.full((max(canvas_h, 100), max(canvas_w, 100), 3), 255, dtype=np.uint8)

        original_canvas = _to_canvas(original)
        reordered_canvas = _to_canvas(reordered)

        cv2.polylines(canvas, [original_canvas], True, (0, 0, 255), 2)
        cv2.polylines(canvas, [reordered_canvas], True, (0, 180, 0), 2)
        cv2.circle(canvas, tuple(original_canvas[0, 0]), 6, (0, 0, 180), -1)
        cv2.circle(canvas, tuple(reordered_canvas[0, 0]), 6, (0, 180, 0), -1)
        cv2.putText(canvas, "Original start", tuple(original_canvas[0, 0] + np.array([8, -8])),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 180), 1, cv2.LINE_AA)
        cv2.putText(canvas, "Reordered start", tuple(reordered_canvas[0, 0] + np.array([8, 18])),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 120, 0), 1, cv2.LINE_AA)
        if pickup_point is not None:
            pickup_canvas = _to_canvas(np.asarray([[float(pickup_point[0]), float(pickup_point[1])]], dtype=np.float64))
            px, py = tuple(pickup_canvas[0, 0])
            cv2.drawMarker(canvas, (int(px), int(py)), (200, 0, 200), cv2.MARKER_CROSS, 18, 2)
            cv2.putText(
                canvas,
                f"Pickup centroid ({float(pickup_point[0]):.1f}, {float(pickup_point[1]):.1f})",
                (int(px) + 8, int(py) - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (140, 0, 140),
                1,
                cv2.LINE_AA,
            )

        os.makedirs(debug_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(debug_dir, f"contour_reorder_debug_{timestamp}.png")
        cv2.imwrite(path, canvas)
        _logger.info("[EXECUTE] Saved contour reorder debug plot to: %s", path)
    except Exception:
        _logger.debug("[EXECUTE] Failed to save contour reorder debug plot", exc_info=True)
