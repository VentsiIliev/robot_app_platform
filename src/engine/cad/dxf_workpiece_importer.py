from __future__ import annotations

from dataclasses import dataclass
import logging
import math
from typing import Iterable

import ezdxf
from ezdxf import recover

_logger = logging.getLogger(__name__)


Point2D = tuple[float, float]


@dataclass(frozen=True)
class DxfImportOptions:
    flatten_distance: float = 0.5
    connect_tolerance: float = 0.5
    normalize_to_origin: bool = True
    close_open_loops: bool = True
    min_closed_points: int = 3


@dataclass
class _PathSequence:
    points: list[Point2D]
    closed: bool = False


class DxfWorkpieceImporter:
    """Vector DXF importer that produces workpiece-editor-compatible data.

    Unlike the legacy PLVision DXF converter, this importer never rasterizes the
    drawing or runs contour detection. It extracts geometry directly from DXF
    entities and stitches open segments into closed paths where possible.
    """

    def __init__(self, options: DxfImportOptions | None = None) -> None:
        self._options = options or DxfImportOptions()

    def import_file(self, dxf_path: str) -> dict:
        doc = self._read_dxf(dxf_path)
        msp = doc.modelspace()
        sequences = self._collect_sequences(msp)
        closed_paths = self._build_closed_paths(sequences)
        if not closed_paths:
            raise ValueError(f"No closed workpiece contour found in DXF: {dxf_path}")

        contour = max(closed_paths, key=lambda path: _polygon_area_abs(path))
        contour = _normalize_path(contour, self._options.normalize_to_origin)
        return {
            "contour": _to_contour_array(contour),
            "sprayPattern": {
                "Contour": [],
                "Fill": [],
            },
        }

    def import_file_to_editor_data(self, dxf_path: str):
        from src.applications.workpiece_editor.editor_core.adapters.workpiece_adapter import WorkpieceAdapter

        return WorkpieceAdapter.from_raw(self.import_file(dxf_path))

    def _read_dxf(self, dxf_path: str):
        try:
            return ezdxf.readfile(dxf_path)
        except Exception as exc:
            _logger.warning("Standard DXF read failed for %s: %s", dxf_path, exc)
            try:
                doc, auditor = recover.readfile(dxf_path)
                if auditor.has_errors:
                    _logger.warning(
                        "DXF recover opened %s with %d errors and %d fixes",
                        dxf_path,
                        len(auditor.errors),
                        len(auditor.fixes),
                    )
                return doc
            except Exception as recover_exc:
                _logger.warning("DXF recover failed for %s: %s", dxf_path, recover_exc)
                sequences = _raw_parse_dxf_sequences(dxf_path, self._options.connect_tolerance)
                if not sequences:
                    raise recover_exc
                return _RawParsedDocument(sequences)

    def _collect_sequences(self, entities: Iterable) -> list[_PathSequence]:
        sequences: list[_PathSequence] = []
        for entity in entities:
            if isinstance(entity, _PathSequence):
                sequences.append(entity)
                continue
            sequences.extend(self._entity_to_sequences(entity))
        return [seq for seq in sequences if len(seq.points) >= 2]

    def _entity_to_sequences(self, entity) -> list[_PathSequence]:
        dxftype = entity.dxftype()
        if dxftype == "INSERT":
            sequences: list[_PathSequence] = []
            for virtual in entity.virtual_entities():
                sequences.extend(self._entity_to_sequences(virtual))
            return sequences

        if dxftype == "LINE":
            start = entity.dxf.start
            end = entity.dxf.end
            return [_PathSequence(points=[(float(start.x), float(start.y)), (float(end.x), float(end.y))], closed=False)]

        if dxftype == "LWPOLYLINE":
            points = [(float(x), float(y)) for x, y, *_ in entity.get_points()]
            return [_PathSequence(points=points, closed=bool(entity.closed))]

        if dxftype == "POLYLINE":
            points = [(float(p.x), float(p.y)) for p in entity.points_in_wcs()]
            return [_PathSequence(points=points, closed=bool(entity.is_closed))]

        if dxftype in {"ARC", "CIRCLE", "ELLIPSE", "SPLINE"}:
            points = [(float(v.x), float(v.y)) for v in entity.flattening(self._options.flatten_distance)]
            return [_PathSequence(points=points, closed=(dxftype == "CIRCLE"))]

        _logger.debug("Skipping unsupported DXF entity type: %s", dxftype)
        return []

    def _build_closed_paths(self, sequences: list[_PathSequence]) -> list[list[Point2D]]:
        tolerance = self._options.connect_tolerance
        paths = [_cleanup_points(seq.points, tolerance) for seq in sequences if len(seq.points) >= 2]
        closed_flags = [seq.closed for seq in sequences if len(seq.points) >= 2]

        changed = True
        while changed:
            changed = False
            for i in range(len(paths)):
                if i >= len(paths):
                    break
                if closed_flags[i]:
                    continue
                for j in range(i + 1, len(paths)):
                    merged = _merge_paths(paths[i], paths[j], tolerance)
                    if merged is None:
                        continue
                    paths[i] = _cleanup_points(merged, tolerance)
                    closed_flags[i] = closed_flags[i] or closed_flags[j]
                    del paths[j]
                    del closed_flags[j]
                    changed = True
                    break
                if changed:
                    break

        closed_paths: list[list[Point2D]] = []
        for path, initially_closed in zip(paths, closed_flags):
            if len(path) < 2:
                continue
            if initially_closed or (
                self._options.close_open_loops and _points_close(path[0], path[-1], tolerance)
            ):
                normalized = list(path)
                if not _points_close(normalized[0], normalized[-1], tolerance):
                    normalized.append(normalized[0])
                normalized = _cleanup_points(normalized, tolerance, keep_closed=True)
                if len(normalized) >= self._options.min_closed_points + 1:
                    closed_paths.append(normalized)
        return closed_paths


