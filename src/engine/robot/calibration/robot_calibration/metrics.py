import json
import logging
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np
from scipy.interpolate import RBFInterpolator

_logger = logging.getLogger(__name__)


def compute_avg_ppm(camera_points, robot_points):
    ppms = []
    cam_pts = np.asarray(camera_points, dtype=np.float32).reshape(-1, 2)
    rob_pts = np.asarray(robot_points, dtype=np.float32).reshape(-1, 2)
    for i, j in combinations(range(len(cam_pts)), 2):
        dist_px = np.linalg.norm(cam_pts[i] - cam_pts[j])
        dist_mm = np.linalg.norm(rob_pts[i] - rob_pts[j])
        if dist_mm > 1e-9:
            ppms.append(float(dist_px / dist_mm))
    return float(np.mean(ppms)) if ppms else None


def test_calibration(homography_matrix, camera_points, robot_points, save_json_path=None):
    cam_pts = np.asarray(camera_points, dtype=np.float32).reshape(-1, 2)
    rob_pts = np.asarray(robot_points, dtype=np.float32).reshape(-1, 2)

    compute_avg_ppm(cam_pts, rob_pts)

    transformed_pts_cv2 = cv2.perspectiveTransform(cam_pts.reshape(-1, 1, 2), homography_matrix)
    transformed_pts_flat = transformed_pts_cv2.reshape(-1, 2)

    results = []
    for i, (cam_pt, transformed, robot_pt) in enumerate(zip(cam_pts, transformed_pts_flat, rob_pts)):
        error = float(np.linalg.norm(transformed - robot_pt))
        _logger.debug("Point %d:", i + 1)
        _logger.debug("  Camera point:      %s", cam_pt)
        _logger.debug("  Transformed point: %s", transformed)
        _logger.debug("  Robot point:       %s", robot_pt)
        _logger.debug("  Error (mm):        %.3f", error)
        results.append(
            {
                "point": i + 1,
                "camera_point": [float(cam_pt[0]), float(cam_pt[1])],
                "transformed_point": [float(transformed[0]), float(transformed[1])],
                "robot_point": [float(robot_pt[0]), float(robot_pt[1])],
                "error_mm": error,
            }
        )

    errors = np.array([r["error_mm"] for r in results], dtype=np.float32)
    average_error = float(np.mean(errors)) if errors.size > 0 else 0.0
    _logger.debug("Average transformation error: %s mm", average_error)

    if save_json_path:
        if not str(save_json_path).lower().endswith(".json"):
            save_json_path = f"{save_json_path}.json"
        json_data = {"calibration_points": results, "average_error_mm": average_error}
        with open(save_json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=4)
        _logger.debug("Saved calibration results to %s", save_json_path)

    return average_error, transformed_pts_cv2


def compute_homography(camera_points_for_homography, robot_positions_for_calibration, use_ransac: bool = False):
    _, src_pts, dst_pts = prepare_correspondence_points(
        camera_points_for_homography,
        robot_positions_for_calibration,
    )
    return compute_homography_from_arrays(src_pts, dst_pts, use_ransac=use_ransac)


def prepare_correspondence_points(camera_points_for_homography, robot_positions_for_calibration):
    camera_by_id = {int(marker_id): np.asarray(point, dtype=np.float32).reshape(2) for marker_id, point in camera_points_for_homography.items()}
    robot_by_id = {
        int(marker_id): np.asarray(position[:2], dtype=np.float32).reshape(2)
        for marker_id, position in robot_positions_for_calibration.items()
    }
    common_ids = sorted(set(camera_by_id).intersection(robot_by_id))
    if not common_ids:
        raise ValueError("No overlapping camera/robot calibration points were found")

    missing_camera = sorted(set(robot_by_id) - set(camera_by_id))
    missing_robot = sorted(set(camera_by_id) - set(robot_by_id))
    if missing_camera or missing_robot:
        _logger.warning(
            "Calibration correspondences are incomplete; using common marker IDs only. missing_camera=%s missing_robot=%s",
            missing_camera,
            missing_robot,
        )

    src_pts = np.array([camera_by_id[marker_id] for marker_id in common_ids], dtype=np.float32)
    dst_pts = np.array([robot_by_id[marker_id] for marker_id in common_ids], dtype=np.float32)
    return common_ids, src_pts, dst_pts


