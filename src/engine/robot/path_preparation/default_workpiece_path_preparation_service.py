from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import cv2
import numpy as np

from src.engine.robot.path_preparation.geometry import (
    PATH_TANGENT_HEADING_DEADBAND_DEG,
    PATH_TANGENT_LOOKAHEAD_DISTANCE_MM,
    compute_pickup_rz_from_robot_path,
    has_valid_contour,
    rebuild_pose_path_from_xy,
)
from src.engine.robot.path_preparation.i_workpiece_path_preparation_service import IWorkpiecePathPreparationService

_EXECUTION_INTERPOLATION_SPACING_MM = 10.0
_EXECUTION_MIN_PREPROCESS_SPACING_MM = 2.5
_EXECUTION_DENSE_SAMPLING_FACTOR = 0.25
_EXECUTION_OUTPUT_SPACING_SCALE = 0.75
_EXECUTION_MIN_OUTPUT_SPACING_MM = 6.0
_EXECUTION_DEFAULT_OUTPUT_SPACING_MM = max(
    _EXECUTION_MIN_OUTPUT_SPACING_MM,
    _EXECUTION_INTERPOLATION_SPACING_MM * _EXECUTION_OUTPUT_SPACING_SCALE,
)
_AUTO_DENSIFY_TRIGGER_RATIO = 2.5
_AUTO_DENSIFY_TARGET_RATIO = 1.25
_DEFAULT_WORKPIECE_HEIGHT_MM = 0.0
_SEGMENT_PREPROCESS_MIN_SPACING_KEY = "preprocess_min_spacing_mm"
_SEGMENT_INTERPOLATION_SPACING_KEY = "interpolation_spacing_mm"
_SEGMENT_DENSE_SAMPLING_FACTOR_KEY = "dense_sampling_factor"
_SEGMENT_EXECUTION_SPACING_KEY = "execution_spacing_mm"
_SEGMENT_TANGENT_LOOKAHEAD_DISTANCE_KEY = "path_tangent_lookahead_mm"
_SEGMENT_TANGENT_DEADBAND_KEY = "path_tangent_deadband_deg"


@dataclass(frozen=True)
class WorkpieceExecutionPlan:
    workpiece: dict
    raw_paths: list[list[list[float]]]
    prepared_paths: list[list[list[float]]]
    curve_paths: list[list[list[float]]]
    sampled_paths: list[list[list[float]]]
    execution_jobs: list[dict]
    total_spline_pts: int

    def execution_paths(self) -> list[list[list[float]]]:
        return [
            [list(point) for point in (job.get("execution_path") or job.get("path") or [])]
            for job in self.execution_jobs
        ]


def _safe_float(value, default: float) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _resample_execution_path(
    path: list[list[float]],
    target_spacing_mm: float,
) -> list[list[float]]:
    if len(path) < 3:
        return [list(point) for point in path]

    target_spacing_mm = max(1.0, float(target_spacing_mm))
    resampled: list[list[float]] = [list(path[0])]
    carry_mm = 0.0

    for i in range(len(path) - 1):
        start = np.array(path[i], dtype=float)
        end = np.array(path[i + 1], dtype=float)
        segment = end[:3] - start[:3]
        seg_len = float(np.linalg.norm(segment))
        if seg_len <= 1e-9:
            continue

        distance_along = target_spacing_mm - carry_mm if carry_mm > 1e-9 else target_spacing_mm
        while distance_along < seg_len - 1e-9:
            ratio = distance_along / seg_len
            point = (start + ratio * (end - start)).tolist()
            if any(abs(float(a) - float(b)) > 1e-9 for a, b in zip(resampled[-1], point)):
                resampled.append(point)
            distance_along += target_spacing_mm

        remaining = seg_len - (distance_along - target_spacing_mm)
        carry_mm = 0.0 if remaining >= target_spacing_mm - 1e-9 else remaining

    if any(abs(float(a) - float(b)) > 1e-9 for a, b in zip(resampled[-1], path[-1])):
        resampled.append(list(path[-1]))
    return resampled


