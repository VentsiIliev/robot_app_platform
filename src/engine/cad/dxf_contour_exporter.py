from __future__ import annotations

from dataclasses import dataclass
import logging
import math
import os
from typing import Iterable, Optional

import ezdxf
import numpy as np

from src.engine.vision.i_capture_snapshot_service import ICaptureSnapshotService

_logger = logging.getLogger(__name__)

Point2D = tuple[float, float]


@dataclass(frozen=True)
class DxfContourExportOptions:
    """Controls how detected vision contours are written into an AutoCAD DXF."""

    dxf_version: str = "R2010"
    units: str = "mm"
    layer_name: str = "OUTER_CONTOURS"
    close_contours: bool = True
    largest_only: bool = False
    min_area: float = 1.0
    postprocess_mode: str = "none"
    simplify_tolerance: float = 0.0
    smooth_window: int = 5
    smooth_iterations: int = 1
    normalize_to_origin: bool = False
    image_coordinates: bool = True
    invert_y_axis: bool = True
    include_metadata: bool = True


@dataclass(frozen=True)
class DxfContourExportResult:
    """Summary of one contour-to-DXF export."""

    path: str
    exported_count: int
    skipped_count: int
    bounds: tuple[float, float, float, float] | None


class DxfContourExporter:
    """Export contour arrays from the vision pipeline to AutoCAD-compatible DXF."""

    _UNIT_CODES = {
        "unitless": 0,
        "in": 1,
        "ft": 2,
        "mi": 3,
        "mm": 4,
        "cm": 5,
        "m": 6,
    }

    def __init__(
        self,
        snapshot_service: Optional[ICaptureSnapshotService] = None,
        options: DxfContourExportOptions | None = None,
    ) -> None:
        self._snapshot_service = snapshot_service
        self._options = options or DxfContourExportOptions()

    def export_latest(self, output_path: str, *, source: str = "dxf_contour_export") -> DxfContourExportResult:
        """Capture contours from the configured snapshot service and write them to DXF."""
        if self._snapshot_service is None:
            raise RuntimeError("Capture snapshot service is not available")

        snapshot = self._snapshot_service.capture_snapshot(source=source)
        image_height = _frame_height(snapshot.frame)
        return self.export_contours(
            snapshot.contours,
            output_path,
            image_height=image_height,
            source=source or snapshot.source,
        )

    def export_contours(
        self,
        contours: Iterable,
        output_path: str,
        *,
        image_height: float | None = None,
        source: str = "",
    ) -> DxfContourExportResult:
        """Write the provided contour list to a DXF file."""
        prepared, skipped = self._prepare_contours(contours, image_height=image_height)
        if self._options.largest_only and prepared:
            largest = max(prepared, key=_polygon_area_abs)
            skipped += len(prepared) - 1
            prepared = [largest]

        bounds = _bounds(prepared)
        if self._options.normalize_to_origin and bounds is not None:
            min_x, min_y, _, _ = bounds
            prepared = [
                [(float(x - min_x), float(y - min_y)) for x, y in contour]
                for contour in prepared
            ]
            bounds = _bounds(prepared)

        dxf_version = _normalize_dxf_version(self._options.dxf_version)
        doc = ezdxf.new(dxf_version)
        doc.header["$INSUNITS"] = self._UNIT_CODES.get(self._options.units.strip().lower(), 4)
        doc.header["$MEASUREMENT"] = 1
        doc.header["$LUNITS"] = 2
        doc.header["$AUNITS"] = 0

        if self._options.layer_name not in doc.layers:
            doc.layers.add(self._options.layer_name, color=7)

        modelspace = doc.modelspace()
        for contour in prepared:
            entity = _add_closed_polyline(
                modelspace,
                contour,
                close=self._options.close_contours,
                layer_name=self._options.layer_name,
                dxf_version=dxf_version,
            )
            if self._options.include_metadata:
                entity.dxf.color = 7
                entity.dxf.linetype = "CONTINUOUS"

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        doc.saveas(output_path)
        _logger.info(
            "Exported %d contour(s) to DXF: %s skipped=%d bounds=%s",
            len(prepared),
            output_path,
            skipped,
            bounds,
        )
        return DxfContourExportResult(
            path=output_path,
            exported_count=len(prepared),
            skipped_count=skipped,
            bounds=bounds,
        )

    def _prepare_contours(self, contours: Iterable, *, image_height: float | None) -> tuple[list[list[Point2D]], int]:
        prepared: list[list[Point2D]] = []
        skipped = 0
        for contour in contours or []:
            points = _contour_to_points(contour)
            if len(points) < 3:
                skipped += 1
                continue
            points = self._to_dxf_coordinates(points, image_height=image_height)
            points = _cleanup_points(points, tolerance=1e-9)
            if self._options.close_contours and points and not _is_closed(points):
                points.append(points[0])
            if len(points) < 4:
                skipped += 1
                continue
            if _polygon_area_abs(points) < float(self._options.min_area):
                skipped += 1
                continue
            points = _postprocess_contour(points, self._options)
            if len(points) < 4 or _polygon_area_abs(points) < float(self._options.min_area):
                skipped += 1
                continue
            prepared.append(points)
        return prepared, skipped

    def _to_dxf_coordinates(self, points: list[Point2D], *, image_height: float | None) -> list[Point2D]:
        if not self._options.image_coordinates:
            return [(float(x), float(y)) for x, y in points]

        if self._options.invert_y_axis and image_height is not None:
            return [(float(x), float(image_height - y)) for x, y in points]
        return [(float(x), float(y)) for x, y in points]


