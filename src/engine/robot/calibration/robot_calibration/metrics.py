import json
import logging
from dataclasses import dataclass
from itertools import combinations

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
    return build_homography_tps_residual_model_from_base(H, src_pts, dst_pts)


def build_homography_residual_model_from_base(
    homography_matrix,
    src_pts,
    dst_pts,
) -> HomographyResidualModel:
    H = np.asarray(homography_matrix, dtype=np.float64).reshape(3, 3)
    base_predictions = cv2.perspectiveTransform(
        np.asarray(src_pts, dtype=np.float32).reshape(-1, 1, 2),
        H,
    ).reshape(-1, 2).astype(np.float64)
    residuals = np.asarray(dst_pts, dtype=np.float64).reshape(-1, 2) - base_predictions
    design = np.asarray(
        [_quadratic_uv_features(point) for point in np.asarray(src_pts, dtype=np.float64).reshape(-1, 2)],
        dtype=np.float64,
    )
    dx_coeffs, _, _, _ = np.linalg.lstsq(design, residuals[:, 0], rcond=None)
    dy_coeffs, _, _, _ = np.linalg.lstsq(design, residuals[:, 1], rcond=None)
    return HomographyResidualModel(
        homography_matrix=H,
        dx_coeffs=np.asarray(dx_coeffs, dtype=np.float64),
        dy_coeffs=np.asarray(dy_coeffs, dtype=np.float64),
    )


def build_homography_tps_residual_model_from_base(
    homography_matrix,
    src_pts,
    dst_pts,
) -> HomographyTPSResidualModel:
    H = np.asarray(homography_matrix, dtype=np.float64).reshape(3, 3)
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


def evaluate_homography_residual_fit_from_model(labels, src_pts, dst_pts, model: HomographyResidualModel) -> dict:
    predictions = [model.predict(point) for point in src_pts]
    records = _build_error_records(labels, src_pts, dst_pts, predictions, model_name="homography_residual")
    return {
        "model": "homography_residual",
        "artifact": model.to_dict(),
        "records": records,
        "summary": _summarize_records(records),
    }


def evaluate_homography_tps_residual_fit_from_model(labels, src_pts, dst_pts, model: HomographyTPSResidualModel) -> dict:
    predictions = [model.predict(point) for point in src_pts]
    records = _build_error_records(labels, src_pts, dst_pts, predictions, model_name="homography_tps_residual")
    return {
        "model": "homography_tps_residual",
        "artifact": model.to_dict(),
        "records": records,
        "summary": _summarize_records(records),
    }


