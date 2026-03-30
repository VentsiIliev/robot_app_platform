from __future__ import annotations

import cv2
import numpy as np
import qtawesome as qta

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.applications.base.i_application_view import IApplicationView
from src.applications.calibration_v2.view.calibration_left_panel import CalibrationLeftPanel
from src.applications.calibration_v2.view.calibration_right_panel import CalibrationRightPanel
from src.applications.calibration_settings.calibration_settings_data import CalibrationSettingsData
from src.applications.base.styled_message_box import show_warning
from src.shared_contracts.declarations import WorkAreaDefinition

_CROSSHAIR_COLOR = (0, 255, 80)
_CROSSHAIR_THICKNESS = 1
_MAGNIFY_CROP_HALF = 60
_MAGNIFY_INSET_SIZE = 210
_MAGNIFY_MARGIN = 10
_MAGNIFY_BORDER = (230, 230, 230)
_MAGNIFY_SOURCE = (0, 200, 255)

# ── Tab bar palette ───────────────────────────────────────────────────────────
_PANEL      = "#FFFFFF"
_BD         = "#D0CCDE"
_PR         = "#905BA9"
_MU         = "#6A6490"
_ICON_OFF   = _MU
_ICON_ON    = _PR
_ICON_SIZE  = 20   # px

# Tab definitions: (id, display label, qtawesome icon name)
_TABS: list[tuple[str, str, str]] = [
    ("system", "System",  "fa5s.clock"),
    ("camera", "Camera",  "fa5s.camera"),
    ("robot",  "Robot",   "fa5s.robot"),
    ("laser",  "Laser",   "fa5s.bolt"),
    ("height", "Height",  "fa5s.chart-area"),
]