def compute_homography_from_arrays(src_pts, dst_pts, use_ransac: bool = False):
    src_pts = np.asarray(src_pts, dtype=np.float32).reshape(-1, 2)
    dst_pts = np.asarray(dst_pts, dtype=np.float32).reshape(-1, 2)
    if len(src_pts) < 4:
        raise ValueError(f"Need at least 4 correspondences for homography, got {len(src_pts)}")
    method = cv2.RANSAC if use_ransac else 0
    ransac_threshold = 2.0
    H_camera_center, status = cv2.findHomography(src_pts, dst_pts, method, ransac_threshold)
    if H_camera_center is None:
        raise ValueError("cv2.findHomography failed to compute a valid matrix")
    return H_camera_center, status


@dataclass(frozen=True)
class HomographyResidualModel:
    homography_matrix: np.ndarray
    dx_coeffs: np.ndarray
    dy_coeffs: np.ndarray

    def predict(self, point) -> np.ndarray:
        point_xy = np.asarray(point, dtype=np.float64).reshape(2)
        base_prediction = cv2.perspectiveTransform(
            np.asarray(point_xy, dtype=np.float32).reshape(1, 1, 2),
            np.asarray(self.homography_matrix, dtype=np.float64),
        ).reshape(2).astype(np.float64)
        features = _quadratic_uv_features(point_xy)
        residual = np.array(
            [
                float(features @ self.dx_coeffs),
                float(features @ self.dy_coeffs),
            ],
            dtype=np.float64,
        )
        return base_prediction + residual

    def to_dict(self) -> dict:
        return {
            "basis": "quadratic_uv",
            "homography_matrix": [[float(v) for v in row] for row in np.asarray(self.homography_matrix, dtype=np.float64)],
            "dx_coeffs": [float(v) for v in np.asarray(self.dx_coeffs, dtype=np.float64).reshape(-1)],
            "dy_coeffs": [float(v) for v in np.asarray(self.dy_coeffs, dtype=np.float64).reshape(-1)],
        }


class HomographyTPSResidualModel:
    """Homography + Thin Plate Spline residual correction model."""

    def __init__(self, homography_matrix, support_points, dx_residuals, dy_residuals):
        self.homography_matrix = np.asarray(homography_matrix, dtype=np.float64).reshape(3, 3)
        self.support_points = np.asarray(support_points, dtype=np.float64).reshape(-1, 2)
        self.dx_residuals = np.asarray(dx_residuals, dtype=np.float64).reshape(-1)
        self.dy_residuals = np.asarray(dy_residuals, dtype=np.float64).reshape(-1)
        residuals_2d = np.column_stack([self.dx_residuals, self.dy_residuals])
        self._interpolator = RBFInterpolator(self.support_points, residuals_2d, kernel="thin_plate_spline", smoothing=0)

    def predict(self, point) -> np.ndarray:
        point_xy = np.asarray(point, dtype=np.float64).reshape(2)
        base = cv2.perspectiveTransform(
            np.asarray(point_xy, dtype=np.float32).reshape(1, 1, 2),
            self.homography_matrix,
        ).reshape(2).astype(np.float64)
        residual = self._interpolator(point_xy.reshape(1, 2)).reshape(2)
        return base + residual

    def to_dict(self) -> dict:
        return {
            "basis": "tps",
            "homography_matrix": [[float(v) for v in row] for row in self.homography_matrix],
            "support_points": [[float(v) for v in pt] for pt in self.support_points],
            "dx_residuals": [float(v) for v in self.dx_residuals],
            "dy_residuals": [float(v) for v in self.dy_residuals],
        }