def _resolve_segment_interpolation_settings(settings: dict) -> tuple[float, float, float, float]:
    preprocess_spacing_mm = max(
        0.1,
        _safe_float(settings.get(_SEGMENT_PREPROCESS_MIN_SPACING_KEY), _EXECUTION_MIN_PREPROCESS_SPACING_MM),
    )
    interpolation_spacing_mm = max(
        0.5,
        _safe_float(settings.get(_SEGMENT_INTERPOLATION_SPACING_KEY), _EXECUTION_INTERPOLATION_SPACING_MM),
    )
    dense_sampling_factor = max(
        0.05,
        _safe_float(settings.get(_SEGMENT_DENSE_SAMPLING_FACTOR_KEY), _EXECUTION_DENSE_SAMPLING_FACTOR),
    )
    execution_spacing_mm = max(
        1.0,
        _safe_float(settings.get(_SEGMENT_EXECUTION_SPACING_KEY), _EXECUTION_DEFAULT_OUTPUT_SPACING_MM),
    )
    return preprocess_spacing_mm, interpolation_spacing_mm, dense_sampling_factor, execution_spacing_mm


def _resolve_segment_tangent_settings(settings: dict) -> tuple[float, float]:
    lookahead_distance_mm = max(
        1.0,
        _safe_float(settings.get(_SEGMENT_TANGENT_LOOKAHEAD_DISTANCE_KEY), PATH_TANGENT_LOOKAHEAD_DISTANCE_MM),
    )
    heading_deadband_deg = max(
        0.0,
        _safe_float(settings.get(_SEGMENT_TANGENT_DEADBAND_KEY), PATH_TANGENT_HEADING_DEADBAND_DEG),
    )
    return lookahead_distance_mm, heading_deadband_deg


def _auto_input_densify_spacing(path_pts: list[list[float]], interpolation_spacing_mm: float) -> float:
    if len(path_pts) < 3:
        return 0.0
    xy = np.asarray(path_pts, dtype=float)[:, :2]
    diffs = np.diff(xy, axis=0)
    seg_lengths = np.linalg.norm(diffs, axis=1)
    seg_lengths = seg_lengths[seg_lengths > 1e-9]
    if seg_lengths.size == 0:
        return 0.0
    max_segment = float(np.max(seg_lengths))
    trigger_spacing = max(float(interpolation_spacing_mm) * _AUTO_DENSIFY_TRIGGER_RATIO, 1.0)
    if max_segment <= trigger_spacing:
        return 0.0
    return max(1.0, float(interpolation_spacing_mm) * _AUTO_DENSIFY_TARGET_RATIO)


