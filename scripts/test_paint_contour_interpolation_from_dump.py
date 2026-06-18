from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.robot_systems.paint.processes.paint.plan.paint_contour_interpolation import (
    PaintContourInterpolation,
    PaintContourInterpolationConfig,
    save_paint_contour_interpolation_debug_plot,
    show_paint_contour_interpolation_debug_plot,
)
from src.robot_systems.paint.processes.paint.plan.contour_utils import pick_largest_contour


DEFAULT_DEBUG_DIR = REPO_ROOT / "src" / "bootstrap" / "debug_plots"
DEFAULT_SECTION = "ORIGINAL_PLATFORM_PATH"


@dataclass(frozen=True)
class ContourPrimitive:
    kind: str
    start_index: int
    end_index: int
    start_xy: tuple[float, float]
    end_xy: tuple[float, float]
    length: float
    point_count: int
    center_xy: tuple[float, float] | None = None
    radius: float | None = None
    sweep_deg: float | None = None
    max_error: float | None = None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the experimental paint contour interpolation on a pivot dump path or live paint vision contour."
    )
    parser.add_argument(
        "dump",
        nargs="?",
        type=Path,
        help="Pivot trajectory dump. Defaults to the latest src/bootstrap/debug_plots/pivot_trajectory_*.txt.",
    )
    parser.add_argument(
        "--vision",
        action="store_true",
        help="Capture the latest contour from the paint vision system instead of reading a pivot dump.",
    )
    parser.add_argument(
        "--vision-wait-s",
        type=float,
        default=5.0,
        help="Maximum time to wait for live vision contours when --vision is used.",
    )
    parser.add_argument(
        "--vision-active-area",
        default="paint",
        help="Paint work-area id to activate before capturing contours.",
    )
    parser.add_argument(
        "--section",
        default=DEFAULT_SECTION,
        choices=("ORIGINAL_PLATFORM_PATH", "ROBOT_COMMAND_PATH"),
        help="Dump section to parse. Use ORIGINAL_PLATFORM_PATH for pre-pivot contour testing.",
    )
    parser.add_argument("--anchor-spacing-mm", type=float, default=1.0)
    parser.add_argument("--execution-spacing-mm", type=float, default=3.0)
    parser.add_argument("--straight-cleanup-distance-mm", type=float, default=0.35)
    parser.add_argument("--straight-cleanup-turn-deg", type=float, default=3.0)
    parser.add_argument("--straight-cleanup-passes", type=int, default=6)
    parser.add_argument("--sharp-boundary-deg", type=float, default=45.0)
    parser.add_argument("--rz-mode", default="path_tangent", choices=("path_tangent", "constant"))
    parser.add_argument(
        "--output",
        type=Path,
        help="Output PNG path when --save is used. Defaults next to dump with _paint_contour_interpolation.png suffix.",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Deprecated: plots are saved by default. Kept for compatibility.",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save the plot PNG.",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not show the plot window.",
    )
    parser.add_argument(
        "--decimate-primitives",
        action="store_true",
        help="Classify the cleaned contour into straight-line and circular-arc primitives.",
    )
    parser.add_argument(
        "--primitive-turn-deg",
        type=float,
        default=4.0,
        help="Minimum local turn angle used to mark a contour point as part of an arc.",
    )
    parser.add_argument(
        "--primitive-min-arc-points",
        type=int,
        default=3,
        help="Minimum number of curved points required for an arc primitive.",
    )
    args = parser.parse_args()

    units = "mm"
    source_label = ""
    dump_path: Path | None = None
    if args.vision:
        robot_path, contour_count = _capture_path_from_paint_vision(
            active_area=args.vision_active_area,
            wait_s=args.vision_wait_s,
        )
        units = "px"
        source_label = f"vision active_area={args.vision_active_area} contours={contour_count}"
    else:
        dump_path = args.dump or _latest_pivot_dump(DEFAULT_DEBUG_DIR)
        if dump_path is None:
            print(f"No pivot dumps found in {DEFAULT_DEBUG_DIR}", file=sys.stderr)
            return 2
        if not dump_path.exists():
            print(f"Dump does not exist: {dump_path}", file=sys.stderr)
            return 2

        robot_path = _parse_path_section(dump_path, args.section)
        if len(robot_path) < 2:
            print(f"Section {args.section!r} in {dump_path} has fewer than 2 points", file=sys.stderr)
            return 2
        source_label = f"dump={dump_path} section={args.section}"

    interpolation = PaintContourInterpolation(
        PaintContourInterpolationConfig(
            units=units,
            anchor_spacing_mm=args.anchor_spacing_mm,
            execution_spacing_mm=args.execution_spacing_mm,
            straight_cleanup_distance_mm=args.straight_cleanup_distance_mm,
            straight_cleanup_turn_deg=args.straight_cleanup_turn_deg,
            straight_cleanup_passes=args.straight_cleanup_passes,
            sharp_boundary_deg=args.sharp_boundary_deg,
            rz_mode=args.rz_mode,
        )
    )
    result = interpolation.build(robot_path)

    print(source_label)
    print(f"raw_points={len(result.raw_path)}")
    print(f"prepared_points={len(result.prepared_path)}")
    print(f"execution_points={len(result.execution_path)}")
    print(f"anchors={len(result.anchor_xy)}")
    print(f"cleaned_anchors={len(result.cleaned_anchor_xy)}")
    print(f"sharp_boundaries={len(result.sharp_boundary_xy)}")
    raw_rect = result.raw_min_rect
    final_rect = result.execution_min_rect
    print(
        "raw_min_rect="
        f"{raw_rect['width_mm']:.3f}x{raw_rect['height_mm']:.3f}{units} "
        f"angle={raw_rect['angle_deg']:.3f}deg"
    )
    print(
        "final_min_rect="
        f"{final_rect['width_mm']:.3f}x{final_rect['height_mm']:.3f}{units} "
        f"angle={final_rect['angle_deg']:.3f}deg"
    )
    print(
        "min_rect_delta="
        f"{final_rect['width_mm'] - raw_rect['width_mm']:+.3f}x"
        f"{final_rect['height_mm'] - raw_rect['height_mm']:+.3f}{units} "
        f"angle_delta={final_rect['angle_deg'] - raw_rect['angle_deg']:+.3f}deg"
    )
    primitives: list[ContourPrimitive] = []
    if args.decimate_primitives:
        primitive_source_xy = (
            np.asarray(result.cleaned_anchor_xy, dtype=float).reshape(-1, 2)
            if result.cleaned_anchor_xy else np.asarray(result.raw_path, dtype=float)[:, :2]
        )
        primitives = decimate_contour_primitives(
            primitive_source_xy,
            turn_threshold_deg=args.primitive_turn_deg,
            min_arc_points=args.primitive_min_arc_points,
        )
        _print_primitives(primitives, units)

    output_path = args.output or _default_output_path(dump_path, args.vision)
    if not args.no_save:
        save_paint_contour_interpolation_debug_plot(result, output_path)
        print(f"plot={output_path}")
        if primitives:
            primitive_output = output_path.with_name(f"{output_path.stem}_primitives{output_path.suffix}")
            save_primitive_debug_plot(result, primitives, primitive_output)
            print(f"primitive_plot={primitive_output}")
    if not args.no_show:
        show_paint_contour_interpolation_debug_plot(result)
        if primitives:
            show_primitive_debug_plot(result, primitives)
    return 0