def evaluate_model_on_holdout(
    labels,
    src_pts,
    dst_pts,
    *,
    homography_matrix=None,
    homography_residual_model: HomographyResidualModel | None = None,
    homography_tps_residual_model: HomographyTPSResidualModel | None = None,
) -> dict:
    labels = [int(v) for v in labels]
    src_pts = np.asarray(src_pts, dtype=np.float64).reshape(-1, 2)
    dst_pts = np.asarray(dst_pts, dtype=np.float64).reshape(-1, 2)
    fit: dict[str, dict] = {}

    if homography_matrix is not None:
        predictions = cv2.perspectiveTransform(
            np.asarray(src_pts, dtype=np.float32).reshape(-1, 1, 2),
            np.asarray(homography_matrix, dtype=np.float64),
        ).reshape(-1, 2)
        records = _build_error_records(labels, src_pts, dst_pts, predictions, model_name="homography")
        fit["homography"] = {"records": records, "summary": _summarize_records(records)}

    if homography_residual_model is not None:
        predictions = [homography_residual_model.predict(point) for point in src_pts]
        records = _build_error_records(labels, src_pts, dst_pts, predictions, model_name="homography_residual")
        fit["homography_residual"] = {"records": records, "summary": _summarize_records(records)}

    if homography_tps_residual_model is not None:
        predictions = [homography_tps_residual_model.predict(point) for point in src_pts]
        records = _build_error_records(labels, src_pts, dst_pts, predictions, model_name="homography_tps_residual")
        fit["homography_tps_residual"] = {"records": records, "summary": _summarize_records(records)}

    return {
        "point_labels": labels,
        "camera_points": [[float(v) for v in pt] for pt in src_pts],
        "robot_points": [[float(v) for v in pt] for pt in dst_pts],
        "fit": fit,
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
    validation_camera_points=None,
    validation_robot_positions=None,
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
    if validation_camera_points and validation_robot_positions:
        validation_labels, validation_src_pts, validation_dst_pts = prepare_correspondence_points(
            validation_camera_points,
            validation_robot_positions,
        )
        report["validation"] = evaluate_model_on_holdout(
            validation_labels,
            validation_src_pts,
            validation_dst_pts,
            homography_matrix=fit_h["matrix"],
            homography_residual_model=build_homography_residual_model(src_pts, dst_pts, use_ransac=use_ransac),
            homography_tps_residual_model=build_homography_tps_residual_model(src_pts, dst_pts, use_ransac=use_ransac),
        )
    if metadata:
        report["metadata"] = _to_json_ready(metadata)
    return report


def build_split_calibration_model_report(
    homography_camera_points,
    homography_robot_points,
    residual_camera_points,
    residual_robot_points,
    *,
    use_ransac: bool = False,
    metadata: dict | None = None,
    validation_camera_points=None,
    validation_robot_positions=None,
) -> dict:
    homography_labels, homography_src_pts, homography_dst_pts = prepare_correspondence_points(
        homography_camera_points,
        homography_robot_points,
    )
    fit_h = evaluate_homography_fit(homography_labels, homography_src_pts, homography_dst_pts, use_ransac=use_ransac)

    residual_labels = []
    residual_src_pts = np.empty((0, 2), dtype=np.float64)
    residual_dst_pts = np.empty((0, 2), dtype=np.float64)
    fit_hr = {
        "model": "homography_residual",
        "artifact": None,
        "records": [],
        "summary": _summarize_records([]),
    }
    fit_tps = {
        "model": "homography_tps_residual",
        "artifact": None,
        "records": [],
        "summary": _summarize_records([]),
    }
    quadratic_model = None
    tps_model = None

    if residual_camera_points and residual_robot_points:
        residual_labels, residual_src_pts, residual_dst_pts = prepare_correspondence_points(
            residual_camera_points,
            residual_robot_points,
        )
        quadratic_model = build_homography_residual_model_from_base(
            fit_h["matrix"], residual_src_pts, residual_dst_pts
        )
        fit_hr = evaluate_homography_residual_fit_from_model(
            residual_labels, residual_src_pts, residual_dst_pts, quadratic_model
        )
        if len(residual_labels) >= 3:
            tps_model = build_homography_tps_residual_model_from_base(
                fit_h["matrix"], residual_src_pts, residual_dst_pts
            )
            fit_tps = evaluate_homography_tps_residual_fit_from_model(
                residual_labels, residual_src_pts, residual_dst_pts, tps_model
            )

    report = {
        "support_point_count": len(homography_labels),
        "point_labels": homography_labels,
        "camera_points": [[float(v) for v in pt] for pt in homography_src_pts],
        "robot_points": [[float(v) for v in pt] for pt in homography_dst_pts],
        "residual_support_point_count": len(residual_labels),
        "residual_point_labels": residual_labels,
        "residual_camera_points": [[float(v) for v in pt] for pt in residual_src_pts],
        "residual_robot_points": [[float(v) for v in pt] for pt in residual_dst_pts],
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

    if validation_camera_points and validation_robot_positions:
        validation_labels, validation_src_pts, validation_dst_pts = prepare_correspondence_points(
            validation_camera_points,
            validation_robot_positions,
        )
        report["validation"] = evaluate_model_on_holdout(
            validation_labels,
            validation_src_pts,
            validation_dst_pts,
            homography_matrix=fit_h["matrix"],
            homography_residual_model=quadratic_model,
            homography_tps_residual_model=tps_model,
        )
    if metadata:
        report["metadata"] = _to_json_ready(metadata)
    return report


def save_calibration_model_report(report: dict, report_path: str) -> None:
    from src.engine.robot.calibration.robot_calibration.calibration_report import (
        save_calibration_model_report as _save_calibration_model_report,
    )
    _save_calibration_model_report(report, report_path)


def save_homography_residual_artifact(homography_residual_artifact: dict, path: str) -> None:
    from src.engine.robot.calibration.robot_calibration.calibration_report import (
        save_homography_residual_artifact as _save_homography_residual_artifact,
    )
    _save_homography_residual_artifact(homography_residual_artifact, path)


def derive_calibration_artifact_paths(matrix_path: str) -> dict:
    from src.engine.robot.calibration.robot_calibration.calibration_report import (
        derive_calibration_artifact_paths as _derive_calibration_artifact_paths,
    )
    return _derive_calibration_artifact_paths(matrix_path)


def format_model_comparison_report(report: dict) -> str:
    from src.engine.robot.calibration.robot_calibration.calibration_report import (
        format_model_comparison_report as _format_model_comparison_report,
    )
    return _format_model_comparison_report(report)


def format_calibration_analysis_report(report: dict) -> str:
    from src.engine.robot.calibration.robot_calibration.calibration_report import (
        format_calibration_analysis_report as _format_calibration_analysis_report,
    )
    return _format_calibration_analysis_report(report)


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
    valid_dx = np.array(
        [
            float(row["predicted_robot_point"][0] - row["robot_point"][0])
            for row in records
            if row.get("predicted_robot_point") is not None and row.get("robot_point") is not None
        ],
        dtype=np.float64,
    )
    valid_dy = np.array(
        [
            float(row["predicted_robot_point"][1] - row["robot_point"][1])
            for row in records
            if row.get("predicted_robot_point") is not None and row.get("robot_point") is not None
        ],
        dtype=np.float64,
    )
    if valid_errors.size == 0:
        return {
            "count": len(records),
            "valid_count": 0,
            "unavailable_count": len(records),
            "mean_mm": None,
            "median_mm": None,
            "std_mm": None,
            "p90_mm": None,
            "p95_mm": None,
            "max_mm": None,
            "mean_dx_mm": None,
            "std_dx_mm": None,
            "mean_dy_mm": None,
            "std_dy_mm": None,
        }
    return {
        "count": len(records),
        "valid_count": int(valid_errors.size),
        "unavailable_count": int(len(records) - valid_errors.size),
        "mean_mm": float(np.mean(valid_errors)),
        "median_mm": float(np.median(valid_errors)),
        "std_mm": float(np.std(valid_errors)),
        "p90_mm": float(np.percentile(valid_errors, 90)),
        "p95_mm": float(np.percentile(valid_errors, 95)),
        "max_mm": float(np.max(valid_errors)),
        "mean_dx_mm": float(np.mean(valid_dx)) if valid_dx.size else None,
        "std_dx_mm": float(np.std(valid_dx)) if valid_dx.size else None,
        "mean_dy_mm": float(np.mean(valid_dy)) if valid_dy.size else None,
        "std_dy_mm": float(np.std(valid_dy)) if valid_dy.size else None,
    }


def _quadratic_uv_features(point) -> np.ndarray:
    u, v = np.asarray(point, dtype=np.float64).reshape(2)
    return np.asarray([1.0, float(u), float(v), float(u * u), float(u * v), float(v * v)], dtype=np.float64)


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