def export_latest_contours_to_dxf(
    snapshot_service: ICaptureSnapshotService,
    output_path: str,
    *,
    options: DxfContourExportOptions | None = None,
    source: str = "dxf_contour_export",
) -> DxfContourExportResult:
    """Capture the latest vision contours and write them to a DXF file."""
    return DxfContourExporter(snapshot_service, options=options).export_latest(output_path, source=source)


def export_contours_to_dxf(
    contours: Iterable,
    output_path: str,
    *,
    options: DxfContourExportOptions | None = None,
    image_height: float | None = None,
    source: str = "",
) -> DxfContourExportResult:
    """Write an explicit contour list to a DXF file."""
    return DxfContourExporter(options=options).export_contours(
        contours,
        output_path,
        image_height=image_height,
        source=source,
    )


def _frame_height(frame) -> float | None:
    if frame is None:
        return None
    try:
        return float(frame.shape[0])
    except Exception:
        return None


def _contour_to_points(contour) -> list[Point2D]:
    try:
        array = np.asarray(contour, dtype=float)
    except Exception:
        return []
    if array.size == 0:
        return []
    array = array.reshape(-1, array.shape[-1] if array.ndim > 1 else 1)
    if array.shape[1] < 2:
        return []
    return [(float(point[0]), float(point[1])) for point in array[:, :2]]


def _cleanup_points(points: list[Point2D], tolerance: float) -> list[Point2D]:
    if not points:
        return []
    cleaned = [points[0]]
    for point in points[1:]:
        if math.hypot(point[0] - cleaned[-1][0], point[1] - cleaned[-1][1]) <= tolerance:
            continue
        cleaned.append(point)
    return cleaned


def _is_closed(points: list[Point2D]) -> bool:
    return bool(points) and math.hypot(points[0][0] - points[-1][0], points[0][1] - points[-1][1]) <= 1e-9