def _latest_pivot_dump(debug_dir: Path) -> Path | None:
    dumps = sorted(debug_dir.glob("pivot_trajectory_*.txt"), key=lambda path: path.stat().st_mtime)
    return dumps[-1] if dumps else None


def _parse_path_section(dump_path: Path, section_name: str) -> list[list[float]]:
    target_header = f"[{section_name}]"
    points: list[list[float]] = []
    in_section = False

    for raw_line in dump_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            if in_section:
                break
            in_section = line == target_header
            continue
        if not in_section or line.startswith("count="):
            continue

        separator = line.find(":")
        if separator < 0:
            continue
        payload = line[separator + 1:].strip()
        if not payload.startswith("["):
            continue
        point = ast.literal_eval(payload)
        if isinstance(point, list) and len(point) >= 2:
            points.append([float(value) for value in point])

    return points


def _capture_path_from_paint_vision(*, active_area: str, wait_s: float) -> tuple[list[list[float]], int]:
    vision_service = _build_paint_vision_service(active_area=active_area)
    try:
        vision_service.start()
        deadline_s = time.monotonic() + max(0.1, float(wait_s))
        contours = []
        while time.monotonic() < deadline_s:
            contours = list(vision_service.get_latest_contours())
            if contours:
                break
            time.sleep(0.1)

        contour = pick_largest_contour(contours)
        if contour is None:
            raise RuntimeError(f"No valid vision contour found after {wait_s:.1f}s")
        return _contour_to_pixel_path(contour), len(contours)
    finally:
        vision_service.stop()