class _RawParsedDocument:
    def __init__(self, sequences: list[_PathSequence]) -> None:
        self._sequences = sequences

    def modelspace(self):
        return self._sequences


def import_dxf_to_workpiece_data(
    dxf_path: str,
    *,
    options: DxfImportOptions | None = None,
) -> dict:
    return DxfWorkpieceImporter(options=options).import_file(dxf_path)


def import_dxf_to_editor_data(
    dxf_path: str,
    *,
    options: DxfImportOptions | None = None,
):
    return DxfWorkpieceImporter(options=options).import_file_to_editor_data(dxf_path)


def _to_contour_array(path: list[Point2D]) -> list[list[list[float]]]:
    return [[[float(x), float(y)]] for x, y in path]


def _normalize_path(path: list[Point2D], normalize_to_origin: bool) -> list[Point2D]:
    if not path:
        return []
    normalized = list(path)
    if not normalize_to_origin:
        return normalized
    min_x = min(point[0] for point in normalized)
    min_y = min(point[1] for point in normalized)
    return [(float(x - min_x), float(y - min_y)) for x, y in normalized]


def _cleanup_points(
    points: list[Point2D],
    tolerance: float,
    *,
    keep_closed: bool = False,
) -> list[Point2D]:
    if not points:
        return []
    cleaned = [points[0]]
    for point in points[1:]:
        if _points_close(cleaned[-1], point, tolerance):
            continue
        cleaned.append(point)
    if keep_closed and len(cleaned) >= 2 and not _points_close(cleaned[0], cleaned[-1], tolerance):
        cleaned.append(cleaned[0])
    return cleaned


def _merge_paths(path_a: list[Point2D], path_b: list[Point2D], tolerance: float) -> list[Point2D] | None:
    a0, a1 = path_a[0], path_a[-1]
    b0, b1 = path_b[0], path_b[-1]
    if _points_close(a1, b0, tolerance):
        return path_a + path_b[1:]
    if _points_close(a1, b1, tolerance):
        return path_a + list(reversed(path_b[:-1]))
    if _points_close(a0, b1, tolerance):
        return path_b + path_a[1:]
    if _points_close(a0, b0, tolerance):
        return list(reversed(path_b)) + path_a[1:]
    return None


def _points_close(a: Point2D, b: Point2D, tolerance: float) -> bool:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1])) <= float(tolerance)


def _polygon_area_abs(path: list[Point2D]) -> float:
    if len(path) < 3:
        return 0.0
    area = 0.0
    for first, second in zip(path, path[1:]):
        area += float(first[0]) * float(second[1]) - float(second[0]) * float(first[1])
    return abs(area) * 0.5


