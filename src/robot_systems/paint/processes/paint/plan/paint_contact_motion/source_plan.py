from __future__ import annotations

import logging

import numpy as np

from src.engine.robot.path_preparation import WorkpieceExecutionPlan
from src.robot_systems.paint.processes.paint.config import PaintSimulationConfig

_logger = logging.getLogger(__name__)

_NON_PAINT_CLEARANCE_MM = 5.0
_CLEARANCE_RAMP_MM = 5.0
_SELECTION_MATCH_TOLERANCE_MM = 2.0


def build_paint_contact_source_plan(
    plan: WorkpieceExecutionPlan,
    contact_config: PaintSimulationConfig,
) -> WorkpieceExecutionPlan:
    """Attach the final paint contact source contour to each execution job.

    Path preparation owns pixel-to-mm conversion, contour smoothing, and final
    sampling. Paint contact planning consumes that final execution path directly
    as contact source geometry; it does not resample or simplify the contour.

    Compatibility keys using the old pivot terminology are kept until all
    downstream readers are migrated.
    """
    if not plan.execution_jobs:
        return plan

    prepared_jobs: list[dict] = []
    total_contact_source_points = 0
    for job_index, job in enumerate(plan.execution_jobs, start=1):
        prepared_job = dict(job)
        source_path = [list(point) for point in (job.get("execution_path") or [])]
        selection_paths = list(job.get("process_selection_paths_mm") or [])
        clearance_profile: list[float] = []
        if source_path and selection_paths:
            source_path, clearance_profile = _trim_and_profile_selected_interval(
                source_path,
                selection_paths,
                cut_moved_outside_selection=bool(job.get("paint_selection_cut_applied")),
            )
        contact_source_path = [list(point) for point in source_path]
        min_spacing_mm, mean_spacing_mm, max_spacing_mm = _planar_spacing_stats(
            contact_source_path,
            contact_config.source_planar_coordinate_indices,
        )
        pipeline = {
            "source": "execution_path",
            "source_points": len(source_path),
            "contact_source_points": len(contact_source_path),
            "pivot_source_points": len(contact_source_path),
            "min_spacing_mm": min_spacing_mm,
            "mean_spacing_mm": mean_spacing_mm,
            "max_spacing_mm": max_spacing_mm,
        }
        prepared_job["paint_contact_source_path"] = contact_source_path
        prepared_job["paint_contact_pipeline"] = pipeline
        prepared_job["pivot_source_path"] = contact_source_path
        prepared_job["pivot_pipeline"] = pipeline
        prepared_job["paint_clearance_profile_mm"] = clearance_profile
        total_contact_source_points += len(contact_source_path)
        if source_path:
            _logger.info(
                "[PAINT_CONTACT_SOURCE] job=%d final_contour_source=%s source_pts=%d contact_source_pts=%d actual_spacing[min=%.3f mean=%.3f max=%.3f]mm",
                job_index,
                pipeline["source"],
                len(source_path),
                len(contact_source_path),
                min_spacing_mm,
                mean_spacing_mm,
                max_spacing_mm,
            )
        prepared_jobs.append(prepared_job)

    return WorkpieceExecutionPlan(
        workpiece=plan.workpiece,
        raw_paths=plan.raw_paths,
        prepared_paths=plan.prepared_paths,
        curve_paths=plan.curve_paths,
        sampled_paths=plan.sampled_paths,
        execution_jobs=prepared_jobs,
        total_spline_pts=total_contact_source_points or plan.total_spline_pts,
        raw_pixel_paths=plan.raw_pixel_paths,
        raw_homography_paths=plan.raw_homography_paths,
    )


def _planar_spacing_stats(
    path: list[list[float]],
    planar_indices: tuple[int, int],
) -> tuple[float, float, float]:
    """Return min/mean/max spacing in the active source plane."""
    import numpy as np

    if len(path) < 2:
        return 0.0, 0.0, 0.0
    planar_i, planar_j = planar_indices
    required_index = max(planar_i, planar_j)
    if any(len(pose) <= required_index for pose in path):
        return 0.0, 0.0, 0.0
    points = np.asarray([[float(pose[planar_i]), float(pose[planar_j])] for pose in path], dtype=float)
    lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
    positive = lengths[lengths > 1e-9]
    if len(positive) == 0:
        return 0.0, 0.0, 0.0
    return float(np.min(positive)), float(np.mean(positive)), float(np.max(positive))