class _TabButton(QWidget):
    """
    Single tab button — icon (qtawesome) above label, matching HTML:
      .tab-btn { flex-direction:row; gap:8px; border-bottom:3px solid }
    Emits clicked() like a normal button.
    """
    clicked = pyqtSignal()

    def __init__(self, tab_id: str, label: str, icon_name: str, active: bool = False, parent=None):
        super().__init__(parent)
        self._tab_id   = tab_id
        self._label    = label
        self._icon_name = icon_name
        self._active   = active
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._build()
        self._apply_state()

    def _build(self) -> None:
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 0, 8, 0)
        row.setSpacing(8)
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon_lbl = QLabel()
        self._icon_lbl.setFixedSize(_ICON_SIZE, _ICON_SIZE)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._text_lbl = QLabel(self._label)
        self._text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        row.addWidget(self._icon_lbl)
        row.addWidget(self._text_lbl)

    def _apply_state(self) -> None:
        color = _ICON_ON if self._active else _ICON_OFF
        icon = qta.icon(self._icon_name, color=color)
        self._icon_lbl.setPixmap(icon.pixmap(_ICON_SIZE, _ICON_SIZE))

        if self._active:
            self.setStyleSheet(f"""
                QWidget {{
                    background: #EDE7F6;
                    border-bottom: 3px solid {_PR};
                }}
            """)
            self._text_lbl.setStyleSheet(
                f"color: {_PR}; font-size: 10pt; font-weight: 600; background: transparent;"
            )
        else:
            self.setStyleSheet("""
                QWidget {
                    background: transparent;
                    border-bottom: 3px solid transparent;
                }
                QWidget:hover { background: #F0EBF8; }
            """)
            self._text_lbl.setStyleSheet(
                f"color: {_MU}; font-size: 10pt; font-weight: 500; background: transparent;"
            )

    def set_active(self, active: bool) -> None:
        self._active = active
        self._apply_state()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


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
    save_calibration_settings_requested = pyqtSignal(dict)
    work_area_changed = pyqtSignal(str)
    measurement_area_changed = pyqtSignal()

    def __init__(self, work_area_definitions: list[WorkAreaDefinition] | None = None, parent=None):
        self._crosshair_on = False
        self._magnifier_on = False
        self._work_area_definitions = [
            d for d in (work_area_definitions or []) if d.supports_height_mapping
        ]
        self._current_tab = "camera"
        self._tab_widgets: dict[str, _TabButton] = {}
        super().__init__("Calibration", parent)

    def setup_ui(self) -> None:
        shell = QVBoxLayout(self)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        # .topbar — full width, above both columns
        shell.addWidget(self._build_tab_bar(), stretch=0)

        # .content-row — left (camera) + right (panes)
        content_row = QWidget()
        content_layout = QHBoxLayout(content_row)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self._left  = CalibrationLeftPanel(self._work_area_definitions)
        self._right = CalibrationRightPanel(self._work_area_definitions)
        self._right.set_preview_label(self._left.preview_label)

        content_layout.addWidget(self._left,  stretch=5)
        content_layout.addWidget(self._right, stretch=3)
        shell.addWidget(content_row, stretch=1)

        self._connect_signals()

    # ------------------------------------------------------------------
    # Tab bar
    # ------------------------------------------------------------------

    def _build_tab_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(56)
        bar.setStyleSheet(
            f"background: {_PANEL};"
            f"border-bottom: 1.5px solid {_BD};"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        for i, (tab_id, label, icon_name) in enumerate(_TABS):
            # Separator before every tab except the first
            if i > 0:
                sep = QWidget()
                sep.setFixedWidth(1)
                sep.setStyleSheet(f"background: {_BD};")
                row.addWidget(sep)

            btn = _TabButton(
                tab_id, label, icon_name,
                active=(tab_id == self._current_tab),
            )
            btn.clicked.connect(lambda tid=tab_id: self._on_tab_clicked(tid))
            self._tab_widgets[tab_id] = btn
            row.addWidget(btn, stretch=1)

        return bar

    def _on_tab_clicked(self, tab_id: str) -> None:
        if tab_id == self._current_tab:
            return
        self._tab_widgets[self._current_tab].set_active(False)
        self._current_tab = tab_id
        self._tab_widgets[tab_id].set_active(True)
        self._right.show_pane(tab_id)
        self._left.set_thumbnail_strip_visible(tab_id == "camera")

    # ------------------------------------------------------------------
    # Guard
    # ------------------------------------------------------------------

    def can_close(self) -> bool:
        if hasattr(self, "_controller") and self._controller.is_calibrating():
            show_warning(self, "Calibration Running",
                         "Calibration is currently running.\nPlease stop it before leaving.")
            return False
        return True

    def clean_up(self) -> None:
        if hasattr(self, "_controller"):
            self._controller.stop()

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        rp = self._right

        # FAB on the camera box is the primary capture trigger (HTML .fab)
        self._left.fab.clicked.connect(self.capture_requested)

        # Crosshair / magnifier toggles live in the camera pane
        rp._camera_pane.crosshair_toggled.connect(self._on_crosshair_toggled)
        rp._camera_pane.magnifier_toggled.connect(self._on_magnifier_toggled)

        rp.capture_requested.connect(self.capture_requested)
        rp.calibrate_camera_requested.connect(self.calibrate_camera_requested)
        rp.calibrate_robot_requested.connect(self.calibrate_robot_requested)
        rp.calibrate_sequence_requested.connect(self.calibrate_sequence_requested)
        rp.calibrate_camera_tcp_offset_requested.connect(self.calibrate_camera_tcp_offset_requested)
        rp.calibrate_laser_requested.connect(self.calibrate_laser_requested)
        rp.detect_laser_requested.connect(self.detect_laser_requested)
        rp.stop_calibration_requested.connect(self.stop_calibration_requested)
        rp.test_calibration_requested.connect(self.test_calibration_requested)
        rp.measure_marker_heights_requested.connect(self.measure_marker_heights_requested)
        rp.generate_area_grid_requested.connect(self.generate_area_grid_requested)
        rp.verify_area_grid_requested.connect(self.verify_area_grid_requested)
        rp.measure_area_grid_requested.connect(self.measure_area_grid_requested)
        rp.view_depth_map_requested.connect(self.view_depth_map_requested)
        rp.verify_saved_model_requested.connect(self.verify_saved_model_requested)
        rp.save_calibration_settings_requested.connect(self.save_calibration_settings_requested)
        rp.work_area_changed.connect(self.work_area_changed)
        rp.measurement_area_changed.connect(self.measurement_area_changed)

        # Wire corner-drag events from preview into the area-grid panel
        self._left.preview_label.corner_updated.connect(
            rp.height_pane.area_grid_panel._on_measurement_area_changed
        )
        self._left.preview_label.empty_clicked.connect(
            rp.height_pane.area_grid_panel._on_measurement_area_empty_clicked
        )

    def _on_crosshair_toggled(self, on: bool) -> None:
        self._crosshair_on = on

    def _on_magnifier_toggled(self, on: bool) -> None:
        self._magnifier_on = on

    # ------------------------------------------------------------------
    # View setters (called by controller)
    # ------------------------------------------------------------------

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
        self._left.set_frame(QPixmap.fromImage(qimg))

    def append_log(self, message: str) -> None:
        self._left.append_log(message)

    def clear_log(self) -> None:
        self._left.clear_log()

    def set_buttons_enabled(self, enabled: bool) -> None:
        self._right.set_buttons_enabled(enabled)
        self._right.height_pane.area_grid_panel.set_enabled(enabled)

    def set_stop_calibration_enabled(self, enabled: bool) -> None:
        self._right.set_stop_calibration_enabled(enabled)

    def set_test_calibration_enabled(self, enabled: bool) -> None:
        self._right.set_test_calibration_enabled(enabled)

    def set_camera_tcp_offset_enabled(self, enabled: bool) -> None:
        self._right.set_camera_tcp_offset_enabled(enabled)

    def set_measure_marker_heights_enabled(self, enabled: bool) -> None:
        self._right.set_measure_marker_heights_enabled(enabled)

    def set_measure_area_grid_enabled(self, enabled: bool) -> None:
        self._right.height_pane.area_grid_panel.set_measure_area_grid_enabled(enabled)

    def set_verify_area_grid_busy(self, busy: bool, current: int = 0, total: int = 0) -> None:
        self._right.height_pane.area_grid_panel.set_verify_area_grid_busy(busy, current, total)

    def set_depth_map_enabled(self, enabled: bool) -> None:
        self._right.height_pane.area_grid_panel.set_depth_map_enabled(enabled)
        self._right.set_depth_map_enabled(enabled)

    def set_laser_actions_enabled(self, enabled: bool) -> None:
        self._right.set_laser_actions_enabled(enabled)

    def load_calibration_settings(self, _settings: CalibrationSettingsData | None, flat: dict) -> None:
        self._right.set_settings_values(flat)

    def iter_save_settings_buttons(self):
        return self._right.iter_save_settings_buttons()

    @property
    def work_area_definitions(self) -> list[WorkAreaDefinition]:
        return list(self._work_area_definitions)

    def current_work_area_id(self) -> str:
        return self._right.height_pane.area_grid_panel.current_work_area_id()

    def set_current_work_area_id(self, area_id: str) -> None:
        self._right.height_pane.area_grid_panel.set_current_work_area_id(area_id)

    def current_height_mapping_area_key(self) -> str | None:
        return self._right.height_pane.area_grid_panel.current_height_mapping_area_key()

    def set_work_area_options(self, definitions: list[WorkAreaDefinition]) -> None:
        self._work_area_definitions = [d for d in definitions if d.supports_height_mapping]
        self._right.height_pane.area_grid_panel.set_work_area_options(self._work_area_definitions)

    def get_measurement_area_corners(self) -> list[tuple[float, float]]:
        return self._right.height_pane.area_grid_panel.get_measurement_area_corners()

    def clear_measurement_area(self) -> None:
        self._right.height_pane.area_grid_panel.clear_measurement_area()

    def set_measurement_area_corners(self, area_id: str, corners: list[tuple[float, float]]) -> None:
        self._right.height_pane.area_grid_panel.set_measurement_area_corners(area_id, corners)

    def set_generated_grid_points(self, points, *, point_labels=None, point_statuses=None) -> None:
        self._right.height_pane.area_grid_panel.set_generated_grid_points(
            points, point_labels=point_labels, point_statuses=point_statuses
        )

    def set_substitute_regions(self, polygons) -> None:
        self._right.height_pane.area_grid_panel.set_substitute_regions(polygons)

    def get_area_grid_shape(self) -> tuple[int, int]:
        return self._right.height_pane.area_grid_panel.get_area_grid_shape()

    # ------------------------------------------------------------------
    # Image helpers
    # ------------------------------------------------------------------

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