class DefaultWorkpiecePathPreparationService(IWorkpiecePathPreparationService):
    def __init__(
        self,
        *,
        logger,
        segment_config,
        transformer=None,
        resolver=None,
        z_min: float = 0.0,
        rz_mode: str = "constant",
        execute_from_workpiece_layer: bool = False,
        target_point_name: str = "",
        pickup_target_point_name: str = "",
        calibration_frame_name: str = "",
        pixel_height_compensation_fn: Optional[Callable[[float], tuple[float, float]]] = None,
        base_position_provider: Optional[Callable[[], Optional[list[float]]]] = None,
    ) -> None:
        self._logger = logger
        self._segment_config = segment_config
        self._transformer = transformer
        self._resolver = resolver
        self._z_min = float(z_min)
        self._rz_mode = str(rz_mode or "constant").strip().lower()
        self._execute_from_workpiece_layer = bool(execute_from_workpiece_layer)
        self._target_point_name = str(target_point_name or "").strip().lower()
        self._pickup_target_point_name = str(pickup_target_point_name or self._target_point_name or "").strip().lower()
        self._calibration_frame_name = str(calibration_frame_name or "").strip().lower()
        self._pixel_height_compensation_fn = pixel_height_compensation_fn
        self._base_position_provider = base_position_provider

    def build_execution_plan(self, workpiece: dict) -> WorkpieceExecutionPlan:
        from src.engine.robot.path_interpolation.new_interpolation.interpolation_pipeline import (
            ContourPathPipeline,
            InterpolationConfig,
            PreprocessConfig,
            RuckigConfig,
        )

        merged = dict(workpiece or {})
        spray_pattern = merged.get("sprayPattern", {})
        workpiece_height_mm = _safe_float(merged.get("height_mm"), _DEFAULT_WORKPIECE_HEIGHT_MM)
        use_workpiece_layer = False
        if not spray_pattern or not any(spray_pattern.get(k) for k in ("Contour", "Fill")):
            if self._execute_from_workpiece_layer and has_valid_contour(merged.get("contour")):
                use_workpiece_layer = True
                self._logger.info("[EXECUTE] No spray patterns found; using workpiece layer for execution")
            else:
                raise ValueError("No spray patterns found — draw Contour or Fill paths first")

        robot_paths = []
        pickup_px = self._extract_pickup_pixel(merged)
        pickup_xy = None
        pickup_rz = 0.0
        pickup_camera_xy = None

        if use_workpiece_layer:
            contour_arr = merged.get("contour", [])
            settings = {key: value for key, value in merged.items() if key not in {"contour", "sprayPattern"}}
            settings["height_mm"] = workpiece_height_mm
            if not isinstance(contour_arr, np.ndarray):
                contour_arr = np.array(contour_arr, dtype=np.float32)
            if contour_arr.size != 0:
                pts_px = contour_arr.reshape(-1, 2)
                self._logger.info("[EXECUTE] Workpiece: %d pixel points | settings=%s", len(pts_px), settings)
                robot_pts = self._transform_to_robot(pts_px, settings)
                if robot_pts:
                    robot_paths.append((robot_pts, settings, "Workpiece"))
        else:
            for pattern_type in ("Contour", "Fill"):
                for i, pattern in enumerate(spray_pattern.get(pattern_type, [])):
                    contour_arr = pattern.get("contour", [])
                    settings = dict(pattern.get("settings", {}) or {})
                    settings["height_mm"] = workpiece_height_mm
                    if not isinstance(contour_arr, np.ndarray):
                        contour_arr = np.array(contour_arr, dtype=np.float32)
                    if contour_arr.size == 0:
                        continue
                    pts_px = contour_arr.reshape(-1, 2)
                    self._logger.info("[EXECUTE] %s[%d]: %d pixel points | settings=%s", pattern_type, i, len(pts_px), settings)
                    robot_pts = self._transform_to_robot(pts_px, settings)
                    if robot_pts:
                        robot_paths.append((robot_pts, settings, pattern_type))

        if not robot_paths:
            raise ValueError("No executable paths after transformation")

        total_spline_pts = 0
        sampled_paths: list[list[list[float]]] = []
        raw_paths: list[list[list[float]]] = []
        prepared_paths: list[list[list[float]]] = []
        curve_paths: list[list[list[float]]] = []
        execution_jobs: list[dict] = []

        for path_pts, settings, pattern_type in robot_paths:
            raw_paths.append([list(pt) for pt in path_pts])
            vel = _safe_float(settings.get("velocity"), 60.0)
            acc = _safe_float(settings.get("acceleration"), 30.0)
            preprocess_spacing_mm, interpolation_spacing_mm, dense_sampling_factor, execution_spacing_mm = _resolve_segment_interpolation_settings(settings)
            tangent_lookahead_distance_mm, tangent_heading_deadband_deg = _resolve_segment_tangent_settings(settings)
            input_densify_spacing_mm = _auto_input_densify_spacing(path_pts, interpolation_spacing_mm)

            pipeline = ContourPathPipeline(
                preprocess=PreprocessConfig(
                    min_spacing=preprocess_spacing_mm,
                    max_segment_length=input_densify_spacing_mm,
                    noise_method="none",
                    noise_strength=0.0,
                ),
                interpolation=InterpolationConfig(
                    method="pchip",
                    output_spacing=interpolation_spacing_mm,
                    dense_sampling_factor=dense_sampling_factor,
                ),
                ruckig=RuckigConfig(enabled=False),
            )
            pipeline_result = pipeline.run(np.asarray(path_pts, dtype=float)[:, :2])
            prepared_path = rebuild_pose_path_from_xy(
                pipeline_result.prepared, path_pts, self._rz_mode,
                tangent_lookahead_distance_mm=tangent_lookahead_distance_mm,
                tangent_heading_deadband_deg=tangent_heading_deadband_deg,
            )
            curve_path = rebuild_pose_path_from_xy(
                pipeline_result.curve, path_pts, self._rz_mode,
                tangent_lookahead_distance_mm=tangent_lookahead_distance_mm,
                tangent_heading_deadband_deg=tangent_heading_deadband_deg,
            )
            sampled_path = rebuild_pose_path_from_xy(
                pipeline_result.sampled, path_pts, self._rz_mode,
                tangent_lookahead_distance_mm=tangent_lookahead_distance_mm,
                tangent_heading_deadband_deg=tangent_heading_deadband_deg,
            )
            execution_spline = _resample_execution_path(sampled_path, target_spacing_mm=execution_spacing_mm)
            total_spline_pts += len(execution_spline)
            prepared_paths.append([list(pt) for pt in prepared_path])
            curve_paths.append([list(pt) for pt in curve_path])
            sampled_paths.append([list(pt) for pt in sampled_path])

            if pickup_px is not None and pickup_xy is None:
                pickup_camera_xy = self._transform_single_pixel_to_robot(
                    float(pickup_px[0]), float(pickup_px[1]),
                    {"height_mm": workpiece_height_mm, **merged},
                    target_point_name=self._target_point_name,
                    frame_name=self._calibration_frame_name,
                    rz_override=0.0,
                )
                pickup_rz = compute_pickup_rz_from_robot_path(execution_spline, pickup_camera_xy)
                pickup_xy = self._transform_single_pixel_to_robot(
                    float(pickup_px[0]), float(pickup_px[1]),
                    {"height_mm": workpiece_height_mm, **merged},
                    target_point_name=self._pickup_target_point_name,
                    frame_name=self._calibration_frame_name,
                    rz_override=pickup_rz,
                )

            execution_jobs.append(
                {
                    "path": [list(pt) for pt in sampled_path],
                    "execution_path": [list(pt) for pt in execution_spline],
                    "vel": vel,
                    "acc": acc,
                    "pattern_type": pattern_type,
                    "workpiece_height_mm": float(workpiece_height_mm),
                    "pickup_xy": [float(pickup_xy[0]), float(pickup_xy[1])] if pickup_xy is not None else None,
                    "pickup_rz": float(pickup_rz),
                    "pickup_target_point_name": str(self._pickup_target_point_name or "").strip().lower(),
                }
            )

        return WorkpieceExecutionPlan(
            workpiece=dict(merged),
            raw_paths=raw_paths,
            prepared_paths=prepared_paths,
            curve_paths=curve_paths,
            sampled_paths=sampled_paths,
            execution_jobs=execution_jobs,
            total_spline_pts=total_spline_pts,
        )

    def _transform_to_robot(self, pts_px: np.ndarray, settings: dict) -> list:
        try:
            defaults = self._segment_config.schema.get_defaults()
            spray_height = float(str(settings.get("spraying_height", defaults.get("spraying_height", "0"))).replace(",", ""))
            base_position = self._resolve_base_position()
            base_z = base_position[2] + spray_height if base_position is not None else self._z_min + spray_height
            rz_offset = float(settings.get("rz_angle", defaults.get("rz_angle", "0")))
            workpiece_height_mm = _safe_float(settings.get("height_mm"), _DEFAULT_WORKPIECE_HEIGHT_MM)
        except (ValueError, TypeError):
            raise ValueError("Invalid segment settings: spraying_height and rz_angle must be numbers")
        rx, ry = 180.0, 0.0
        robot_xy_points: list[tuple[float, float]] = []
        compensated_pts_px = np.asarray(pts_px, dtype=np.float64).copy()

        if callable(self._pixel_height_compensation_fn) and abs(workpiece_height_mm) > 1e-9:
            try:
                compensation_dx_px, compensation_dy_px = self._pixel_height_compensation_fn(workpiece_height_mm)
                compensated_pts_px[:, 0] -= float(compensation_dx_px)
                compensated_pts_px[:, 1] -= float(compensation_dy_px)
                self._logger.info(
                    "[EXECUTE] Applied pixel height compensation: height_mm=%.3f pixel_delta=(%.6f, %.6f)",
                    workpiece_height_mm,
                    float(compensation_dx_px),
                    float(compensation_dy_px),
                )
            except Exception:
                self._logger.exception("[EXECUTE] Failed to apply pixel height compensation")

        if self._resolver is not None:
            from src.engine.robot.targeting import VisionPoseRequest

            target_point = self._resolver.registry.by_name(self._target_point_name)
            seeded_results = [
                self._resolver.resolve(
                    VisionPoseRequest(
                        float(px),
                        float(py),
                        z_mm=base_z,
                        rz_degrees=rz_offset,
                        rx_degrees=rx,
                        ry_degrees=ry,
                    ),
                    target_point,
                )
                for px, py in compensated_pts_px
            ]
            robot_xy_points = [
                (float(result.final_xy[0]), float(result.final_xy[1]))
                for result in seeded_results
            ]
        else:
            seeded_results = None
            if self._transformer is None or not self._transformer.is_available():
                self._logger.warning("[EXECUTE] No calibration transformer — using raw pixel coords")
            for px, py in compensated_pts_px:
                if self._transformer is not None and self._transformer.is_available():
                    rx_coord, ry_coord = self._transformer.transform(float(px), float(py))
                else:
                    rx_coord, ry_coord = float(px), float(py)
                robot_xy_points.append((float(rx_coord), float(ry_coord)))

        from src.engine.robot.path_preparation.geometry import compute_path_aligned_rz_degrees
        if self._rz_mode == "path_tangent":
            rz_values = compute_path_aligned_rz_degrees(robot_xy_points, base_rz_offset_degrees=rz_offset)
        else:
            rz_values = [float(rz_offset) for _ in robot_xy_points]

        if seeded_results is not None:
            result = [
                [float(x), float(y), float(seed.z), rx, ry, float(rz)]
                for seed, (x, y), rz in zip(seeded_results, robot_xy_points, rz_values)
            ]
        else:
            result = [
                [float(x), float(y), float(base_z), rx, ry, float(rz)]
                for (x, y), rz in zip(robot_xy_points, rz_values)
            ]
        if result:
            self._logger.debug(
                "[EXECUTE] RZ mode=%s first headings=%s",
                self._rz_mode,
                [round(float(point[5]), 3) for point in result[: min(5, len(result))]],
            )
        return result

    def _extract_pickup_pixel(self, merged: dict) -> tuple[float, float] | None:
        pickup_point = (merged or {}).get("pickupPoint")
        parsed_pickup = self._parse_pickup_point(pickup_point)
        if parsed_pickup is not None:
            return parsed_pickup

        contour_arr = np.asarray((merged or {}).get("contour", []), dtype=np.float32)
        if contour_arr.size == 0:
            return None
        contour_pts = contour_arr.reshape(-1, 1, 2)
        moments = cv2.moments(contour_pts)
        if abs(float(moments.get("m00", 0.0))) > 1e-9:
            cx = float(moments["m10"] / moments["m00"])
            cy = float(moments["m01"] / moments["m00"])
            return cx, cy
        flat_pts = contour_pts.reshape(-1, 2)
        return float(np.mean(flat_pts[:, 0])), float(np.mean(flat_pts[:, 1]))

    @staticmethod
    def _parse_pickup_point(value) -> tuple[float, float] | None:
        if value is None:
            return None
        if isinstance(value, str):
            try:
                x_str, y_str = value.split(",", 1)
                return float(x_str), float(y_str)
            except (TypeError, ValueError):
                return None
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            try:
                return float(value[0]), float(value[1])
            except (TypeError, ValueError):
                return None
        if isinstance(value, dict):
            try:
                return float(value["x"]), float(value["y"])
            except (KeyError, TypeError, ValueError):
                return None
        return None

    def _transform_single_pixel_to_robot(
        self,
        px: float,
        py: float,
        settings: dict,
        *,
        target_point_name: str | None = None,
        frame_name: str = "",
        rz_override: float | None = None,
    ) -> tuple[float, float]:
        workpiece_height_mm = _safe_float(settings.get("height_mm"), _DEFAULT_WORKPIECE_HEIGHT_MM)
        compensated_px = float(px)
        compensated_py = float(py)

        if callable(self._pixel_height_compensation_fn) and abs(workpiece_height_mm) > 1e-9:
            dx_px, dy_px = self._pixel_height_compensation_fn(workpiece_height_mm)
            compensated_px -= float(dx_px)
            compensated_py -= float(dy_px)

        try:
            defaults = self._segment_config.schema.get_defaults()
            spray_height = float(str(settings.get("spraying_height", defaults.get("spraying_height", "0"))).replace(",", ""))
            rz_offset = float(settings.get("rz_angle", defaults.get("rz_angle", "0")))
        except (ValueError, TypeError):
            spray_height = 0.0
            rz_offset = 0.0
        if rz_override is not None:
            rz_offset = float(rz_override)

        base_position = self._resolve_base_position()
        base_z = base_position[2] + spray_height if base_position is not None else self._z_min + spray_height

        if self._resolver is not None:
            from src.engine.robot.targeting import VisionPoseRequest

            resolved_target_name = str(target_point_name or self._target_point_name or "").strip().lower()
            target_point = self._resolver.registry.by_name(resolved_target_name)
            result = self._resolver.resolve(
                VisionPoseRequest(
                    compensated_px,
                    compensated_py,
                    z_mm=base_z,
                    rz_degrees=rz_offset,
                    rx_degrees=180.0,
                    ry_degrees=0.0,
                ),
                target_point,
                frame=str(frame_name or "").strip().lower(),
            )
            return float(result.final_xy[0]), float(result.final_xy[1])

        if self._transformer is None or not self._transformer.is_available():
            return compensated_px, compensated_py

        rx_coord, ry_coord = self._transformer.transform(compensated_px, compensated_py)
        return float(rx_coord), float(ry_coord)

    def _resolve_base_position(self) -> Optional[list[float]]:
        provider = self._base_position_provider
        if provider is None:
            return None
        try:
            position = provider()
        except Exception:
            self._logger.debug("Path preparation base position lookup failed", exc_info=True)
            return None
        if not position or len(position) < 3:
            return None
        try:
            return [float(position[i]) for i in range(6 if len(position) >= 6 else len(position))]
        except (TypeError, ValueError):
            return None
