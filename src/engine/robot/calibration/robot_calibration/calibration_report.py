from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from src.engine.robot.calibration.robot_calibration.logging import (
    construct_calibration_completion_log_message,
)

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CalibrationReportBundle:
    completion_log: str
    model_comparison_report: str
    calibration_analysis_report: str
    artifact_paths: dict


def build_calibration_reports(
    *,
    context,
    model_result,
    candidate_ids: list[int],
    selected_ids: list[int],
    used_ids: list[int],
    skipped_ids: list[int],
    failed_ids: list[int],
    recovery_marker_id: int | None,
    total_calibration_time: float,
) -> CalibrationReportBundle:
    artifact_paths = derive_calibration_artifact_paths(
        context.vision_service.camera_to_robot_matrix_path,
    )
    completion_log = construct_calibration_completion_log_message(
        sorted_robot_items=model_result.sorted_robot_items,
        sorted_camera_items=model_result.sorted_camera_items,
        H_camera_center=model_result.homography_matrix,
        status=model_result.homography_status,
        average_error_camera_center=model_result.average_error_mm,
        matrix_path=context.vision_service.camera_to_robot_matrix_path,
        total_calibration_time=total_calibration_time,
        candidate_ids=candidate_ids,
        selected_ids=selected_ids,
        used_ids=used_ids,
        skipped_ids=skipped_ids,
        failed_ids=failed_ids,
        recovery_marker_id=recovery_marker_id,
    )
    return CalibrationReportBundle(
        completion_log=completion_log,
        model_comparison_report=format_model_comparison_report(model_result.model_report),
        calibration_analysis_report=format_calibration_analysis_report(model_result.model_report),
        artifact_paths=artifact_paths,
    )


def save_calibration_model_report(report: dict, report_path: str) -> None:
    payload = _to_json_ready(report)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def save_homography_residual_artifact(homography_residual_artifact: dict, path: str) -> None:
    if homography_residual_artifact is None:
        _logger.warning("No homography residual artifact to save for %s", path)
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_to_json_ready(homography_residual_artifact), f, indent=2)


def derive_calibration_artifact_paths(matrix_path: str) -> dict:
    base = Path(matrix_path)
    stem = base.stem
    return {
        "homography_residual_path": str(base.with_name(f"{stem}_homography_residual.json")),
        "report_path": str(base.with_name(f"{stem}_model_report.json")),
    }


def format_model_comparison_report(report: dict) -> str:
    fit_h = report["fit"]["homography"]["summary"]
    fit_hr = report["fit"]["homography_residual"]["summary"]
    fit_tps = report["fit"].get("homography_tps_residual", {}).get("summary")

    lines = [
        "=== CALIBRATION MODEL COMPARISON REPORT ===",
        f"Support points: {report['support_point_count']}",
    ]

    metadata = report.get("metadata") or {}
    if metadata:
        if metadata.get("candidate_ids") is not None:
            lines.append(f"Candidate IDs: {metadata['candidate_ids']}")
        if metadata.get("selected_target_ids") is not None:
            lines.append(f"Selected target IDs: {metadata['selected_target_ids']}")
        if metadata.get("used_marker_ids") is not None:
            lines.append(f"Used marker IDs: {metadata['used_marker_ids']}")
        if metadata.get("skipped_marker_ids"):
            lines.append(f"Skipped marker IDs: {metadata['skipped_marker_ids']}")
        if metadata.get("failed_marker_ids"):
            lines.append(f"Failed marker IDs: {metadata['failed_marker_ids']}")
        if metadata.get("known_unreachable_marker_ids"):
            lines.append(f"Known unreachable marker IDs: {metadata['known_unreachable_marker_ids']}")
        if metadata.get("recovery_marker_id") is not None:
            lines.append(f"Recovery marker ID: {metadata['recovery_marker_id']}")

    lines.extend([
        "",
        "Training fit on support points:",
        _format_summary_line("Homography                  ", fit_h),
        _format_summary_line("Homography + Quadratic      ", fit_hr),
    ])
    if fit_tps:
        lines.append(
            _format_summary_line("Homography + TPS (active)   ", fit_tps)
            + "  [exact interpolant - 0 on training points by design]"
        )

    validation = report.get("validation") or {}
    validation_fit = validation.get("fit") or {}
    if validation_fit:
        lines.extend(["", "Holdout validation:"])
        for model_key, label in [
            ("homography", "Homography                  "),
            ("homography_residual", "Homography + Quadratic      "),
            ("homography_tps_residual", "Homography + TPS (active)   "),
        ]:
            summary = (validation_fit.get(model_key) or {}).get("summary")
            if summary:
                lines.append(_format_summary_line(label, summary))

    lines.extend(["", "Training per-point comparison:"])

    homography_by_label = {row["label"]: row for row in report["fit"]["homography"]["records"]}
    quadratic_by_label = {row["label"]: row for row in report["fit"]["homography_residual"]["records"]}
    tps_by_label = (
        {row["label"]: row for row in report["fit"]["homography_tps_residual"]["records"]}
        if fit_tps else {}
    )

    all_comparison_labels = sorted(set(homography_by_label) | set(quadratic_by_label))
    for label in all_comparison_labels:
        h_row = homography_by_label.get(label)
        q_row = quadratic_by_label.get(label)
        h_err = h_row["error_mm"] if h_row is not None else None
        q_err = q_row["error_mm"] if q_row is not None else None
        if h_err is not None and q_err is not None:
            parts = [
                f"  ID {label:3d}: homography={_fmt_error(h_err)} mm",
                f"+quadratic={_fmt_error(q_err)} mm (Δ{_fmt_delta(h_err, q_err)})",
            ]
            if tps_by_label and label in tps_by_label:
                t_err = tps_by_label[label]["error_mm"]
                parts.append(f"+tps={_fmt_error(t_err)} mm (Δ{_fmt_delta(h_err, t_err)})")
        elif h_err is not None:
            parts = [f"  ID {label:3d}: homography={_fmt_error(h_err)} mm"]
        else:
            parts = [
                f"  ID {label:3d}: quadratic={_fmt_error(q_err)} mm",
            ]
            if tps_by_label and label in tps_by_label:
                t_err = tps_by_label[label]["error_mm"]
                parts.append(f"+tps={_fmt_error(t_err)} mm")
        lines.append("  ".join(parts))

    return "\n".join(lines)


