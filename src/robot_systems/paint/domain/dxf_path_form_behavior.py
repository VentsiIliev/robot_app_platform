from __future__ import annotations

from typing import Callable

import numpy as np
from PyQt6.QtWidgets import QFileDialog

from contour_editor.ui.form_field_hooks import (
    install_line_edit_click_action,
    set_form_field_value,
)


class PaintDxfPathFormBehavior:
    """
    Paint-specific behavior for the `dxfPath` field.

    Clicking the field opens a DXF picker, maps the DXF into image space for the
    current camera view, and renders it as a non-destructive verification overlay.
    """

    def __init__(
        self,
        *,
        prepare_dxf_raw_for_image: Callable[[dict, float, float], dict],
        dxf_importer: Callable[[str], dict],
        dxf_alignment_strategy: str = "rigid",
        dxf_max_scale_deviation: float = 0.03,
    ) -> None:
        self._prepare_dxf_raw_for_image = prepare_dxf_raw_for_image
        self._dxf_importer = dxf_importer
        self._dxf_alignment_strategy = str(dxf_alignment_strategy or "rigid").strip().lower()
        self._dxf_max_scale_deviation = float(dxf_max_scale_deviation)

    def apply(self, form, editor_frame) -> None:
        install_line_edit_click_action(
            form,
            "dxfPath",
            lambda: self._pick_and_preview(form, editor_frame),
            placeholder="Click to choose DXF",
            read_only=True,
        )

    def _pick_and_preview(self, form, editor_frame) -> None:
        current_path = ""
        try:
            current_path = str(form.get_data().get("dxfPath", "") or "")
        except Exception:
            current_path = ""

        dxf_path, _ = QFileDialog.getOpenFileName(
            editor_frame,
            "Select DXF",
            current_path,
            "DXF Files (*.dxf)",
        )
        if not dxf_path:
            return

        raw = self._dxf_importer(dxf_path)
        image_w, image_h = self._resolve_image_size(editor_frame)
        placed = self._prepare_dxf_raw_for_image(raw, image_w, image_h)
        target_contour = self._get_current_editor_contour(editor_frame)
        if len(target_contour) >= 3:
            placed = self._align_raw_workpiece_to_contour(placed, target_contour)
        points = self._extract_raw_contour_points(placed)
        editor_frame.set_verification_contours([points] if len(points) >= 2 else [])
        set_form_field_value(form, "dxfPath", dxf_path)

    @staticmethod
    def _resolve_image_size(editor_frame) -> tuple[float, float]:
        try:
            image = editor_frame.contourEditor.editor_with_rulers.editor.image
            width_getter = getattr(image, "width", None)
            height_getter = getattr(image, "height", None)
            if callable(width_getter) and callable(height_getter):
                width = float(width_getter())
                height = float(height_getter())
                if width > 0.0 and height > 0.0:
                    return width, height
        except Exception:
            pass
        return 1280.0, 720.0

    @staticmethod
    def _extract_raw_contour_points(raw: dict) -> np.ndarray:
        contour = raw.get("contour") or []
        points = [point[0] for point in contour if point and point[0]]
        if not points:
            return np.empty((0, 2), dtype=np.float64)
        return np.asarray([[float(point[0]), float(point[1])] for point in points], dtype=np.float64)

    @staticmethod
    def _get_current_editor_contour(editor_frame) -> np.ndarray:
        try:
            workpiece_manager = editor_frame.contourEditor.editor_with_rulers.editor.workpiece_manager
            contours_by_layer = workpiece_manager.get_contours() or {}
        except Exception:
            return np.empty((0, 2), dtype=np.float64)

        main_layer = contours_by_layer.get("Main") or contours_by_layer.get("Workpiece") or []
        if isinstance(main_layer, dict):
            main_layer = main_layer.get("contours") or []
        if not main_layer:
            return np.empty((0, 2), dtype=np.float64)

        contour = np.asarray(main_layer[0], dtype=np.float64)
        if contour.ndim == 3 and contour.shape[1] == 1:
            contour = contour[:, 0, :]
        if contour.ndim != 2 or contour.shape[1] < 2:
            return np.empty((0, 2), dtype=np.float64)
        return contour[:, :2]

    def _align_raw_workpiece_to_contour(self, raw: dict, captured_contour: np.ndarray) -> dict:
        from src.robot_systems.paint.processes.paint.workpiece_alignment import align_raw_workpiece_to_contour

        return align_raw_workpiece_to_contour(
            raw,
            captured_contour,
            strategy=self._dxf_alignment_strategy,
            max_scale_deviation=self._dxf_max_scale_deviation,
        )

    @staticmethod
    def _resample_closed_path(points: np.ndarray, count: int) -> np.ndarray:
        if len(points) < 2:
            return points
        closed_points = points
        if np.linalg.norm(points[0] - points[-1]) > 1e-6:
            closed_points = np.vstack([points, points[0]])
        segment_lengths = np.linalg.norm(np.diff(closed_points, axis=0), axis=1)
        total_length = float(np.sum(segment_lengths))
        if total_length <= 1e-9:
            return closed_points[:-1]
        cumulative = np.concatenate([[0.0], np.cumsum(segment_lengths)])
        samples = np.linspace(0.0, total_length, num=max(int(count), 3), endpoint=False)
        resampled = []
        seg_index = 0
        for sample in samples:
            while seg_index + 1 < len(cumulative) and cumulative[seg_index + 1] < sample:
                seg_index += 1
            seg_start = closed_points[seg_index]
            seg_end = closed_points[seg_index + 1]
            seg_len = segment_lengths[seg_index]
            if seg_len <= 1e-9:
                resampled.append(seg_start.copy())
                continue
            ratio = (sample - cumulative[seg_index]) / seg_len
            resampled.append(seg_start + ratio * (seg_end - seg_start))
        return np.asarray(resampled, dtype=np.float64)

    @staticmethod
    def _principal_axis_angle(points: np.ndarray) -> float:
        if len(points) < 2:
            return 0.0
        covariance = np.cov(points.T)
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        axis = eigenvectors[:, int(np.argmax(eigenvalues))]
        return float(np.arctan2(axis[1], axis[0]))

    @staticmethod
    def _rotate_points(points: np.ndarray, center: np.ndarray, theta: float) -> np.ndarray:
        rotation = np.array(
            [
                [np.cos(theta), -np.sin(theta)],
                [np.sin(theta), np.cos(theta)],
            ],
            dtype=np.float64,
        )
        return (points - center) @ rotation.T + center

    @staticmethod
    def _rotate_and_scale_points(points: np.ndarray, center: np.ndarray, theta: float, scale: float) -> np.ndarray:
        rotation = np.array(
            [
                [np.cos(theta), -np.sin(theta)],
                [np.sin(theta), np.cos(theta)],
            ],
            dtype=np.float64,
        )
        return ((points - center) @ rotation.T) * float(scale) + center

    @classmethod
    def _transform_points(
        cls,
        points: np.ndarray,
        center: np.ndarray,
        theta: float,
        scale: float,
        translation: np.ndarray,
    ) -> np.ndarray:
        return cls._rotate_and_scale_points(points, center, theta, scale) + translation

    @staticmethod
    def _estimate_uniform_scale(source_centered: np.ndarray, target_centered: np.ndarray) -> float:
        source_norm = float(np.sqrt(np.sum(source_centered * source_centered)))
        target_norm = float(np.sqrt(np.sum(target_centered * target_centered)))
        if source_norm <= 1e-9 or target_norm <= 1e-9:
            return 1.0
        return max(1e-3, target_norm / source_norm)

    @staticmethod
    def _alignment_error(source_points: np.ndarray, target_points: np.ndarray) -> float:
        if len(source_points) == 0 or len(target_points) == 0:
            return float("inf")
        deltas = source_points[:, None, :] - target_points[None, :, :]
        distances = np.linalg.norm(deltas, axis=2)
        return float(np.mean(np.min(distances, axis=1)))

    @staticmethod
    # TODO NEED BETTER WAY TO GET THE SCALE !
    def _refine_alignment_with_mask_overlap(
        source_points: np.ndarray,
        target_points: np.ndarray,
        source_centroid: np.ndarray,
        initial_theta: float,
        initial_scale: float,
        initial_translation: np.ndarray,
        overlap_fn,
    ) -> tuple[float, float, np.ndarray]:
        best_theta = float(initial_theta)
        best_scale = max(1e-3, float(initial_scale))
        best_translation = np.asarray(initial_translation, dtype=np.float64)
        best_overlap = PaintDxfPathFormBehavior._mask_overlap_for_pose(
            source_points,
            target_points,
            source_centroid,
            best_theta,
            best_scale,
            best_translation,
            overlap_fn,
        )

        rotation_steps_deg = [6.0, 2.0, 0.5]
        translation_steps_px = [12.0, 4.0, 1.5]
        scale_steps = [0.10, 0.03, 0.01]

        for rotation_step_deg, translation_step_px, scale_step in zip(rotation_steps_deg, translation_steps_px, scale_steps):
            improved = True
            while improved:
                improved = False
                candidates: list[tuple[float, float, np.ndarray]] = [
                    (best_theta - np.deg2rad(rotation_step_deg), best_scale, best_translation),
                    (best_theta + np.deg2rad(rotation_step_deg), best_scale, best_translation),
                    (best_theta, max(1e-3, best_scale * (1.0 - scale_step)), best_translation),
                    (best_theta, best_scale * (1.0 + scale_step), best_translation),
                    (best_theta, best_scale, best_translation + np.array([translation_step_px, 0.0], dtype=np.float64)),
                    (best_theta, best_scale, best_translation + np.array([-translation_step_px, 0.0], dtype=np.float64)),
                    (best_theta, best_scale, best_translation + np.array([0.0, translation_step_px], dtype=np.float64)),
                    (best_theta, best_scale, best_translation + np.array([0.0, -translation_step_px], dtype=np.float64)),
                    (best_theta, best_scale, best_translation + np.array([translation_step_px, translation_step_px], dtype=np.float64)),
                    (best_theta, best_scale, best_translation + np.array([translation_step_px, -translation_step_px], dtype=np.float64)),
                    (best_theta, best_scale, best_translation + np.array([-translation_step_px, translation_step_px], dtype=np.float64)),
                    (best_theta, best_scale, best_translation + np.array([-translation_step_px, -translation_step_px], dtype=np.float64)),
                ]
                for candidate_theta, candidate_scale, candidate_translation in candidates:
                    overlap = PaintDxfPathFormBehavior._mask_overlap_for_pose(
                        source_points,
                        target_points,
                        source_centroid,
                        float(candidate_theta),
                        float(candidate_scale),
                        np.asarray(candidate_translation, dtype=np.float64),
                        overlap_fn,
                    )
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_theta = float(candidate_theta)
                        best_scale = float(candidate_scale)
                        best_translation = np.asarray(candidate_translation, dtype=np.float64)
                        improved = True
        return best_theta, best_scale, best_translation

    @staticmethod
    def _mask_overlap_for_pose(
        source_points: np.ndarray,
        target_points: np.ndarray,
        source_centroid: np.ndarray,
        theta: float,
        scale: float,
        translation: np.ndarray,
        overlap_fn,
    ) -> float:
        transformed = PaintDxfPathFormBehavior._transform_points(
            source_points,
            source_centroid,
            theta,
            scale,
            translation,
        )
        return float(overlap_fn(transformed, target_points))