def _build_paint_vision_service(*, active_area: str):
    from src.engine.common_service_ids import CommonServiceID
    from src.engine.core.message_broker import MessageBroker
    from src.engine.repositories.settings_service_factory import build_from_specs
    from src.engine.work_areas.work_area_service import WorkAreaService
    from src.robot_systems.default_service_builders import build_vision_service
    from src.robot_systems.paint.paint_robot_system import PaintRobotSystem

    settings_service = build_from_specs(
        PaintRobotSystem.settings_specs,
        PaintRobotSystem.metadata.settings_root,
        PaintRobotSystem,
    )
    work_area_service = WorkAreaService(
        settings_service=settings_service,
        definitions=PaintRobotSystem.work_areas,
        default_active_area_id=PaintRobotSystem.default_active_work_area_id,
    )
    if active_area:
        work_area_service.set_active_area_id(active_area)

    ctx = SimpleNamespace(
        settings=settings_service,
        system_class=PaintRobotSystem,
        services={CommonServiceID.WORK_AREAS: work_area_service},
        messaging_service=MessageBroker(),
    )
    vision_service = build_vision_service(ctx)
    if active_area:
        vision_service.set_active_work_area(active_area)
    return vision_service


def _contour_to_pixel_path(contour: np.ndarray) -> list[list[float]]:
    points = np.asarray(contour, dtype=float).reshape(-1, 2)
    if len(points) >= 3 and np.linalg.norm(points[-1] - points[0]) > 1e-9:
        points = np.vstack([points, points[0]])
    return [[float(x), float(y), 0.0, 0.0, 0.0, 0.0] for x, y in points]


def decimate_contour_primitives(
    xy_points: np.ndarray,
    *,
    turn_threshold_deg: float,
    min_arc_points: int,
) -> list[ContourPrimitive]:
    points, closed = _open_contour_points(xy_points)
    if len(points) < 3:
        return []

    turns = np.asarray([
        _signed_turn_degrees(
            points[(index - 1) % len(points)],
            points[index],
            points[(index + 1) % len(points)],
        )
        for index in range(len(points))
    ])
    curved = np.abs(turns) >= max(0.1, float(turn_threshold_deg))
    curved = _dilate_circular_mask(curved, radius=1)
    clusters = _true_clusters(curved)

    min_arc_points = max(1, int(min_arc_points))
    arc_ranges: list[tuple[int, int]] = []
    for start, end in clusters:
        arc_indices = _circular_range(start, end, len(points))
        if len(arc_indices) >= min_arc_points:
            arc_ranges.append((start, end))

    if not arc_ranges:
        return [
            _make_line_primitive(points, 0, len(points) - 1, closed=closed)
        ]

    primitives: list[ContourPrimitive] = []
    for arc_idx, (arc_start, arc_end) in enumerate(arc_ranges):
        prev_arc_end = arc_ranges[arc_idx - 1][1]
        line_start = prev_arc_end
        line_end = arc_start
        if line_start != line_end:
            primitives.append(_make_line_primitive(points, line_start, line_end, closed=closed))
        primitives.append(_make_arc_primitive(points, arc_start, arc_end))

    if not closed and arc_ranges:
        first_start = arc_ranges[0][0]
        last_end = arc_ranges[-1][1]
        if first_start > 0:
            primitives.insert(0, _make_line_primitive(points, 0, first_start, closed=False))
        if last_end < len(points) - 1:
            primitives.append(_make_line_primitive(points, last_end, len(points) - 1, closed=False))

    return [primitive for primitive in primitives if primitive.length > 1e-9]


def save_primitive_debug_plot(
    result: PaintContourInterpolation,
    primitives: list[ContourPrimitive],
    output_path: str | Path,
) -> Path:
    import matplotlib.pyplot as plt

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig = _build_primitive_figure(result, primitives)
    fig.savefig(output, dpi=150)
    plt.close(fig)
    return output


def show_primitive_debug_plot(
    result: PaintContourInterpolation,
    primitives: list[ContourPrimitive],
) -> None:
    import matplotlib.pyplot as plt

    _build_primitive_figure(result, primitives)
    plt.show()


