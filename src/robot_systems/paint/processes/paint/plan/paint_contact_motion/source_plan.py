from __future__ import annotations

import logging

from src.engine.robot.path_preparation import WorkpieceExecutionPlan
from src.robot_systems.paint.processes.paint.config import PaintSimulationConfig

_logger = logging.getLogger(__name__)


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