prepare_pivot_source_plan = build_paint_contact_source_plan


def _trim_and_profile_selected_interval(
    source_path: list[list[float]],
    selection_paths: list[list[list[float]]],
    *,
    cut_moved_outside_selection: bool = False,
) -> tuple[list[list[float]], list[float]]:
    """Trim after the last selected span and add clearance through internal gaps."""
    source_xy = np.asarray(source_path, dtype=float)[:, :2]
    selected = np.zeros(len(source_xy), dtype=bool)
    for selection in selection_paths:
        selected_xy = np.asarray(selection, dtype=float)
        if selected_xy.ndim != 2 or len(selected_xy) < 2:
            continue
        selected |= _points_near_polyline(
            source_xy,
            selected_xy[:, :2],
            tolerance_mm=_SELECTION_MATCH_TOLERANCE_MM,
        )
    if cut_moved_outside_selection and selected[0] and selected[-1] and np.any(~selected):
        # Closed resampling repeats the first point at the end, and the matching
        # tolerance can also mark a few adjacent tail samples. The cut was
        # deliberately placed inside an unselected run, so this terminal run is
        # closure bleed rather than a second paint segment.
        last_unselected = int(np.flatnonzero(~selected)[-1])
        selected[last_unselected + 1:] = False
        if np.allclose(source_xy[0], source_xy[-1], atol=1e-6):
            source_path = source_path[:-1]
            source_xy = source_xy[:-1]
            selected = selected[:-1]
    indices = np.flatnonzero(selected)
    if len(indices) == 0:
        _logger.warning("[PAINT_SELECTION] No selected segment matched the prepared contour; using full contact")
        return [list(point) for point in source_path], [0.0] * len(source_path)

    first = int(indices[0])
    last = int(indices[-1])
    trimmed_path = [list(point) for point in source_path[first:last + 1]]
    trimmed_selected = selected[first:last + 1]
    distances = _cumulative_distances(np.asarray(trimmed_path, dtype=float)[:, :2])
    profile = np.where(trimmed_selected, 0.0, _NON_PAINT_CLEARANCE_MM)

    # Ramp over physical contour distance on both sides of every contact edge.
    contact_distances = distances[trimmed_selected]
    if len(contact_distances):
        nearest_contact = np.min(np.abs(distances[:, None] - contact_distances[None, :]), axis=1)
        ramp = np.clip(nearest_contact / _CLEARANCE_RAMP_MM, 0.0, 1.0)
        profile = np.where(trimmed_selected, 0.0, _NON_PAINT_CLEARANCE_MM * ramp)

    _logger.info(
        "[PAINT_SELECTION] source_pts=%d trimmed_pts=%d first=%d last=%d selected_pts=%d clearance_mm=%.1f",
        len(source_path), len(trimmed_path), first, last, int(np.count_nonzero(trimmed_selected)),
        _NON_PAINT_CLEARANCE_MM,
    )
    return trimmed_path, profile.astype(float).tolist()


def _points_near_polyline(points: np.ndarray, polyline: np.ndarray, *, tolerance_mm: float) -> np.ndarray:
    result = np.zeros(len(points), dtype=bool)
    for start, end in zip(polyline[:-1], polyline[1:]):
        vector = end - start
        length_sq = float(np.dot(vector, vector))
        if length_sq <= 1e-12:
            distances = np.linalg.norm(points - start, axis=1)
        else:
            ratios = np.clip(((points - start) @ vector) / length_sq, 0.0, 1.0)
            projections = start + ratios[:, None] * vector
            distances = np.linalg.norm(points - projections, axis=1)
        result |= distances <= float(tolerance_mm)
    return result


def _cumulative_distances(points: np.ndarray) -> np.ndarray:
    if len(points) == 0:
        return np.empty(0, dtype=float)
    if len(points) == 1:
        return np.zeros(1, dtype=float)
    return np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))))