def _build_primitive_figure(result, primitives: list[ContourPrimitive]):
    import matplotlib.pyplot as plt

    raw = np.asarray(result.raw_path, dtype=float)
    cleaned = (
        np.asarray(result.cleaned_anchor_xy, dtype=float).reshape(-1, 2)
        if result.cleaned_anchor_xy else raw[:, :2]
    )
    fig, axis = plt.subplots(1, 1, figsize=(8, 6))
    axis.plot(raw[:, 0], raw[:, 1], color="0.75", linewidth=1.0, label="raw")
    axis.plot(cleaned[:, 0], cleaned[:, 1], "o", color="tab:blue", markersize=3, label="cleaned")
    colors = {"line": "tab:green", "arc": "tab:orange"}
    for index, primitive in enumerate(primitives, start=1):
        start = np.asarray(primitive.start_xy, dtype=float)
        end = np.asarray(primitive.end_xy, dtype=float)
        color = colors.get(primitive.kind, "tab:red")
        axis.plot([start[0], end[0]], [start[1], end[1]], "-", color=color, linewidth=2.0)
        mid = (start + end) * 0.5
        axis.text(mid[0], mid[1], f"{index}:{primitive.kind[0]}", color=color, fontsize=9)
        if primitive.kind == "arc" and primitive.center_xy is not None:
            center = np.asarray(primitive.center_xy, dtype=float)
            axis.scatter([center[0]], [center[1]], s=10, c=color, marker="+")
    line_count = sum(1 for primitive in primitives if primitive.kind == "line")
    arc_count = sum(1 for primitive in primitives if primitive.kind == "arc")
    axis.set_title(f"Contour Primitives: lines={line_count} arcs={arc_count}")
    axis.set_xlabel(f"X ({result.units})")
    axis.set_ylabel(f"Y ({result.units})")
    axis.set_aspect("equal", adjustable="box")
    axis.grid(True, alpha=0.5)
    axis.legend(loc="best")
    fig.tight_layout()
    return fig


def _print_primitives(primitives: list[ContourPrimitive], units: str) -> None:
    line_count = sum(1 for primitive in primitives if primitive.kind == "line")
    arc_count = sum(1 for primitive in primitives if primitive.kind == "arc")
    print(f"primitives={len(primitives)} lines={line_count} arcs={arc_count}")
    for index, primitive in enumerate(primitives, start=1):
        details = (
            f"{index:02d} {primitive.kind:<4} "
            f"idx={primitive.start_index}->{primitive.end_index} "
            f"pts={primitive.point_count} "
            f"start=({primitive.start_xy[0]:.3f},{primitive.start_xy[1]:.3f}) "
            f"end=({primitive.end_xy[0]:.3f},{primitive.end_xy[1]:.3f}) "
            f"length={primitive.length:.3f}{units}"
        )
        if primitive.kind == "arc":
            details += (
                f" radius={float(primitive.radius or 0.0):.3f}{units} "
                f"sweep={float(primitive.sweep_deg or 0.0):.1f}deg "
                f"fit_error={float(primitive.max_error or 0.0):.3f}{units}"
            )
        print(details)


def _open_contour_points(xy_points: np.ndarray) -> tuple[np.ndarray, bool]:
    points = np.asarray(xy_points, dtype=float)
    if points.ndim != 2 or points.shape[0] == 0 or points.shape[1] < 2:
        return np.empty((0, 2), dtype=float), False
    points = points[:, :2].copy()
    segment_lengths = np.linalg.norm(np.diff(points, axis=0), axis=1) if len(points) >= 2 else np.empty(0)
    if len(segment_lengths):
        keep = np.concatenate([[True], segment_lengths > 1e-9])
        points = points[keep]
    closed = len(points) >= 4 and float(np.linalg.norm(points[0] - points[-1])) <= 1e-6
    if closed:
        points = points[:-1]
    return points, closed


def _signed_turn_degrees(prev: np.ndarray, current: np.ndarray, nxt: np.ndarray) -> float:
    incoming = np.asarray(current, dtype=float) - np.asarray(prev, dtype=float)
    outgoing = np.asarray(nxt, dtype=float) - np.asarray(current, dtype=float)
    in_len = float(np.linalg.norm(incoming))
    out_len = float(np.linalg.norm(outgoing))
    if in_len <= 1e-9 or out_len <= 1e-9:
        return 0.0
    cross = float(incoming[0] * outgoing[1] - incoming[1] * outgoing[0])
    dot = float(np.dot(incoming, outgoing))
    return float(np.degrees(np.arctan2(cross, dot)))


def _dilate_circular_mask(mask: np.ndarray, *, radius: int) -> np.ndarray:
    mask = np.asarray(mask, dtype=bool)
    if len(mask) == 0 or radius <= 0:
        return mask
    output = mask.copy()
    for offset in range(1, radius + 1):
        output |= np.roll(mask, offset)
        output |= np.roll(mask, -offset)
    return output