def evaluate_homography_fit(labels, src_pts, dst_pts, use_ransac: bool = False) -> dict:
    H, status = compute_homography_from_arrays(src_pts, dst_pts, use_ransac=use_ransac)
    predictions = cv2.perspectiveTransform(np.asarray(src_pts, dtype=np.float32).reshape(-1, 1, 2), H).reshape(-1, 2)
    records = _build_error_records(labels, src_pts, dst_pts, predictions, model_name="homography")
    return {
        "model": "homography",
        "matrix": np.asarray(H, dtype=np.float64),
        "status": np.asarray(status).reshape(-1).astype(int).tolist() if status is not None else None,
        "records": records,
        "summary": _summarize_records(records),
    }


def build_homography_residual_model(src_pts, dst_pts, use_ransac: bool = False) -> HomographyResidualModel:
    H, _ = compute_homography_from_arrays(src_pts, dst_pts, use_ransac=use_ransac)
    base_predictions = cv2.perspectiveTransform(
        np.asarray(src_pts, dtype=np.float32).reshape(-1, 1, 2),
        H,
    ).reshape(-1, 2).astype(np.float64)
    residuals = np.asarray(dst_pts, dtype=np.float64).reshape(-1, 2) - base_predictions
    design = np.asarray([_quadratic_uv_features(point) for point in np.asarray(src_pts, dtype=np.float64).reshape(-1, 2)], dtype=np.float64)
    dx_coeffs, _, _, _ = np.linalg.lstsq(design, residuals[:, 0], rcond=None)
    dy_coeffs, _, _, _ = np.linalg.lstsq(design, residuals[:, 1], rcond=None)
    return HomographyResidualModel(
        homography_matrix=np.asarray(H, dtype=np.float64),
        dx_coeffs=np.asarray(dx_coeffs, dtype=np.float64),
        dy_coeffs=np.asarray(dy_coeffs, dtype=np.float64),
    )


def evaluate_homography_residual_fit(labels, src_pts, dst_pts, use_ransac: bool = False) -> dict:
    model = build_homography_residual_model(src_pts, dst_pts, use_ransac=use_ransac)
    predictions = [model.predict(point) for point in src_pts]
    records = _build_error_records(labels, src_pts, dst_pts, predictions, model_name="homography_residual")
    return {
        "model": "homography_residual",
        "artifact": model.to_dict(),
        "records": records,
        "summary": _summarize_records(records),
    }


def build_homography_tps_residual_model(src_pts, dst_pts, use_ransac: bool = False) -> HomographyTPSResidualModel:
    H, _ = compute_homography_from_arrays(src_pts, dst_pts, use_ransac=use_ransac)
    base_predictions = cv2.perspectiveTransform(
        np.asarray(src_pts, dtype=np.float32).reshape(-1, 1, 2),
        H,
    ).reshape(-1, 2).astype(np.float64)
    residuals = np.asarray(dst_pts, dtype=np.float64).reshape(-1, 2) - base_predictions
    return HomographyTPSResidualModel(
        homography_matrix=H,
        support_points=np.asarray(src_pts, dtype=np.float64).reshape(-1, 2),
        dx_residuals=residuals[:, 0],
        dy_residuals=residuals[:, 1],
    )


def evaluate_homography_tps_residual_fit(labels, src_pts, dst_pts, use_ransac: bool = False) -> dict:
    model = build_homography_tps_residual_model(src_pts, dst_pts, use_ransac=use_ransac)
    predictions = [model.predict(point) for point in src_pts]
    records = _build_error_records(labels, src_pts, dst_pts, predictions, model_name="homography_tps_residual")
    return {
        "model": "homography_tps_residual",
        "artifact": model.to_dict(),
        "records": records,
        "summary": _summarize_records(records),
    }


