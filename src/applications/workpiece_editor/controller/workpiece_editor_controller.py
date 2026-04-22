import logging
from typing import List, Tuple, Callable
import copy

import numpy as np
import cv2

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QLabel, QScrollArea, QVBoxLayout, QPushButton, QHBoxLayout, QFileDialog

from src.applications.base.i_application_controller import IApplicationController
from src.applications.workpiece_editor.model import WorkpieceEditorModel
from src.applications.workpiece_editor.view.workpiece_editor_view import WorkpieceEditorView
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.vision_events import VisionTopics
from src.applications.base.styled_message_box import show_warning, show_info, show_critical
from src.shared_contracts.events.workpiece_events import WorkpieceTopics

_DEFAULT_WORKPIECE_HEIGHT_MM = 0.0


class _Bridge(QObject):
    camera_frame       = pyqtSignal(object)
    load_workpiece_raw = pyqtSignal(dict)


class WorkpieceEditorController(IApplicationController):

    def __init__(self, model: WorkpieceEditorModel, view: WorkpieceEditorView,
                 messaging: IMessagingService):
        self._model          = model
        self._view           = view
        self._broker         = messaging
        self._bridge         = _Bridge()
        self._subs:          List[Tuple[str, Callable]] = []
        self._active         = False
        self._camera_active  = True          # ← controls whether feed updates are forwarded
        self._logger         = logging.getLogger(self.__class__.__name__)
        self._preview_dialog = None
        self._latest_frame_shape = None
        self._dxf_test_button = None
        self._current_dxf_path = ""
        self._captured_pickup_point = None

    def load(self) -> None:
        self._active        = True
        self._camera_active = True
        self._bridge.camera_frame.connect(self._on_camera_frame)
        self._bridge.load_workpiece_raw.connect(self._on_load_workpiece_raw)
        self._view.set_capture_handler(self._on_capture)   # ← renamed
        self._view.set_save_callback(self._on_form_submit)
        self._install_optional_actions()
        self._connect_signals()
        self._subscribe()
        self._view.destroyed.connect(self.stop)
        self._connect_segment_added()

    def stop(self) -> None:
        self._active = False
        try:
            self._bridge.camera_frame.disconnect()
        except (RuntimeError, TypeError):
            pass

        try:
            self._bridge.load_workpiece_raw.disconnect()
        except (RuntimeError, TypeError):
            pass

        for topic, cb in reversed(self._subs):
            try:
                self._broker.unsubscribe(topic, cb)
            except Exception:
                pass

        try:
            inner = self._view._editor.contourEditor.editor_with_rulers.editor
            bus = getattr(inner, '_event_bus', None)
            if bus is not None and hasattr(bus, 'segment_added'):
                try:
                    bus.segment_added.disconnect(self._on_segment_added)
                except (RuntimeError, TypeError):
                    pass
        except Exception:
            pass

        self._subs.clear()

    # ── Capture ───────────────────────────────────────────────────────

    def _on_capture(self) -> list:
        """Called by the editor's capture button. Picks the largest contour,
        stops the live feed and loads the contour into the Workpiece layer."""
        contours = self._model.get_contours()
        self._logger.debug("Capture: got %d contours from vision", len(contours))
        largest = self._pick_largest(contours)
        if largest is None:
            self._logger.warning("Capture: no usable contour found")
            show_warning(self._view, "Capture", "No contour detected.\nMake sure the vision vision_service is running.")
            return []

        self._logger.debug("Capture: largest contour has %d points", len(largest))

        # Stop live camera feed so the captured frame stays visible
        self._camera_active = False
        self._current_dxf_path = ""
        self._captured_pickup_point = self._compute_contour_centroid(largest)
        self._clear_verification_overlay()

        known_raw = self._try_prepare_known_workpiece_capture(largest)
        if known_raw is not None:
            try:
                self._load_raw_into_editor(known_raw, storage_id=None)
                self._view._editor.set_verification_contours([self._normalize_contour_points(largest)])
                return [largest]
            except Exception:
                self._logger.exception("Capture: failed to load matched DXF workpiece")

        try:
            self._load_capture_contour_into_editor(largest)
            self._set_pickup_point_overlay()
        except Exception:
            self._logger.exception("Capture: failed to load contour into editor")

        return [largest]

    @staticmethod
    def _pick_largest(contours: list):
        import cv2
        import numpy as np
        if not contours:
            return None
        best, best_area = None, -1.0
        for c in contours:
            try:
                arr = np.array(c, dtype=np.float32)
                area = float(cv2.contourArea(arr))
                if area > best_area:
                    best_area = area
                    best = arr
            except Exception:
                import traceback
                traceback.print_exc()
                continue
        return best

    # ── Broker → Bridge ───────────────────────────────────────────────

    def _subscribe(self) -> None:
        self._sub(VisionTopics.LATEST_IMAGE, self._on_latest_image_raw)
        self._sub(WorkpieceTopics.OPEN_IN_EDITOR, self._on_open_in_editor_raw)

    def _on_latest_image_raw(self, msg) -> None:
        if isinstance(msg, dict):
            frame = msg.get("image")
            if frame is not None:
                self._bridge.camera_frame.emit(frame)

    def _on_camera_frame(self, frame) -> None:
        if not self._active or not self._camera_active or frame is None:
            return
        try:
            self._latest_frame_shape = tuple(frame.shape)
        except Exception:
            self._latest_frame_shape = None
        try:
            import cv2
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        except Exception:
            rgb = frame
        self._view.update_camera_feed(rgb)

    # ── View → Model ──────────────────────────────────────────────────

    def _on_form_submit(self, form_data: dict):
        form_data = self._augment_form_data_with_editor_context(form_data)
        try:
            inner = self._view._editor.contourEditor.editor_with_rulers.editor
            editor_data = inner.workpiece_manager.export_editor_data()
        except Exception:
            editor_data = None

        data = {"form_data": form_data, "editor_data": editor_data}
        ok, msg = self._model.save_workpiece(data)
        self._logger.info("Save workpiece: %s — %s", ok, msg)
        if not ok:
            show_warning(self._view, "Cannot Save", msg)
            return False, msg
        # Resume live feed after successful save
        self._camera_active = True
        return True, msg

    def _connect_signals(self) -> None:
        self._view.save_requested.connect(self._on_save)
        self._view.execute_requested.connect(self._on_execute)

    def _set_verification_overlay_from_raw(self, raw: dict) -> None:
        try:
            points = self._extract_raw_contour_points(raw)
            overlays = [points] if len(points) >= 2 else []
            pickup_point = self._parse_pickup_point((raw or {}).get("pickupPoint"))
            if pickup_point is not None:
                overlays.extend(self._build_pickup_point_overlay(pickup_point))
            self._view._editor.set_verification_contours(overlays)
        except Exception:
            self._logger.debug("Failed to set DXF verification overlay", exc_info=True)

    def _resolve_image_size(self) -> tuple[float, float]:
        if self._latest_frame_shape is not None and len(self._latest_frame_shape) >= 2:
            return float(self._latest_frame_shape[1]), float(self._latest_frame_shape[0])
        return 1280.0, 720.0

    def _preview_aligned_dxf_from_path(self, dxf_path: str, captured_contour) -> bool:
        if not dxf_path:
            return False
        try:
            from src.engine.cad import import_dxf_to_workpiece_data

            raw = import_dxf_to_workpiece_data(dxf_path)
            image_w, image_h = self._resolve_image_size()
            placed = self._model.prepare_dxf_test_raw_for_image(raw, image_w, image_h)
            aligned = self._align_raw_workpiece_to_contour(placed, captured_contour)
            self._set_verification_overlay_from_raw(aligned)
            return True
        except Exception:
            self._logger.exception("Failed to prepare aligned DXF overlay from %s", dxf_path)
            return False

    def _clear_verification_overlay(self) -> None:
        try:
            self._view._editor.clear_verification_contours()
        except Exception:
            self._logger.debug("Failed to clear DXF verification overlay", exc_info=True)

    def _set_pickup_point_overlay(self) -> None:
        try:
            if self._captured_pickup_point is None:
                self._view._editor.set_verification_contours([])
                return
            self._view._editor.set_verification_contours(
                self._build_pickup_point_overlay(self._captured_pickup_point)
            )
        except Exception:
            self._logger.debug("Failed to set pickup point overlay", exc_info=True)

    def _install_optional_actions(self) -> None:
        if not self._model.can_import_dxf_test():
            return
        layout = self._view.layout()
        if layout is None:
            return
        row = QHBoxLayout()
        row.addStretch(1)
        load_button = QPushButton("Load DXF Test")
        load_button.clicked.connect(self._on_load_dxf_test)
        row.addWidget(load_button)
        align_button = QPushButton("Capture + Align DXF Test")
        align_button.clicked.connect(self._on_capture_align_dxf_test)
        row.addWidget(align_button)
        match_button = QPushButton("Match Workpiece Test")
        match_button.clicked.connect(self._on_match_workpiece_test)
        row.addWidget(match_button)
        layout.insertLayout(0, row)
        self._dxf_test_button = load_button

    def _on_load_dxf_test(self) -> None:
        dxf_path, _ = QFileDialog.getOpenFileName(
            self._view,
            "Load DXF Test",
            "",
            "DXF Files (*.dxf)",
        )
        if not dxf_path:
            return
        try:
            from src.engine.cad import import_dxf_to_workpiece_data

            raw = import_dxf_to_workpiece_data(dxf_path)
            image_w, image_h = self._resolve_image_size()
            placed = self._model.prepare_dxf_test_raw_for_image(raw, image_w, image_h)
            placed["dxfPath"] = str(dxf_path)
            self._current_dxf_path = str(dxf_path)
            self._clear_verification_overlay()
            self._on_load_workpiece_raw({"raw": placed, "storage_id": None})
            show_info(self._view, "DXF Loaded", f"Loaded test DXF:\n{dxf_path}")
        except Exception as exc:
            self._logger.exception("Failed to load DXF test file: %s", exc)
            show_warning(self._view, "DXF Load Failed", str(exc))

    def _on_capture_align_dxf_test(self) -> None:
        contours = self._model.get_contours()
        largest = self._pick_largest(contours)
        if largest is None:
            show_warning(self._view, "Capture", "No contour detected.")
            return

        dxf_path, _ = QFileDialog.getOpenFileName(
            self._view,
            "Capture + Align DXF Test",
            "",
            "DXF Files (*.dxf)",
        )
        if not dxf_path:
            return

        try:
            from src.engine.cad import import_dxf_to_workpiece_data

            raw = import_dxf_to_workpiece_data(dxf_path)
            image_w, image_h = self._resolve_image_size()
            placed = self._model.prepare_dxf_test_raw_for_image(raw, image_w, image_h)
            aligned = self._align_raw_workpiece_to_contour(placed, largest)
            aligned["dxfPath"] = str(dxf_path)
            self._current_dxf_path = str(dxf_path)
            self._camera_active = False
            self._clear_verification_overlay()
            self._on_load_workpiece_raw({"raw": aligned, "storage_id": None})
            show_info(self._view, "DXF Aligned", f"Captured contour and aligned DXF:\n{dxf_path}")
        except Exception as exc:
            self._logger.exception("Failed to capture and align DXF test file: %s", exc)
            show_warning(self._view, "DXF Align Failed", str(exc))

    def _on_match_workpiece_test(self) -> None:
        contours = self._model.get_contours()
        largest = self._pick_largest(contours)
        if largest is None:
            show_warning(self._view, "Match Workpiece", "No contour detected.")
            return

        if not self._model.can_match_saved_workpieces():
            show_warning(self._view, "Match Workpiece", "Matching is not available in this editor.")
            return

        try:
            ok, payload, msg = self._model.match_saved_workpieces(largest)
            if not ok or not payload:
                show_info(self._view, "Match Workpiece", msg)
                return

            self._camera_active = False
            self._clear_verification_overlay()
            self._on_load_workpiece_raw({"raw": payload["raw"], "storage_id": payload.get("storage_id")})
            dxf_overlay_loaded = self._preview_aligned_dxf_from_path(
                str((payload.get("raw") or {}).get("dxfPath", "") or ""),
                largest,
            )
            show_info(
                self._view,
                "Matched Workpiece",
                f"Matched: {payload.get('workpieceId') or '(no id)'}"
                + (f"\nName: {payload.get('name')}" if payload.get("name") else "")
                + (
                    f"\nConfidence: {float(payload.get('confidence')):.2f}"
                    if payload.get("confidence") is not None
                    else ""
                )
                + f"\nSaved workpieces checked: {payload.get('candidate_count', 0)}"
                + f"\nUnmatched contours: {payload.get('no_match_count', 0)}"
                + ("\nDXF overlay: aligned and shown" if dxf_overlay_loaded else "\nDXF overlay: unavailable"),
            )
        except Exception as exc:
            self._logger.exception("Failed to match saved workpieces: %s", exc)
            show_warning(self._view, "Match Workpiece Failed", str(exc))

    def _align_raw_workpiece_to_contour(self, raw: dict, captured_contour) -> dict:
        from src.robot_systems.paint.processes.workpiece_alignment import align_raw_workpiece_to_contour

        return align_raw_workpiece_to_contour(raw, captured_contour)

    @staticmethod
    def _extract_raw_contour_points(raw: dict) -> np.ndarray:
        contour = raw.get("contour") or []
        points = [point[0] for point in contour if point and point[0]]
        if not points:
            return np.empty((0, 2), dtype=np.float64)
        return np.asarray([[float(point[0]), float(point[1])] for point in points], dtype=np.float64)

    @staticmethod
    def _normalize_contour_points(contour) -> np.ndarray:
        array = np.asarray(contour, dtype=np.float64)
        if array.ndim == 3 and array.shape[1] == 1:
            array = array[:, 0, :]
        if array.ndim != 2 or array.shape[1] < 2:
            return np.empty((0, 2), dtype=np.float64)
        return array[:, :2]

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
        best_overlap = WorkpieceEditorController._mask_overlap_for_pose(
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
                    overlap = WorkpieceEditorController._mask_overlap_for_pose(
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
        transformed = WorkpieceEditorController._transform_points(
            source_points,
            source_centroid,
            theta,
            scale,
            translation,
        )
        return float(overlap_fn(transformed, target_points))

    def _on_save(self, data: dict) -> None:
        data = self._augment_form_data_with_editor_context(data)
        ok, msg = self._model.save_workpiece(data)
        self._logger.info("Save workpiece (fallback): %s — %s", ok, msg)
        if not ok:
            show_warning(self._view, "Cannot Save", msg)

    def _on_execute(self, data: dict) -> None:
        self._restore_live_feed()
        try:
            inner = self._view._editor.contourEditor.editor_with_rulers.editor
            editor_data = inner.workpiece_manager.export_editor_data()
        except Exception:
            editor_data = None
        payload = {"form_data": data, "editor_data": editor_data}
        ok, msg = self._model.execute_workpiece(payload)
        self._logger.info("Execute workpiece: %s — %s", ok, msg)
        if ok:
            try:
                raw_paths = self._model.get_last_raw_preview_paths()
                prepared_paths = self._model.get_last_prepared_preview_paths()
                curve_paths = self._model.get_last_curve_preview_paths()
                sampled_paths = self._model.get_last_sampled_preview_paths()
                execution_paths = self._model.get_last_execution_preview_paths()
                if raw_paths or sampled_paths:
                    self._show_interpolation_plot(
                        raw_paths,
                        prepared_paths,
                        curve_paths,
                        sampled_paths,
                        execution_paths,
                    )
            except Exception:
                self._logger.debug("Failed to show interpolation preview", exc_info=True)

    def _show_interpolation_plot(
        self,
        raw_paths: list[list[list[float]]],
        prepared_paths: list[list[list[float]]],
        curve_paths: list[list[list[float]]],
        sampled_paths: list[list[list[float]]],
        execution_paths: list[list[list[float]]],
    ) -> None:
        from src.engine.robot.path_interpolation.new_interpolation.debug_plotting import plot_trajectory_debug

        image_path = plot_trajectory_debug(
            raw_paths,
            curve_paths,
            sampled_paths,
            execution_paths,
            prepared_paths=prepared_paths,
        )
        if not image_path:
            return

        dialog = QDialog(self._view)
        dialog.setWindowTitle("Interpolation Pipeline Preview")
        dialog.resize(1100, 800)

        layout = QVBoxLayout(dialog)
        scroll = QScrollArea(dialog)
        image_label = QLabel(scroll)
        pixmap = QPixmap(image_path)
        image_label.setPixmap(pixmap)
        image_label.setScaledContents(False)
        scroll.setWidget(image_label)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        mode_labels = {
            "continuous": "Execute Continuous",
            "pose_path": "Execute Pose Path",
            "pivot_path": "Execute Pivot Path",
            "segmented": "Execute Segmented",
        }
        for mode in self._model.get_available_execution_modes():
            label = mode_labels.get(mode, f"Execute {str(mode).replace('_', ' ').title()}")
            button = QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, selected_mode=mode: self._on_execute_preview_confirmed(selected_mode)
            )
            button_row.addWidget(button)
        if self._model.can_execute_pickup_to_pivot():
            pickup_button = QPushButton("Pickup To Pivot")
            pickup_button.clicked.connect(self._on_execute_pickup_to_pivot)
            button_row.addWidget(pickup_button)
            pickup_and_paint_button = QPushButton("Pickup And Pivot Paint")
            pickup_and_paint_button.clicked.connect(self._on_execute_pickup_and_pivot_paint)
            button_row.addWidget(pickup_and_paint_button)
        layout.addLayout(button_row)

        self._preview_dialog = dialog
        dialog.show()

    def _on_execute_preview_confirmed(self, mode: str) -> None:
        self._restore_live_feed()
        if mode == "pivot_path":
            try:
                source_paths = self._model.get_last_execution_preview_paths()
                pivot_paths, pivot_pose = self._model.get_last_pivot_preview_paths()
                motion_snapshots, _ = self._model.get_last_pivot_motion_preview()
                if source_paths and pivot_paths:
                    self._show_pivot_path_plot(source_paths, pivot_paths, pivot_pose, motion_snapshots)
            except Exception:
                self._logger.debug("Failed to show pivot path preview", exc_info=True)
        ok, msg = self._model.execute_last_preview_paths(mode=mode)
        self._logger.info("Execute preview paths (%s): %s — %s", mode, ok, msg)
        if ok:
            show_info(self._preview_dialog or self._view, "Execution Started", msg)
        else:
            show_critical(self._preview_dialog or self._view, "Execution Failed", msg)

    def _on_execute_pickup_to_pivot(self) -> None:
        self._restore_live_feed()
        ok, msg = self._model.execute_pickup_to_pivot()
        self._logger.info("Execute pickup-to-pivot: %s — %s", ok, msg)
        if ok:
            show_info(self._preview_dialog or self._view, "Pickup To Pivot", msg)
        else:
            show_critical(self._preview_dialog or self._view, "Pickup To Pivot Failed", msg)

    def _on_execute_pickup_and_pivot_paint(self) -> None:
        self._restore_live_feed()
        ok, msg = self._model.execute_pickup_and_pivot_paint()
        self._logger.info("Execute pickup-and-pivot-paint: %s — %s", ok, msg)
        if ok:
            show_info(self._preview_dialog or self._view, "Pickup And Pivot Paint", msg)
        else:
            show_critical(self._preview_dialog or self._view, "Pickup And Pivot Paint Failed", msg)

    def _show_pivot_path_plot(
        self,
        source_paths: list[list[list[float]]],
        pivot_paths: list[list[list[float]]],
        pivot_pose: list[float] | None,
        motion_snapshots=None,
    ) -> None:
        from src.engine.robot.path_interpolation.new_interpolation.debug_plotting import plot_pivot_path_debug

        image_path = plot_pivot_path_debug(source_paths, pivot_paths, pivot_pose, motion_snapshots=motion_snapshots)
        if not image_path:
            return

        dialog = QDialog(self._view)
        dialog.setWindowTitle("Pivot Path Preview")
        dialog.resize(1000, 700)

        layout = QVBoxLayout(dialog)
        scroll = QScrollArea(dialog)
        image_label = QLabel(scroll)
        pixmap = QPixmap(image_path)
        image_label.setPixmap(pixmap)
        image_label.setScaledContents(False)
        scroll.setWidget(image_label)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        dialog.show()

    def _sub(self, topic: str, cb: Callable) -> None:
        self._broker.subscribe(topic, cb)
        self._subs.append((topic, cb))

    def _on_open_in_editor_raw(self, payload) -> None:
        if isinstance(payload, dict) and "storage_id" in payload:
            self._bridge.load_workpiece_raw.emit(payload)
        elif isinstance(payload, dict):
            self._bridge.load_workpiece_raw.emit({"raw": payload, "storage_id": None})

    def _on_load_workpiece_raw(self, payload: dict) -> None:
        if not self._active:
            return
        try:
            raw = payload.get("raw", payload)
            storage_id = payload.get("storage_id")
            self._clear_verification_overlay()
            self._load_raw_into_editor(raw, storage_id=storage_id)
        except Exception as exc:
            self._logger.exception("Failed to load workpiece: %s", exc)
            show_warning(self._view, "Load Failed", str(exc))

    def _augment_form_data_with_editor_context(self, form_data: dict) -> dict:
        enriched = dict(form_data or {})
        if self._current_dxf_path and not str(enriched.get("dxfPath", "")).strip():
            enriched["dxfPath"] = self._current_dxf_path
        if self._captured_pickup_point is not None and not enriched.get("pickupPoint"):
            enriched["pickupPoint"] = f"{float(self._captured_pickup_point[0]):.3f},{float(self._captured_pickup_point[1]):.3f}"
        enriched["height_mm"] = self._safe_float(enriched.get("height_mm"), _DEFAULT_WORKPIECE_HEIGHT_MM)
        return enriched

    def _load_capture_contour_into_editor(self, contour) -> None:
        from src.applications.workpiece_editor.editor_core.handlers.CaptureDataHandler import CaptureDataHandler

        editor_frame = self._view._editor
        inner = editor_frame.contourEditor.editor_with_rulers.editor
        wm = inner.workpiece_manager

        wm.clear_workpiece()
        editor_data = CaptureDataHandler.from_capture_data(
            contours=contour,
            metadata={"source": "camera_capture"},
        )
        wm.load_editor_data(editor_data, close_contour=True)
        editor_frame.pointManagerWidget.refresh_points()
        inner.update()

    def _load_raw_into_editor(self, raw: dict, storage_id=None) -> None:
        from src.applications.workpiece_editor.editor_core.adapters.workpiece_adapter import WorkpieceAdapter

        raw = self._normalize_workpiece_raw(raw)
        editor_data = WorkpieceAdapter.from_raw(raw)
        inner = self._view._editor.contourEditor.editor_with_rulers.editor
        inner.workpiece_manager.clear_workpiece()
        inner.workpiece_manager.load_editor_data(editor_data, close_contour=False)
        self._view._editor.contourEditor.data = raw
        self._model.set_editing(storage_id)
        self._current_dxf_path = str(raw.get("dxfPath", "") or "")
        if raw.get("pickupPoint"):
            self._captured_pickup_point = self._parse_pickup_point(raw.get("pickupPoint"))
        self._logger.info("Loaded workpiece into editor (storage_id=%s)", storage_id)
        try:
            self._view._editor.pointManagerWidget.refresh_points()
            inner.update()
        except Exception:
            self._logger.debug("Failed to refresh editor after loading workpiece", exc_info=True)
        self._set_pickup_point_overlay()

    @staticmethod
    def _compute_contour_centroid(contour) -> tuple[float, float] | None:
        try:
            contour_arr = np.asarray(contour, dtype=np.float32).reshape(-1, 1, 2)
            if contour_arr.size == 0:
                return None
            moments = cv2.moments(contour_arr)
            if abs(float(moments.get("m00", 0.0))) > 1e-9:
                return float(moments["m10"] / moments["m00"]), float(moments["m01"] / moments["m00"])
            flat_pts = contour_arr.reshape(-1, 2)
            return float(np.mean(flat_pts[:, 0])), float(np.mean(flat_pts[:, 1]))
        except Exception:
            return None

    @staticmethod
    def _build_pickup_point_overlay(pickup_point: tuple[float, float], size_px: float = 12.0) -> list[np.ndarray]:
        cx = float(pickup_point[0])
        cy = float(pickup_point[1])
        half = float(size_px) * 0.5
        horizontal = np.array(
            [[[cx - half, cy]], [[cx + half, cy]]],
            dtype=np.float32,
        )
        vertical = np.array(
            [[[cx, cy - half]], [[cx, cy + half]]],
            dtype=np.float32,
        )
        return [horizontal, vertical]

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

    @staticmethod
    def _safe_float(value, default: float) -> float:
        try:
            return float(str(value).replace(",", "")) if value is not None else default
        except (ValueError, TypeError):
            return default

    @classmethod
    def _normalize_workpiece_raw(cls, raw: dict) -> dict:
        normalized = dict(raw or {})
        normalized["height_mm"] = cls._safe_float(normalized.get("height_mm"), _DEFAULT_WORKPIECE_HEIGHT_MM)
        return normalized

    def _restore_live_feed(self) -> None:
        self._camera_active = True

    def _try_prepare_known_workpiece_capture(self, captured_contour) -> dict | None:
        if not self._model.can_match_saved_workpieces():
            return None
        try:
            ok, payload, _msg = self._model.match_saved_workpieces(captured_contour)
            if not ok or not payload:
                return None

            matched_raw = copy.deepcopy(payload.get("raw") or {})
            dxf_path = str(matched_raw.get("dxfPath", "") or "").strip()
            if not dxf_path:
                return matched_raw if matched_raw.get("contour") else None

            from src.engine.cad import import_dxf_to_workpiece_data

            image_w, image_h = self._resolve_image_size()
            dxf_raw = import_dxf_to_workpiece_data(dxf_path)
            placed = self._model.prepare_dxf_test_raw_for_image(dxf_raw, image_w, image_h)
            aligned = self._align_raw_workpiece_to_contour(placed, captured_contour)

            # Preserve saved metadata while replacing geometry with the aligned DXF.
            for key, value in matched_raw.items():
                if key in {"contour", "sprayPattern"}:
                    continue
                aligned[key] = copy.deepcopy(value)
            aligned["dxfPath"] = dxf_path
            aligned.setdefault("sprayPattern", {"Contour": [], "Fill": []})

            self._logger.info(
                "Capture: recognized known workpiece %s and loaded aligned DXF",
                payload.get("workpieceId") or "(no id)",
            )
            return aligned
        except Exception:
            self._logger.exception("Capture: known-workpiece detection failed")
            return None

    def _connect_segment_added(self) -> None:
        try:
            inner = self._view._editor.contourEditor.editor_with_rulers.editor
            bus = getattr(inner, '_event_bus', None)
            if bus is not None and hasattr(bus, 'segment_added'):
                bus.segment_added.connect(self._on_segment_added)
        except Exception:
            self._logger.debug("Could not connect segment_added event", exc_info=True)

    def _on_segment_added(self, *_args) -> None:
        """Called when the user draws a new segment — assign defaults to it immediately."""
        try:
            inner = self._view._editor.contourEditor.editor_with_rulers.editor
            if hasattr(inner, 'workpiece_manager'):
                inner.workpiece_manager.apply_defaults_to_segments_without_settings()
        except Exception:
            self._logger.debug("_on_segment_added: could not apply defaults", exc_info=True)