def format_calibration_analysis_report(report: dict) -> str:
    lines = ["=== CALIBRATION ANALYSIS ==="]
    metadata = report.get("metadata") or {}
    if metadata:
        if metadata.get("homography_marker_ids") is not None:
            lines.append(f"Homography IDs: {metadata['homography_marker_ids']}")
        if metadata.get("residual_marker_ids") is not None:
            lines.append(f"Residual IDs: {metadata['residual_marker_ids']}")
        if metadata.get("validation_marker_ids") is not None:
            lines.append(f"Validation IDs: {metadata['validation_marker_ids']}")
        if metadata.get("known_unreachable_marker_ids") is not None:
            lines.append(f"Known unreachable IDs: {metadata['known_unreachable_marker_ids']}")
        if metadata.get("unreachable_marker_failure_counts") is not None:
            lines.append(f"Known unreachable failure counts: {metadata['unreachable_marker_failure_counts']}")

    lines.append("")
    lines.append("Training metrics:")
    for model_key, label in [
        ("homography", "Homography"),
        ("homography_residual", "Homography + Quadratic"),
        ("homography_tps_residual", "Homography + TPS (active)"),
    ]:
        summary = (report.get("fit", {}).get(model_key) or {}).get("summary")
        if summary:
            lines.append(_format_analysis_line(label, summary))

    validation_fit = (report.get("validation") or {}).get("fit") or {}
    if validation_fit:
        lines.append("")
        lines.append("Holdout validation metrics:")
        for model_key, label in [
            ("homography", "Homography"),
            ("homography_residual", "Homography + Quadratic"),
            ("homography_tps_residual", "Homography + TPS (active)"),
        ]:
            summary = (validation_fit.get(model_key) or {}).get("summary")
            if summary:
                lines.append(_format_analysis_line(label, summary))
    else:
        lines.append("")
        lines.append("Holdout validation metrics: unavailable")

    return "\n".join(lines)


def _format_summary_line(model_name: str, summary: dict) -> str:
    return (
        f"  {model_name}: "
        f"count={summary['count']} valid={summary['valid_count']} unavailable={summary['unavailable_count']} "
        f"mean={_fmt_error(summary['mean_mm'])} median={_fmt_error(summary['median_mm'])} "
        f"std={_fmt_error(summary.get('std_mm'))} "
        f"p90={_fmt_error(summary['p90_mm'])} p95={_fmt_error(summary.get('p95_mm'))} max={_fmt_error(summary['max_mm'])} "
        f"dx_mean={_fmt_error(summary.get('mean_dx_mm'))} dx_std={_fmt_error(summary.get('std_dx_mm'))} "
        f"dy_mean={_fmt_error(summary.get('mean_dy_mm'))} dy_std={_fmt_error(summary.get('std_dy_mm'))}"
    )


def _format_analysis_line(model_name: str, summary: dict) -> str:
    return (
        f"  {model_name}: "
        f"mean={_fmt_error(summary.get('mean_mm'))} "
        f"median={_fmt_error(summary.get('median_mm'))} "
        f"std={_fmt_error(summary.get('std_mm'))} "
        f"p90={_fmt_error(summary.get('p90_mm'))} "
        f"p95={_fmt_error(summary.get('p95_mm'))} "
        f"max={_fmt_error(summary.get('max_mm'))} "
        f"dx_mean={_fmt_error(summary.get('mean_dx_mm'))} "
        f"dx_std={_fmt_error(summary.get('std_dx_mm'))} "
        f"dy_mean={_fmt_error(summary.get('mean_dy_mm'))} "
        f"dy_std={_fmt_error(summary.get('std_dy_mm'))}"
    )


def _fmt_error(value) -> str:
    return "n/a" if value is None else f"{float(value):.4f}"


def _fmt_delta(before, after) -> str:
    if before is None or after is None:
        return "n/a"
    return f"{float(after) - float(before):+.4f} mm"


def _to_json_ready(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, dict):
        return {str(k): _to_json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_json_ready(v) for v in value]
    return value