def evaluate_leave_one_out(labels, src_pts, dst_pts, use_ransac: bool = False) -> dict:
    labels = [int(v) for v in labels]
    src_pts = np.asarray(src_pts, dtype=np.float64).reshape(-1, 2)
    dst_pts = np.asarray(dst_pts, dtype=np.float64).reshape(-1, 2)

    homography_records = []
    homography_residual_records = []
    for index, label in enumerate(labels):
        train_src = np.delete(src_pts, index, axis=0)
        train_dst = np.delete(dst_pts, index, axis=0)
        target_src = src_pts[index]
        target_dst = dst_pts[index]

        homography_pred = None
        homography_error = None
        homography_note = None
        try:
            H, _ = compute_homography_from_arrays(train_src, train_dst, use_ransac=use_ransac)
            homography_pred = cv2.perspectiveTransform(
                np.asarray(target_src, dtype=np.float32).reshape(1, 1, 2),
                H,
            ).reshape(2)
            homography_error = float(np.linalg.norm(homography_pred - target_dst))
        except Exception as exc:
            homography_note = str(exc)

        homography_records.append(
            _build_single_record(
                label=label,
                camera_point=target_src,
                robot_point=target_dst,
                prediction=homography_pred,
                model_name="homography",
                note=homography_note,
                error_override=homography_error,
            )
        )

        homography_residual_pred = None
        homography_residual_error = None
        homography_residual_note = None
        try:
            homography_residual_model = build_homography_residual_model(train_src, train_dst, use_ransac=use_ransac)
            homography_residual_pred = homography_residual_model.predict(target_src)
            homography_residual_error = float(np.linalg.norm(homography_residual_pred - target_dst))
        except Exception as exc:
            homography_residual_note = str(exc)

        homography_residual_records.append(
            _build_single_record(
                label=label,
                camera_point=target_src,
                robot_point=target_dst,
                prediction=homography_residual_pred,
                model_name="homography_residual",
                note=homography_residual_note,
                error_override=homography_residual_error,
            )
        )

    return {
        "homography": {
            "records": homography_records,
            "summary": _summarize_records(homography_records),
        },
        "homography_residual": {
            "records": homography_residual_records,
            "summary": _summarize_records(homography_residual_records),
        },
    }


def build_calibration_model_report(
    camera_points_for_homography,
    robot_positions_for_calibration,
    use_ransac: bool = False,
    metadata: dict | None = None,
) -> dict:
    labels, src_pts, dst_pts = prepare_correspondence_points(
        camera_points_for_homography,
        robot_positions_for_calibration,
    )
    fit_h = evaluate_homography_fit(labels, src_pts, dst_pts, use_ransac=use_ransac)
    fit_hr = evaluate_homography_residual_fit(labels, src_pts, dst_pts, use_ransac=use_ransac)
    fit_tps = evaluate_homography_tps_residual_fit(labels, src_pts, dst_pts, use_ransac=use_ransac)

    report = {
        "support_point_count": len(labels),
        "point_labels": labels,
        "camera_points": [[float(v) for v in pt] for pt in src_pts],
        "robot_points": [[float(v) for v in pt] for pt in dst_pts],
        "fit": {
            "homography": {
                "summary": fit_h["summary"],
                "records": fit_h["records"],
                "status": fit_h["status"],
            },
            "homography_residual": {
                "summary": fit_hr["summary"],
                "records": fit_hr["records"],
            },
            "homography_tps_residual": {
                "summary": fit_tps["summary"],
                "records": fit_tps["records"],
            },
        },
        "artifacts": {
            "homography_matrix": np.asarray(fit_h["matrix"], dtype=np.float64),
            "homography_status": fit_h["status"],
            "homography_residual": fit_hr["artifact"],
            "homography_tps_residual": fit_tps["artifact"],
        },
    }
    if metadata:
        report["metadata"] = _to_json_ready(metadata)
    return report


