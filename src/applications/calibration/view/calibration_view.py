from __future__ import annotations

import cv2
import numpy as np

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QTextCursor
from PyQt6.QtWidgets import QHBoxLayout

from src.applications.base.i_application_view import IApplicationView
from src.applications.calibration.view.calibration_controls_panel import CalibrationControlsPanel
from src.applications.calibration.view.calibration_preview_panel import (
    CalibrationAreaGridPanel,
    CalibrationPreviewPanel,
)
from src.applications.calibration.view.robot_calibration_preview_dialog import (
    RobotCalibrationPreviewDialog,
)
from src.applications.calibration_settings.calibration_settings_data import CalibrationSettingsData
from src.applications.base.styled_message_box import show_warning
from src.applications.calibration.service.i_calibration_service import RobotCalibrationPreview
from src.applications.intrinsic_calibration_capture.service.i_intrinsic_capture_service import IntrinsicCaptureConfig
from src.shared_contracts.declarations import WorkAreaDefinition

_CROSSHAIR_COLOR = (0, 255, 80)
_CROSSHAIR_THICKNESS = 1
_MAGNIFY_CROP_HALF = 60
_MAGNIFY_INSET_SIZE = 210
_MAGNIFY_MARGIN = 10
_MAGNIFY_BORDER = (230, 230, 230)
_MAGNIFY_SOURCE = (0, 200, 255)