def _true_clusters(mask: np.ndarray) -> list[tuple[int, int]]:
    mask = np.asarray(mask, dtype=bool)
    if len(mask) == 0 or not bool(np.any(mask)):
        return []
    if bool(np.all(mask)):
        return [(0, len(mask) - 1)]

    start_scan = int(np.flatnonzero(~mask)[0])
    clusters: list[tuple[int, int]] = []
    in_cluster = False
    cluster_start = 0
    last_true = 0
    for step in range(1, len(mask) + 1):
        index = (start_scan + step) % len(mask)
        if mask[index] and not in_cluster:
            in_cluster = True
            cluster_start = index
        if mask[index]:
            last_true = index
        if in_cluster and not mask[index]:
            clusters.append((cluster_start, last_true))
            in_cluster = False
    return clusters


def _circular_range(start: int, end: int, count: int) -> list[int]:
    if count <= 0:
        return []
    values = [start]
    while values[-1] != end:
        values.append((values[-1] + 1) % count)
        if len(values) > count:
            break
    return values


def _make_line_primitive(points: np.ndarray, start: int, end: int, *, closed: bool) -> ContourPrimitive:
    indices = _circular_range(start, end, len(points)) if closed else list(range(start, end + 1))
    segment_points = points[indices]
    length = _polyline_length(segment_points)
    return ContourPrimitive(
        kind="line",
        start_index=int(start),
        end_index=int(end),
        start_xy=(float(points[start, 0]), float(points[start, 1])),
        end_xy=(float(points[end, 0]), float(points[end, 1])),
        length=float(length),
        point_count=len(indices),
        max_error=_line_max_error(segment_points),
    )


def _make_arc_primitive(points: np.ndarray, start: int, end: int) -> ContourPrimitive:
    indices = _circular_range(start, end, len(points))
    segment_points = points[indices]
    center, radius, max_error = _fit_circle(segment_points)
    sweep_deg = _arc_sweep_degrees(segment_points, center)
    length = abs(np.radians(sweep_deg) * radius) if radius > 1e-9 else _polyline_length(segment_points)
    return ContourPrimitive(
        kind="arc",
        start_index=int(start),
        end_index=int(end),
        start_xy=(float(points[start, 0]), float(points[start, 1])),
        end_xy=(float(points[end, 0]), float(points[end, 1])),
        length=float(length),
        point_count=len(indices),
        center_xy=(float(center[0]), float(center[1])),
        radius=float(radius),
        sweep_deg=float(sweep_deg),
        max_error=float(max_error),
    )


def _polyline_length(points: np.ndarray) -> float:
    if len(points) < 2:
        return 0.0
    return float(np.sum(np.linalg.norm(np.diff(points, axis=0), axis=1)))


def _line_max_error(points: np.ndarray) -> float:
    if len(points) <= 2:
        return 0.0
    start = points[0]
    end = points[-1]
    line = end - start
    line_len = float(np.linalg.norm(line))
    if line_len <= 1e-9:
        return float(np.max(np.linalg.norm(points - start, axis=1)))
    distances = np.abs(np.cross(line, points - start)) / line_len
    return float(np.max(distances))


def _fit_circle(points: np.ndarray) -> tuple[np.ndarray, float, float]:
    if len(points) < 3:
        center = np.mean(points, axis=0)
        radius = float(np.mean(np.linalg.norm(points - center, axis=1))) if len(points) else 0.0
        return center, radius, 0.0
    x = points[:, 0]
    y = points[:, 1]
    system = np.column_stack([2.0 * x, 2.0 * y, np.ones(len(points))])
    target = x * x + y * y
    cx, cy, c = np.linalg.lstsq(system, target, rcond=None)[0]
    center = np.asarray([cx, cy], dtype=float)
    radius = float(np.sqrt(max(c + cx * cx + cy * cy, 0.0)))
    errors = np.abs(np.linalg.norm(points - center, axis=1) - radius)
    return center, radius, float(np.max(errors)) if len(errors) else 0.0


def _arc_sweep_degrees(points: np.ndarray, center: np.ndarray) -> float:
    vectors = points - center
    angles = np.unwrap(np.arctan2(vectors[:, 1], vectors[:, 0]))
    if len(angles) < 2:
        return 0.0
    return float(np.degrees(angles[-1] - angles[0]))


def _default_output_path(dump_path: Path | None, from_vision: bool) -> Path:
    if dump_path is not None:
        return dump_path.with_name(f"{dump_path.stem}_paint_contour_interpolation.png")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    prefix = "paint_vision_contour" if from_vision else "paint_contour"
    return DEFAULT_DEBUG_DIR / f"{prefix}_{timestamp}_paint_contour_interpolation.png"


if __name__ == "__main__":
    raise SystemExit(main())