def save_calibration_model_report(report: dict, report_path: str) -> None:
    payload = _to_json_ready(report)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def save_homography_residual_artifact(homography_residual_artifact: dict, path: str) -> None:
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
        if metadata.get("recovery_marker_id") is not None:
            lines.append(f"Recovery marker ID: {metadata['recovery_marker_id']}")

    lines.extend([
        "",
        "Reprojection error on support points:",
        _format_summary_line("Homography                  ", fit_h),
        _format_summary_line("Homography + Quadratic      ", fit_hr),
    ])
    if fit_tps:
        lines.append(
            _format_summary_line("Homography + TPS (active)   ", fit_tps)
            + "  [exact interpolant — 0 on training points by design]"
        )

    lines.extend(["", "Per-point comparison:"])

    homography_by_label = {row["label"]: row for row in report["fit"]["homography"]["records"]}
    quadratic_by_label = {row["label"]: row for row in report["fit"]["homography_residual"]["records"]}
    tps_by_label = (
        {row["label"]: row for row in report["fit"]["homography_tps_residual"]["records"]}
        if fit_tps else {}
    )

    for label in report["point_labels"]:
        h_err = homography_by_label[label]["error_mm"]
        q_err = quadratic_by_label[label]["error_mm"]
        parts = [
            f"  ID {label:3d}: homography={_fmt_error(h_err)} mm",
            f"+quadratic={_fmt_error(q_err)} mm (Δ{_fmt_delta(h_err, q_err)})",
        ]
        if tps_by_label:
            t_err = tps_by_label[label]["error_mm"]
            parts.append(f"+tps={_fmt_error(t_err)} mm (Δ{_fmt_delta(h_err, t_err)})")
        lines.append("  ".join(parts))

    return "\n".join(lines)


def _build_error_records(labels, src_pts, dst_pts, predictions, model_name: str) -> list[dict]:
    records = []
    for label, camera_point, robot_point, prediction in zip(labels, src_pts, dst_pts, predictions):
        records.append(
            _build_single_record(
                label=label,
                camera_point=camera_point,
                robot_point=robot_point,
                prediction=prediction,
                model_name=model_name,
            )
        )
    return records


def _build_single_record(label, camera_point, robot_point, prediction, model_name: str, note: str | None = None, error_override: float | None = None) -> dict:
    robot_point = np.asarray(robot_point, dtype=np.float64).reshape(2)
    prediction_xy = None if prediction is None else np.asarray(prediction, dtype=np.float64).reshape(2)
    error_mm = error_override
    if error_mm is None and prediction_xy is not None:
        error_mm = float(np.linalg.norm(prediction_xy - robot_point))

    return {
        "label": int(label),
        "model": model_name,
        "camera_point": [float(v) for v in np.asarray(camera_point, dtype=np.float64).reshape(2)],
        "robot_point": [float(v) for v in robot_point],
        "predicted_robot_point": None if prediction_xy is None else [float(v) for v in prediction_xy],
        "error_mm": None if error_mm is None else float(error_mm),
        "note": note,
    }


def _summarize_records(records: list[dict]) -> dict:
    valid_errors = np.array([row["error_mm"] for row in records if row.get("error_mm") is not None], dtype=np.float64)
    if valid_errors.size == 0:
        return {
            "count": len(records),
            "valid_count": 0,
            "unavailable_count": len(records),
            "mean_mm": None,
            "median_mm": None,
            "p90_mm": None,
            "max_mm": None,
        }
    return {
        "count": len(records),
        "valid_count": int(valid_errors.size),
        "unavailable_count": int(len(records) - valid_errors.size),
        "mean_mm": float(np.mean(valid_errors)),
        "median_mm": float(np.median(valid_errors)),
        "p90_mm": float(np.percentile(valid_errors, 90)),
        "max_mm": float(np.max(valid_errors)),
    }


def _quadratic_uv_features(point) -> np.ndarray:
    u, v = np.asarray(point, dtype=np.float64).reshape(2)
    return np.asarray([1.0, float(u), float(v), float(u * u), float(u * v), float(v * v)], dtype=np.float64)


def _format_summary_line(model_name: str, summary: dict) -> str:
    return (
        f"  {model_name}: "
        f"count={summary['count']} valid={summary['valid_count']} unavailable={summary['unavailable_count']} "
        f"mean={_fmt_error(summary['mean_mm'])} median={_fmt_error(summary['median_mm'])} "
        f"p90={_fmt_error(summary['p90_mm'])} max={_fmt_error(summary['max_mm'])}"
    )


def _fmt_error(value) -> str:
    return "n/a" if value is None else f"{float(value):.4f}"


def _fmt_delta(before, after) -> str:
    if before is None or after is None:
        return "n/a"
    return f"{float(after) - float(before):+.4f} mm"


def _fmt_note(note: str | None) -> str:
    return "" if not note else f" ({note})"


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