def _raw_parse_dxf_sequences(dxf_path: str, tolerance: float) -> list[_PathSequence]:
    pairs = _read_dxf_tag_pairs(dxf_path)
    if not pairs:
        return []

    sequences: list[_PathSequence] = []
    in_entities = False
    active_type: str | None = None
    entity_tags: list[tuple[int, str]] = []
    polyline_vertices: list[Point2D] = []
    polyline_closed = False

    def flush_entity() -> None:
        nonlocal active_type, entity_tags
        if active_type is None:
            entity_tags = []
            return
        if active_type == "LWPOLYLINE":
            sequence = _parse_raw_lwpolyline(entity_tags, tolerance)
            if sequence is not None:
                sequences.append(sequence)
        elif active_type == "LINE":
            sequence = _parse_raw_line(entity_tags, tolerance)
            if sequence is not None:
                sequences.append(sequence)
        entity_tags = []
        active_type = None

    def flush_polyline() -> None:
        nonlocal polyline_vertices, polyline_closed
        if len(polyline_vertices) >= 2:
            sequences.append(_PathSequence(points=_cleanup_points(polyline_vertices, tolerance), closed=polyline_closed))
        polyline_vertices = []
        polyline_closed = False

    index = 0
    while index < len(pairs):
        code, value = pairs[index]
        if code == 0 and value == "SECTION":
            next_code, next_value = pairs[index + 1] if index + 1 < len(pairs) else (-1, "")
            if next_code == 2:
                in_entities = next_value == "ENTITIES"
                if not in_entities:
                    flush_entity()
                    flush_polyline()
            index += 2
            continue
        if not in_entities:
            index += 1
            continue
        if code == 0 and value == "ENDSEC":
            flush_entity()
            flush_polyline()
            in_entities = False
            index += 1
            continue
        if code != 0:
            if active_type is not None:
                entity_tags.append((code, value))
            index += 1
            continue

        if value == "POLYLINE":
            flush_entity()
            flush_polyline()
            active_type = None
            entity_tags = []
            polyline_vertices = []
            polyline_closed = False
            index += 1
            while index < len(pairs):
                sub_code, sub_value = pairs[index]
                if sub_code == 0 and sub_value == "VERTEX":
                    vertex_tags: list[tuple[int, str]] = []
                    index += 1
                    while index < len(pairs):
                        v_code, v_value = pairs[index]
                        if v_code == 0:
                            break
                        vertex_tags.append((v_code, v_value))
                        index += 1
                    vertex = _parse_raw_vertex(vertex_tags)
                    if vertex is not None:
                        polyline_vertices.append(vertex)
                    continue
                if sub_code == 0 and sub_value == "SEQEND":
                    flush_polyline()
                    index += 1
                    break
                if sub_code != 0:
                    if sub_code == 70:
                        polyline_closed = (_safe_int(sub_value) & 1) != 0
                    index += 1
                    continue
                break
            continue

        flush_entity()
        active_type = value
        entity_tags = []
        index += 1

    flush_entity()
    flush_polyline()
    return [seq for seq in sequences if len(seq.points) >= 2]


def _read_dxf_tag_pairs(dxf_path: str) -> list[tuple[int, str]]:
    with open(dxf_path, "r", encoding="utf-8", errors="ignore") as handle:
        lines = [line.rstrip("\r\n") for line in handle]
    if len(lines) < 2:
        return []

    pairs: list[tuple[int, str]] = []
    for index in range(0, len(lines) - 1, 2):
        try:
            code = int(lines[index].strip())
        except ValueError:
            continue
        pairs.append((code, lines[index + 1].strip()))
    return pairs


def _parse_raw_lwpolyline(tags: list[tuple[int, str]], tolerance: float) -> _PathSequence | None:
    points: list[Point2D] = []
    current_x: float | None = None
    closed = False
    for code, value in tags:
        if code == 70:
            closed = (_safe_int(value) & 1) != 0
        elif code == 10:
            current_x = _safe_float(value)
        elif code == 20 and current_x is not None:
            points.append((current_x, _safe_float(value)))
            current_x = None
    cleaned = _cleanup_points(points, tolerance)
    if len(cleaned) < 2:
        return None
    return _PathSequence(points=cleaned, closed=closed)


def _parse_raw_line(tags: list[tuple[int, str]], tolerance: float) -> _PathSequence | None:
    start_x = start_y = end_x = end_y = None
    for code, value in tags:
        if code == 10:
            start_x = _safe_float(value)
        elif code == 20:
            start_y = _safe_float(value)
        elif code == 11:
            end_x = _safe_float(value)
        elif code == 21:
            end_y = _safe_float(value)
    if None in {start_x, start_y, end_x, end_y}:
        return None
    points = _cleanup_points([(start_x, start_y), (end_x, end_y)], tolerance)
    if len(points) < 2:
        return None
    return _PathSequence(points=points, closed=False)


def _parse_raw_vertex(tags: list[tuple[int, str]]) -> Point2D | None:
    x = y = None
    for code, value in tags:
        if code == 10:
            x = _safe_float(value)
        elif code == 20:
            y = _safe_float(value)
    if x is None or y is None:
        return None
    return (x, y)


def _safe_float(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