class CalibrationView(IApplicationView):
    SHOW_JOG_WIDGET = True
    JOG_FRAME_SELECTOR_ENABLED = True

    capture_requested = pyqtSignal()
    calibrate_camera_requested = pyqtSignal()
    intrinsic_auto_capture_requested = pyqtSignal()
    intrinsic_auto_capture_stop_requested = pyqtSignal()
    calibrate_robot_requested = pyqtSignal()
    calibrate_sequence_requested = pyqtSignal()
    calibrate_camera_tcp_offset_requested = pyqtSignal()
    calibrate_laser_requested = pyqtSignal()
    detect_laser_requested = pyqtSignal()
    stop_calibration_requested = pyqtSignal()
    test_calibration_requested = pyqtSignal()
    measure_marker_heights_requested = pyqtSignal()
    generate_area_grid_requested = pyqtSignal()
    verify_area_grid_requested = pyqtSignal()
    measure_area_grid_requested = pyqtSignal()
    view_depth_map_requested = pyqtSignal()
    verify_saved_model_requested = pyqtSignal()
    save_calibration_settings_requested = pyqtSignal(dict)
    work_area_changed = pyqtSignal(str)
    measurement_area_changed = pyqtSignal()

    def __init__(self, work_area_definitions: list[WorkAreaDefinition] | None = None, parent=None):
        self._crosshair_on = False
        self._magnifier_on = False
        self._robot_overlay_payload: dict | None = None
        self._work_area_definitions = [
            definition for definition in (work_area_definitions or []) if definition.supports_height_mapping
        ]
        super().__init__("Calibration", parent)

    def setup_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._preview_panel = CalibrationPreviewPanel(self._work_area_definitions)
        self._area_grid_panel = CalibrationAreaGridPanel(
            self._preview_panel.preview_label,
            self._work_area_definitions,
        )
        self._preview_panel.preview_label.corner_updated.connect(self._area_grid_panel._on_measurement_area_changed)
        self._preview_panel.preview_label.empty_clicked.connect(self._area_grid_panel._on_measurement_area_empty_clicked)
        self._controls_panel = CalibrationControlsPanel()
        self._controls_panel.set_height_mapping_content(self._area_grid_panel)
        root.addWidget(self._preview_panel, stretch=3)
        root.addWidget(self._controls_panel, stretch=2)
        self._connect_signals()

    def can_close(self) -> bool:
        if hasattr(self, "_controller") and self._controller.is_calibrating():
            show_warning(
                self,
                "Calibration Running",
                "Calibration is currently running.\nPlease stop it before leaving.",
            )
            return False
        return True

    def clean_up(self) -> None:
        if hasattr(self, "_controller"):
            self._controller.stop()

    def _connect_signals(self) -> None:
        self._controls_panel.capture_btn.clicked.connect(self.capture_requested.emit)
        self._controls_panel.calibrate_camera_btn.clicked.connect(self.calibrate_camera_requested.emit)
        self._controls_panel.intrinsic_auto_capture.start_requested.connect(self.intrinsic_auto_capture_requested.emit)
        self._controls_panel.intrinsic_auto_capture.stop_requested.connect(self.intrinsic_auto_capture_stop_requested.emit)
        self._controls_panel.calibrate_robot_btn.clicked.connect(self.calibrate_robot_requested.emit)
        self._controls_panel.calibrate_sequence_btn.clicked.connect(self.calibrate_sequence_requested.emit)
        self._controls_panel.calibrate_camera_tcp_offset_btn.clicked.connect(
            self.calibrate_camera_tcp_offset_requested.emit
        )
        self._controls_panel.calibrate_laser_btn.clicked.connect(self.calibrate_laser_requested.emit)
        self._controls_panel.detect_laser_btn.clicked.connect(self.detect_laser_requested.emit)
        self._controls_panel.test_calibration_btn.clicked.connect(self.test_calibration_requested.emit)
        self._controls_panel.measure_marker_heights_btn.clicked.connect(self.measure_marker_heights_requested.emit)
        self._controls_panel.verify_saved_model_btn.clicked.connect(self.verify_saved_model_requested.emit)
        self._controls_panel.stop_robot_btn.clicked.connect(self.stop_calibration_requested.emit)
        self._controls_panel.crosshair_btn.clicked.connect(self._toggle_crosshair)
        self._controls_panel.magnifier_btn.clicked.connect(self._toggle_magnifier)
        for button in self._controls_panel.iter_save_settings_buttons():
            button.clicked.connect(self._emit_save_calibration_settings)

        self._area_grid_panel.generate_area_grid_requested.connect(self.generate_area_grid_requested.emit)
        self._area_grid_panel.verify_area_grid_requested.connect(self.verify_area_grid_requested.emit)
        self._area_grid_panel.measure_area_grid_requested.connect(self.measure_area_grid_requested.emit)
        self._area_grid_panel.view_depth_map_requested.connect(self.view_depth_map_requested.emit)
        self._area_grid_panel.work_area_changed.connect(self.work_area_changed.emit)
        self._area_grid_panel.measurement_area_changed.connect(self.measurement_area_changed.emit)

    def _toggle_crosshair(self) -> None:
        self._crosshair_on = self._controls_panel.toggle_crosshair()

    def _toggle_magnifier(self) -> None:
        self._magnifier_on = self._controls_panel.toggle_magnifier()

    def _emit_save_calibration_settings(self) -> None:
        self.save_calibration_settings_requested.emit(self._controls_panel.get_settings_values())

    def set_stop_calibration_enabled(self, enabled: bool) -> None:
        self._controls_panel.set_stop_calibration_enabled(enabled)

    def set_test_calibration_enabled(self, enabled: bool) -> None:
        self._controls_panel.set_test_calibration_enabled(enabled)

    def set_camera_tcp_offset_enabled(self, enabled: bool) -> None:
        self._controls_panel.set_camera_tcp_offset_enabled(enabled)

    def set_measure_marker_heights_enabled(self, enabled: bool) -> None:
        self._controls_panel.set_measure_marker_heights_enabled(enabled)

    def set_measure_area_grid_enabled(self, enabled: bool) -> None:
        self._area_grid_panel.set_measure_area_grid_enabled(enabled)

    def set_verify_area_grid_busy(self, busy: bool, current: int = 0, total: int = 0) -> None:
        self._area_grid_panel.set_verify_area_grid_busy(busy, current, total)

    def set_depth_map_enabled(self, enabled: bool) -> None:
        self._area_grid_panel.set_depth_map_enabled(enabled)
        self._controls_panel.set_depth_map_enabled(enabled)

    def set_laser_actions_enabled(self, enabled: bool) -> None:
        self._controls_panel.set_laser_actions_enabled(enabled)

    def load_calibration_settings(self, _settings: CalibrationSettingsData | None, flat: dict) -> None:
        self._controls_panel.set_settings_values(flat)

    def set_intrinsic_capture_config(self, config: IntrinsicCaptureConfig) -> None:
        self._controls_panel.intrinsic_auto_capture.set_config(config)

    def get_intrinsic_capture_config(self) -> IntrinsicCaptureConfig:
        return self._controls_panel.intrinsic_auto_capture.get_config()

    def set_intrinsic_auto_capture_running(self, running: bool) -> None:
        self._controls_panel.intrinsic_auto_capture.set_running(running)

    def update_camera_view(self, image) -> None:
        if image is None:
            return
        frame = image.copy()
        if self._robot_overlay_payload:
            frame = self._draw_robot_calibration_overlay(frame, self._robot_overlay_payload)
        if self._crosshair_on:
            frame = self._draw_crosshair(frame)
        if self._magnifier_on:
            frame = self._draw_magnifier(frame)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._preview_panel.preview_label.set_frame(QPixmap.fromImage(qimg))

    def set_robot_calibration_status(self, payload: dict | None) -> None:
        self._robot_overlay_payload = payload
        self._preview_panel.set_robot_calibration_status(payload)

    def append_log(self, message: str) -> None:
        self._preview_panel.log.append(message)
        self._preview_panel.log.moveCursor(QTextCursor.MoveOperation.End)

    def clear_log(self) -> None:
        self._preview_panel.log.clear()

    def set_buttons_enabled(self, enabled: bool) -> None:
        self._controls_panel.set_enabled(enabled)
        self._area_grid_panel.set_enabled(enabled)

    def confirm_robot_calibration_preview(self, preview: RobotCalibrationPreview) -> bool:
        dialog = RobotCalibrationPreviewDialog(preview, self)
        return dialog.exec() == dialog.DialogCode.Accepted

    @property
    def work_area_definitions(self) -> list[WorkAreaDefinition]:
        return list(self._work_area_definitions)

    def current_work_area_id(self) -> str:
        return self._area_grid_panel.current_work_area_id()

    def set_current_work_area_id(self, area_id: str) -> None:
        self._area_grid_panel.set_current_work_area_id(area_id)

    def current_height_mapping_area_key(self) -> str | None:
        return self._area_grid_panel.current_height_mapping_area_key()

    def set_work_area_options(self, definitions: list[WorkAreaDefinition]) -> None:
        self._work_area_definitions = [definition for definition in definitions if definition.supports_height_mapping]
        self._area_grid_panel.set_work_area_options(self._work_area_definitions)

    def get_measurement_area_corners(self) -> list[tuple[float, float]]:
        return self._area_grid_panel.get_measurement_area_corners()

    def clear_measurement_area(self) -> None:
        self._area_grid_panel.clear_measurement_area()

    def set_measurement_area_corners(self, area_id: str, corners: list[tuple[float, float]]) -> None:
        self._area_grid_panel.set_measurement_area_corners(area_id, corners)

    def set_generated_grid_points(
        self,
        points: list[tuple[float, float]],
        *,
        point_labels: list[str] | None = None,
        point_statuses: dict[str, str] | None = None,
    ) -> None:
        self._area_grid_panel.set_generated_grid_points(
            points,
            point_labels=point_labels,
            point_statuses=point_statuses,
        )

    def set_substitute_regions(self, polygons: dict[str, list[tuple[float, float]]]) -> None:
        self._area_grid_panel.set_substitute_regions(polygons)

    def get_area_grid_shape(self) -> tuple[int, int]:
        return self._area_grid_panel.get_area_grid_shape()

    @staticmethod
    def _draw_robot_calibration_overlay(image: np.ndarray, payload: dict | None) -> np.ndarray:
        if not payload:
            return image

        frame = image.copy()
        state_name = str(payload.get("state_name") or "")
        active_target = payload.get("active_target_id")
        active_target_px = payload.get("active_target_px")
        current_error_mm = payload.get("current_error_mm")
        current_index = int(payload.get("current_marker_index") or 0)
        total_targets = int(payload.get("total_targets") or 0)
        iteration = int(payload.get("iteration_count") or 0)
        max_iterations = int(payload.get("max_iterations") or 0)

        panel_h = 90
        overlay = frame.copy()
        cv2.rectangle(overlay, (12, 12), (520, 12 + panel_h), (18, 26, 38), -1)
        cv2.addWeighted(overlay, 0.45, frame, 0.55, 0.0, frame)

        lines = [f"State: {state_name}"]
        if active_target is not None:
            lines.append(f"Target: {active_target} ({current_index + 1}/{total_targets})")
        elif total_targets > 0:
            lines.append(f"Progress: {current_index}/{total_targets}")
        if current_error_mm is not None:
            lines.append(f"Error: {float(current_error_mm):.3f} mm")
        if max_iterations > 0:
            lines.append(f"Iteration: {iteration}/{max_iterations}")

        y = 38
        for i, line in enumerate(lines):
            scale = 0.7 if i == 0 else 0.62
            thickness = 2 if i == 0 else 1
            cv2.putText(frame, line, (24, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (235, 245, 250), thickness, cv2.LINE_AA)
            y += 22

        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        cv2.drawMarker(frame, (cx, cy), (60, 255, 120), cv2.MARKER_CROSS, 22, 2, cv2.LINE_AA)

        return frame

    @staticmethod
    def _draw_crosshair(image: np.ndarray) -> np.ndarray:
        frame = image.copy()
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        cv2.line(frame, (0, cy), (w, cy), _CROSSHAIR_COLOR, _CROSSHAIR_THICKNESS)
        cv2.line(frame, (cx, 0), (cx, h), _CROSSHAIR_COLOR, _CROSSHAIR_THICKNESS)
        return frame

    @staticmethod
    def _draw_magnifier(image: np.ndarray) -> np.ndarray:
        frame = image.copy()
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        half = _MAGNIFY_CROP_HALF

        x1 = max(0, cx - half)
        y1 = max(0, cy - half)
        x2 = min(w, cx + half)
        y2 = min(h, cy + half)

        crop = frame[y1:y2, x1:x2]
        size = _MAGNIFY_INSET_SIZE
        zoomed = cv2.resize(crop, (size, size), interpolation=cv2.INTER_LINEAR)

        iz = size // 2
        cv2.line(zoomed, (0, iz), (size, iz), _CROSSHAIR_COLOR, 1)
        cv2.line(zoomed, (iz, 0), (iz, size), _CROSSHAIR_COLOR, 1)
        cv2.circle(zoomed, (iz, iz), 3, _CROSSHAIR_COLOR, -1)

        margin = _MAGNIFY_MARGIN
        px = w - size - margin
        py = h - size - margin
        if px >= 0 and py >= 0:
            frame[py:py + size, px:px + size] = zoomed
            cv2.rectangle(frame, (px - 1, py - 1), (px + size, py + size), _MAGNIFY_BORDER, 1)

        cv2.rectangle(frame, (x1, y1), (x2, y2), _MAGNIFY_SOURCE, 1)
        return frame
