from __future__ import annotations

import json

import cv2
import numpy as np

from src.engine.robot.calibration.robot_calibration.calibration_report import (
    derive_calibration_artifact_paths,
)
from src.engine.robot.path_preparation.pixel_to_mm.context import PixelToMmContext
from src.engine.robot.targeting import VisionPoseRequest


class GeometryPpmAnchorStrategy:
    """Convert pixels using one resolver anchor plus geometry PPM offsets."""

    def convert(
        self,
        compensated_pts_px: np.ndarray,
        *,
        resolver,
        context: PixelToMmContext,
    ) -> tuple[list, list[tuple[float, float]]] | None:
        points = np.asarray(compensated_pts_px, dtype=np.float64).reshape(-1, 2)
        if points.shape[0] < 2:
            return None

        ppm = self._load_geometry_ppm(resolver, context)
        if ppm is None or ppm <= 1e-9:
            return None

        anchor_px = self._compute_pixel_anchor(points)
        axes = self._geometry_axes_from_homography(resolver, anchor_px, context)
        if axes is None:
            context.logger.warning("[EXECUTE] Geometry PPM available but homography direction basis is unavailable")
            return None

        target_point = resolver.registry.by_name(context.target_point_name)
        anchor_result = resolver.resolve(
            VisionPoseRequest(
                float(anchor_px[0]),
                float(anchor_px[1]),
                z_mm=context.base_z,
                rz_degrees=context.rz_offset,
                rx_degrees=context.rx,
                ry_degrees=context.ry,
            ),
            target_point,
            frame=context.calibration_frame_name,
        )
        anchor_xy = np.asarray(anchor_result.final_xy, dtype=np.float64).reshape(2)
        x_axis, y_axis = axes
        mm_per_px = 1.0 / float(ppm)

        robot_xy = []
        for point_px in points:
            delta_px = point_px - anchor_px
            delta_robot = (delta_px[0] * mm_per_px * x_axis) + (delta_px[1] * mm_per_px * y_axis)
            xy = anchor_xy + delta_robot
            robot_xy.append((float(xy[0]), float(xy[1])))

        seeded_results = [anchor_result for _ in robot_xy]
        if robot_xy:
            xy_arr = np.asarray(robot_xy, dtype=np.float64)
            bbox = np.ptp(xy_arr, axis=0)
            context.logger.info(
                "[EXECUTE] Geometry transform: mode=ppm_anchor ppm=%.6f mm_per_px=%.6f "
                "anchor_px=(%.3f, %.3f) anchor_robot_xy=(%.3f, %.3f) "
                "basis_x=(%.6f, %.6f) basis_y=(%.6f, %.6f) "
                "bbox_robot_mm=(%.3f x %.3f) points=%d",
                float(ppm),
                float(mm_per_px),
                float(anchor_px[0]),
                float(anchor_px[1]),
                float(anchor_xy[0]),
                float(anchor_xy[1]),
                float(x_axis[0]),
                float(x_axis[1]),
                float(y_axis[0]),
                float(y_axis[1]),
                float(bbox[0]),
                float(bbox[1]),
                len(robot_xy),
            )
        return seeded_results, robot_xy

    @staticmethod
    def _load_geometry_ppm(resolver, context: PixelToMmContext) -> float | None:
        matrix_path = GeometryPpmAnchorStrategy._resolver_matrix_path(resolver)
        if not matrix_path:
            return None
        if context.geometry_scale_cache.entry is not None and context.geometry_scale_cache.entry[0] == matrix_path:
            return context.geometry_scale_cache.entry[1]

        geometry_path = derive_calibration_artifact_paths(matrix_path)["geometry_scale_path"]
        try:
            with open(geometry_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            ppm = float(payload.get("ppm"))
            if ppm <= 0.0:
                return None
            context.geometry_scale_cache.entry = (matrix_path, ppm)
            context.logger.info("[EXECUTE] Loaded geometry PPM %.6f from %s", ppm, geometry_path)
            return ppm
        except Exception:
            context.logger.debug("[EXECUTE] Geometry PPM artifact unavailable at %s", geometry_path, exc_info=True)
            return None

    @staticmethod
    def _resolver_matrix_path(resolver) -> str | None:
        base = getattr(resolver, "_base", None)
        matrix_path = getattr(base, "_matrix_path", None)
        if matrix_path:
            return str(matrix_path)
        nested_base = getattr(base, "_base", None)
        matrix_path = getattr(nested_base, "_matrix_path", None)
        return str(matrix_path) if matrix_path else None

    @staticmethod
    def _compute_pixel_anchor(points: np.ndarray) -> np.ndarray:
        pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
        if pts.shape[0] >= 3:
            contour = np.ascontiguousarray(pts.astype(np.float32).reshape(-1, 1, 2))
            moments = cv2.moments(contour)
            if abs(float(moments.get("m00", 0.0))) > 1e-9:
                return np.asarray(
                    [
                        float(moments["m10"] / moments["m00"]),
                        float(moments["m01"] / moments["m00"]),
                    ],
                    dtype=np.float64,
                )
        return np.mean(pts, axis=0)

    @staticmethod
    def _geometry_axes_from_homography(
        resolver,
        anchor_px: np.ndarray,
        context: PixelToMmContext,
    ) -> tuple[np.ndarray, np.ndarray] | None:
        homography_matrix = GeometryPpmAnchorStrategy._base_homography_matrix(resolver)
        if homography_matrix is None:
            return None

        anchor = np.asarray(anchor_px, dtype=np.float64).reshape(2)
        probe = np.asarray(
            [
                anchor,
                anchor + np.asarray([1.0, 0.0], dtype=np.float64),
                anchor + np.asarray([0.0, 1.0], dtype=np.float64),
            ],
            dtype=np.float32,
        ).reshape(-1, 1, 2)
        mapped = cv2.perspectiveTransform(
            probe,
            np.asarray(homography_matrix, dtype=np.float64).reshape(3, 3),
        ).reshape(-1, 2).astype(np.float64)

        frame_obj = resolver.get_frame(context.calibration_frame_name) if context.calibration_frame_name else None
        mapper = getattr(frame_obj, "mapper", None) if frame_obj is not None else None
        if mapper is not None:
            mapped = np.asarray([mapper.map_point(float(x), float(y)) for x, y in mapped], dtype=np.float64)

        jacobian = np.column_stack((mapped[1] - mapped[0], mapped[2] - mapped[0]))
        if not np.all(np.isfinite(jacobian)):
            return None
        try:
            u, _, vt = np.linalg.svd(jacobian)
        except np.linalg.LinAlgError:
            return None
        basis = u @ vt
        x_axis = basis[:, 0]
        y_axis = basis[:, 1]
        x_norm = float(np.linalg.norm(x_axis))
        y_norm = float(np.linalg.norm(y_axis))
        if x_norm <= 1e-12 or y_norm <= 1e-12:
            return None
        return x_axis / x_norm, y_axis / y_norm

    @staticmethod
    def _base_homography_matrix(resolver):
        base = getattr(resolver, "_base", None)
        model = getattr(base, "_model", None)
        homography_matrix = getattr(model, "homography_matrix", None)
        if homography_matrix is not None:
            return homography_matrix

        nested_base = getattr(base, "_base", None)
        model = getattr(nested_base, "_model", None)
        return getattr(model, "homography_matrix", None)