def _polygon_area_abs(points: list[Point2D]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    pairs = zip(points, points[1:] if _is_closed(points) else points[1:] + points[:1])
    for first, second in pairs:
        area += first[0] * second[1] - second[0] * first[1]
    return abs(area) * 0.5


def _bounds(contours: list[list[Point2D]]) -> tuple[float, float, float, float] | None:
    points = [point for contour in contours for point in contour]
    if not points:
        return None
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _simplify_closed_contour(points: list[Point2D], tolerance: float) -> list[Point2D]:
    if len(points) < 4:
        return points
    closed = _is_closed(points)
    body = points[:-1] if closed else points
    simplified = _ramer_douglas_peucker(body, float(tolerance))
    if len(simplified) < 3:
        simplified = body
    if closed and simplified[0] != simplified[-1]:
        simplified.append(simplified[0])
    return simplified


def _postprocess_contour(points: list[Point2D], options: DxfContourExportOptions) -> list[Point2D]:
    mode = str(options.postprocess_mode or "none").strip().lower().replace(" ", "_")
    processed = list(points)

    if mode in {"moving_average", "moving_average_simplify", "smooth", "smooth_simplify"}:
        processed = _smooth_closed_contour(
            processed,
            window=int(options.smooth_window),
            iterations=int(options.smooth_iterations),
        )
    elif mode in {"chaikin", "chaikin_simplify"}:
        processed = _chaikin_closed_contour(processed, iterations=int(options.smooth_iterations))

    should_simplify = (
        float(options.simplify_tolerance) > 0.0
        and mode in {"none", "simplify", "moving_average_simplify", "smooth_simplify", "chaikin_simplify"}
    )
    if should_simplify:
        processed = _simplify_closed_contour(processed, float(options.simplify_tolerance))

    return _cleanup_points(processed, tolerance=1e-9)


def _smooth_closed_contour(points: list[Point2D], *, window: int, iterations: int) -> list[Point2D]:
    if len(points) < 4:
        return points
    closed = _is_closed(points)
    body = points[:-1] if closed else points
    if len(body) < 3:
        return points

    window = max(3, int(window))
    if window % 2 == 0:
        window += 1
    radius = window // 2

    smoothed = [(float(x), float(y)) for x, y in body]
    for _ in range(max(0, int(iterations))):
        next_points: list[Point2D] = []
        count = len(smoothed)
        for index in range(count):
            samples: list[Point2D] = []
            for offset in range(-radius, radius + 1):
                sample_index = index + offset
                if closed:
                    sample_index %= count
                else:
                    sample_index = min(max(sample_index, 0), count - 1)
                samples.append(smoothed[sample_index])
            next_points.append((
                sum(point[0] for point in samples) / len(samples),
                sum(point[1] for point in samples) / len(samples),
            ))
        smoothed = next_points

    if closed:
        smoothed.append(smoothed[0])
    return smoothed


def _chaikin_closed_contour(points: list[Point2D], *, iterations: int) -> list[Point2D]:
    if len(points) < 4:
        return points
    closed = _is_closed(points)
    body = points[:-1] if closed else points
    if len(body) < 3:
        return points

    refined = [(float(x), float(y)) for x, y in body]
    for _ in range(max(0, int(iterations))):
        next_points: list[Point2D] = []
        last_index = len(refined) - 1
        edge_count = len(refined) if closed else last_index
        for index in range(edge_count):
            first = refined[index]
            second = refined[(index + 1) % len(refined)]
            next_points.append((
                0.75 * first[0] + 0.25 * second[0],
                0.75 * first[1] + 0.25 * second[1],
            ))
            next_points.append((
                0.25 * first[0] + 0.75 * second[0],
                0.25 * first[1] + 0.75 * second[1],
            ))
        refined = next_points

    if closed:
        refined.append(refined[0])
    return refined


def _ramer_douglas_peucker(points: list[Point2D], tolerance: float) -> list[Point2D]:
    if len(points) <= 2:
        return list(points)
    start = points[0]
    end = points[-1]
    max_distance = -1.0
    max_index = 0
    for index, point in enumerate(points[1:-1], start=1):
        distance = _point_line_distance(point, start, end)
        if distance > max_distance:
            max_distance = distance
            max_index = index
    if max_distance > tolerance:
        left = _ramer_douglas_peucker(points[: max_index + 1], tolerance)
        right = _ramer_douglas_peucker(points[max_index:], tolerance)
        return left[:-1] + right
    return [start, end]


def _point_line_distance(point: Point2D, start: Point2D, end: Point2D) -> float:
    line_dx = end[0] - start[0]
    line_dy = end[1] - start[1]
    if abs(line_dx) <= 1e-12 and abs(line_dy) <= 1e-12:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    numerator = abs(line_dy * point[0] - line_dx * point[1] + end[0] * start[1] - end[1] * start[0])
    denominator = math.hypot(line_dx, line_dy)
    return numerator / denominator


def _normalize_dxf_version(version: str) -> str:
    normalized = str(version or "R2010").strip().upper()
    aliases = {
        "AC1009": "R12",
        "AC1015": "R2000",
        "AC1018": "R2004",
        "AC1021": "R2007",
        "AC1024": "R2010",
        "AC1027": "R2013",
        "AC1032": "R2018",
    }
    normalized = aliases.get(normalized, normalized)
    supported = {"R12", "R2000", "R2004", "R2007", "R2010", "R2013", "R2018"}
    return normalized if normalized in supported else "R2010"


def _add_closed_polyline(
    modelspace,
    contour: list[Point2D],
    *,
    close: bool,
    layer_name: str,
    dxf_version: str,
):
    points = contour[:-1] if _is_closed(contour) else contour
    if dxf_version == "R12":
        entity = modelspace.add_polyline2d(
            points,
            close=close,
            dxfattribs={"layer": layer_name},
        )
    else:
        entity = modelspace.add_lwpolyline(
            points,
            close=close,
            dxfattribs={"layer": layer_name},
        )
    return entity
