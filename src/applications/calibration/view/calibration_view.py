from __future__ import annotations

import cv2
import numpy as np

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QTextCursor
from PyQt6.QtWidgets import QHBoxLayout

from src.applications.base.i_application_view import IApplicationView
from src.applications.calibration.view.calibration_controls_panel import CalibrationControlsPanel
from src.applications.calibration.view.calibration_preview_panel import CalibrationPreviewPanel
from src.applications.base.styled_message_box import show_warning
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
    work_area_changed = pyqtSignal(str)
    measurement_area_changed = pyqtSignal()

    def __init__(self, work_area_definitions: list[WorkAreaDefinition] | None = None, parent=None):
        self._crosshair_on = False
        self._magnifier_on = False
        self._work_area_definitions = [
            definition for definition in (work_area_definitions or []) if definition.supports_height_mapping
        ]
        super().__init__("Calibration", parent)

    def setup_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._preview_panel = CalibrationPreviewPanel(self._work_area_definitions)
        self._controls_panel = CalibrationControlsPanel()
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

        self._preview_panel.generate_area_grid_requested.connect(self.generate_area_grid_requested.emit)
        self._preview_panel.verify_area_grid_requested.connect(self.verify_area_grid_requested.emit)
        self._preview_panel.measure_area_grid_requested.connect(self.measure_area_grid_requested.emit)
        self._preview_panel.view_depth_map_requested.connect(self.view_depth_map_requested.emit)
        self._preview_panel.work_area_changed.connect(self.work_area_changed.emit)
        self._preview_panel.measurement_area_changed.connect(self.measurement_area_changed.emit)

    def _toggle_crosshair(self) -> None:
        self._crosshair_on = self._controls_panel.toggle_crosshair()

    def _toggle_magnifier(self) -> None:
        self._magnifier_on = self._controls_panel.toggle_magnifier()

    def set_stop_calibration_enabled(self, enabled: bool) -> None:
        self._controls_panel.set_stop_calibration_enabled(enabled)

    def set_test_calibration_enabled(self, enabled: bool) -> None:
        self._controls_panel.set_test_calibration_enabled(enabled)

    def set_camera_tcp_offset_enabled(self, enabled: bool) -> None:
        self._controls_panel.set_camera_tcp_offset_enabled(enabled)

    def set_measure_marker_heights_enabled(self, enabled: bool) -> None:
        self._controls_panel.set_measure_marker_heights_enabled(enabled)

    def set_measure_area_grid_enabled(self, enabled: bool) -> None:
        self._preview_panel.set_measure_area_grid_enabled(enabled)

    def set_verify_area_grid_busy(self, busy: bool, current: int = 0, total: int = 0) -> None:
        self._preview_panel.set_verify_area_grid_busy(busy, current, total)

    def set_depth_map_enabled(self, enabled: bool) -> None:
        self._preview_panel.set_depth_map_enabled(enabled)
        self._controls_panel.set_depth_map_enabled(enabled)

    def set_laser_actions_enabled(self, enabled: bool) -> None:
        self._controls_panel.set_laser_actions_enabled(enabled)

    def update_camera_view(self, image) -> None:
        if image is None:
            return
        frame = image
        if self._crosshair_on:
            frame = self._draw_crosshair(frame)
        if self._magnifier_on:
            frame = self._draw_magnifier(frame)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._preview_panel.preview_label.set_frame(QPixmap.fromImage(qimg))

    def append_log(self, message: str) -> None:
        self._controls_panel.append_log(message)
        self._controls_panel.log.moveCursor(QTextCursor.MoveOperation.End)

    def clear_log(self) -> None:
        self._controls_panel.clear_log()

    def set_buttons_enabled(self, enabled: bool) -> None:
        self._controls_panel.set_enabled(enabled)
        self._preview_panel.set_enabled(enabled)

    @property
    def work_area_definitions(self) -> list[WorkAreaDefinition]:
        return list(self._work_area_definitions)

    def current_work_area_id(self) -> str:
        return self._preview_panel.current_work_area_id()

    def set_current_work_area_id(self, area_id: str) -> None:
        self._preview_panel.set_current_work_area_id(area_id)

    def current_height_mapping_area_key(self) -> str | None:
        return self._preview_panel.current_height_mapping_area_key()

    def set_work_area_options(self, definitions: list[WorkAreaDefinition]) -> None:
        self._work_area_definitions = [definition for definition in definitions if definition.supports_height_mapping]
        self._preview_panel.set_work_area_options(self._work_area_definitions)

    def get_measurement_area_corners(self) -> list[tuple[float, float]]:
        return self._preview_panel.get_measurement_area_corners()

    def clear_measurement_area(self) -> None:
        self._preview_panel.clear_measurement_area()

    def set_measurement_area_corners(self, area_id: str, corners: list[tuple[float, float]]) -> None:
        self._preview_panel.set_measurement_area_corners(area_id, corners)

    def set_generated_grid_points(
        self,
        points: list[tuple[float, float]],
        *,
        point_labels: list[str] | None = None,
        point_statuses: dict[str, str] | None = None,
    ) -> None:
        self._preview_panel.set_generated_grid_points(
            points,
            point_labels=point_labels,
            point_statuses=point_statuses,
        )

    def set_substitute_regions(self, polygons: dict[str, list[tuple[float, float]]]) -> None:
        self._preview_panel.set_substitute_regions(polygons)

    def get_area_grid_shape(self) -> tuple[int, int]:
        return self._preview_panel.get_area_grid_shape()

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
