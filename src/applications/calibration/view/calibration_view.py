import cv2
import numpy as np

from PyQt6.QtWidgets import (
    QFormLayout, QHBoxLayout, QVBoxLayout, QWidget, QLabel,
    QTextEdit, QSizePolicy, QSpinBox, QScrollArea,
)
from PyQt6.QtCore import pyqtSignal, Qt, QPointF
from PyQt6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QTextCursor

from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton
from pl_gui.utils.utils_widgets.camera_view import CameraView
from src.applications.base.i_application_view import IApplicationView

_BG          = "#F8F9FA"
_PANEL_BG    = "#FFFFFF"
_CAPTION     = "color: #888899; font-size: 8pt; background: transparent; padding: 2px 6px;"
_SECTION_LBL = "color: #1A1A2E; font-size: 9pt; font-weight: bold; background: transparent; padding: 4px 0;"
_LOG_STYLE   = """
QTextEdit {
    background: #F3F4F8;
    color: #1A1A2E;
    border: 1px solid #E0E0E0;
    border-radius: 6px;
    font-family: monospace;
    font-size: 9pt;
    padding: 6px;
}
"""
_DIVIDER_CSS = "background: #E0E0E0;"

_BTN_PRIMARY = """
MaterialButton {
    background: #905BA9;
    color: white;
    border-radius: 8px;
    font-weight: bold;
    min-height: 44px;
}
MaterialButton:hover   { background: #7A4D90; }
MaterialButton:pressed { background: #6B4080; }
"""
_BTN_SECONDARY = """
MaterialButton {
    background: transparent;
    color: #905BA9;
    border: 1.5px solid #905BA9;
    border-radius: 8px;
    font-weight: bold;
    min-height: 44px;
}
MaterialButton:hover { background: rgba(144,91,169,0.08); }
"""
_BTN_SEQUENCE = """
MaterialButton {
    background: #EDE7F6;
    color: #5B3ED6;
    border: 1.5px solid #5B3ED6;
    border-radius: 8px;
    font-weight: bold;
    min-height: 44px;
}
MaterialButton:hover   { background: #E0D6F0; }
MaterialButton:pressed { background: #D4CAE4; }
"""

_BTN_OVERLAY_OFF = """
MaterialButton {
    background: transparent;
    color: #888;
    border: 1.5px solid #CCCCCC;
    border-radius: 8px;
    font-weight: bold;
    min-height: 36px;
}
MaterialButton:hover { background: rgba(0,0,0,0.04); }
"""
_BTN_OVERLAY_ON = """
MaterialButton {
    background: #E8F5E9;
    color: #2E7D32;
    border: 1.5px solid #4CAF50;
    border-radius: 8px;
    font-weight: bold;
    min-height: 36px;
}
MaterialButton:hover { background: #DCEDC8; }
"""

_BTN_DANGER = """
MaterialButton {
    background: #D32F2F;
    color: white;
    border-radius: 8px;
    font-weight: bold;
    min-height: 44px;
}
MaterialButton:hover   { background: #B71C1C; }
MaterialButton:pressed { background: #9A0007; }
MaterialButton:disabled {
    background: #EEEEEE;
    color: #BDBDBD;
    border: 1.5px solid #E0E0E0;
}
"""

_BTN_TEST = """
MaterialButton {
    background: #E8F5E9;
    color: #2E7D32;
    border: 1.5px solid #4CAF50;
    border-radius: 8px;
    font-weight: bold;
    min-height: 44px;
}
MaterialButton:hover   { background: #DCEDC8; }
MaterialButton:pressed { background: #C8E6C9; }
MaterialButton:disabled {
    background: #EEEEEE;
    color: #BDBDBD;
    border: 1.5px solid #E0E0E0;
}
"""


_CROSSHAIR_COLOR     = (0, 255, 80)    # BGR bright green
_CROSSHAIR_THICKNESS = 1

_MAGNIFY_CROP_HALF   = 60              # x_pixels from center to crop edge
_MAGNIFY_INSET_SIZE  = 210             # output inset square (x_pixels)
_MAGNIFY_MARGIN      = 10              # inset distance from frame edge
_MAGNIFY_BORDER      = (230, 230, 230) # BGR inset border
_MAGNIFY_SOURCE      = (0, 200, 255)   # BGR source-region indicator
_GRID_POINT_COLOR    = QColor("#FF7043")
_GRID_POINT_FILL     = QColor(255, 112, 67, 180)
_GRID_LABEL_COLOR    = QColor("#1A1A2E")
_GRID_REACHABLE_COLOR = QColor("#2E7D32")
_GRID_REACHABLE_FILL  = QColor(46, 125, 50, 190)
_GRID_UNREACHABLE_COLOR = QColor("#D32F2F")
_GRID_UNREACHABLE_FILL  = QColor(211, 47, 47, 190)
_SUBSTITUTE_PALETTE = [
    (QColor("#F9A825"), QColor(249, 168,  37, 55)),   # amber
    (QColor("#7B1FA2"), QColor(123,  31, 162, 55)),   # purple
    (QColor("#0288D1"), QColor(  2, 136, 209, 55)),   # blue
    (QColor("#E64A19"), QColor(230,  74,  25, 55)),   # deep orange
    (QColor("#00838F"), QColor(  0, 131, 143, 55)),   # teal
]
_CARD_STYLE = f"background: {_PANEL_BG}; border: 1px solid #E0E0E0; border-radius: 10px;"


def _divider() -> QWidget:
    d = QWidget()
    d.setFixedHeight(1)
    d.setStyleSheet(_DIVIDER_CSS)
    return d


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(_SECTION_LBL)
    return lbl


class _GridCameraView(CameraView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._grid_points: list[tuple[float, float]] = []
        self._grid_labels: list[str] = []
        self._point_statuses: dict[str, str] = {}
        self._substitute_polygons: dict[str, list[tuple[float, float]]] = {}

    def set_grid_points(
        self,
        points: list[tuple[float, float]],
        *,
        point_labels: list[str] | None = None,
        point_statuses: dict[str, str] | None = None,
    ) -> None:
        self._grid_points = [(float(x), float(y)) for x, y in points]
        self._grid_labels = [str(label) for label in (point_labels or [])]
        self._point_statuses = {
            str(label): str(status)
            for label, status in (point_statuses or {}).items()
        }
        self.update()

    def set_substitute_regions(self, polygons: dict[str, list[tuple[float, float]]]) -> None:
        self._substitute_polygons = dict(polygons)
        self.update()

    def _paint_overlay(self, painter: QPainter, image_rect) -> None:
        if not self._grid_points and not self._substitute_polygons:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        ordered_labels = list(self._substitute_polygons.keys())

        # Build area clip path from the measurement area corners
        area_corners = self.get_area_corners("measurement_area")
        area_path: QPainterPath | None = None
        if len(area_corners) >= 3:
            area_path = QPainterPath()
            area_path.addPolygon(QPolygonF([QPointF(*self._to_pixel(xn, yn)) for xn, yn in area_corners]))
            area_path.closeSubpath()

        # Draw search region polygons first (behind the dots), clipped to the area
        for i, (u_label, poly_norm) in enumerate(self._substitute_polygons.items()):
            if len(poly_norm) < 3:
                continue
            color_line, color_fill = _SUBSTITUTE_PALETTE[i % len(_SUBSTITUTE_PALETTE)]
            painter.setPen(QPen(color_line, 1.0, Qt.PenStyle.DashLine))
            painter.setBrush(QBrush(color_fill))
            circle_path = QPainterPath()
            circle_path.addPolygon(QPolygonF([QPointF(*self._to_pixel(xn, yn)) for xn, yn in poly_norm]))
            circle_path.closeSubpath()
            draw_path = circle_path.intersected(area_path) if area_path is not None else circle_path
            painter.drawPath(draw_path)

        pen = QPen(_GRID_POINT_COLOR, 1.5)
        painter.setPen(pen)
        painter.setBrush(QBrush(_GRID_POINT_FILL))

        for index, (xn, yn) in enumerate(self._grid_points):
            px, py = self._to_pixel(xn, yn)
            point_name = self._grid_labels[index] if index < len(self._grid_labels) else str(index + 1)
            status = self._point_statuses.get(point_name, "")
            if status in ("direct", "via_anchor", "reachable"):
                painter.setPen(QPen(_GRID_REACHABLE_COLOR, 1.5))
                painter.setBrush(QBrush(_GRID_REACHABLE_FILL))
            elif status == "unreachable":
                painter.setPen(QPen(_GRID_UNREACHABLE_COLOR, 1.5))
                painter.setBrush(QBrush(_GRID_UNREACHABLE_FILL))
            elif status == "substitute":
                u_label = point_name[:-4]  # strip "_sub"
                pair_idx = ordered_labels.index(u_label) if u_label in ordered_labels else 0
                color_line, _ = _SUBSTITUTE_PALETTE[pair_idx % len(_SUBSTITUTE_PALETTE)]
                painter.setPen(QPen(color_line, 1.5))
                painter.setBrush(QBrush(color_line))
            else:
                painter.setPen(pen)
                painter.setBrush(QBrush(_GRID_POINT_FILL))
            painter.drawEllipse(int(px) - 4, int(py) - 4, 8, 8)
            painter.setPen(_GRID_LABEL_COLOR)
            painter.drawText(int(px) + 6, int(py) - 6, point_name)
            painter.setPen(pen)


class CalibrationView(IApplicationView):
    SHOW_JOG_WIDGET = True
    JOG_FRAME_SELECTOR_ENABLED = True

    capture_requested            = pyqtSignal()
    calibrate_camera_requested   = pyqtSignal()
    calibrate_robot_requested    = pyqtSignal()
    calibrate_sequence_requested = pyqtSignal()
    calibrate_camera_tcp_offset_requested = pyqtSignal()
    stop_calibration_requested   = pyqtSignal()
    test_calibration_requested   = pyqtSignal()
    measure_marker_heights_requested = pyqtSignal()
    generate_area_grid_requested = pyqtSignal()
    verify_area_grid_requested   = pyqtSignal()
    measure_area_grid_requested  = pyqtSignal()
    view_depth_map_requested     = pyqtSignal()
    verify_saved_model_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Calibration", parent)
        self._crosshair_on = False
        self._magnifier_on = False

    def setup_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_preview_panel(),  stretch=3)
        root.addWidget(self._build_controls_panel(), stretch=2)

    def can_close(self) -> bool:
        if hasattr(self, "_controller") and self._controller.is_calibrating():
            from src.applications.base.styled_message_box import show_warning
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

    # ── Preview panel ─────────────────────────────────────────────────

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {_BG};")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        preview_card = QWidget()
        preview_card.setStyleSheet(_CARD_STYLE)
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        caption = QLabel("Camera Preview")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption.setFixedHeight(24)
        caption.setStyleSheet(_CAPTION)

        self._preview_label = _GridCameraView()
        self._preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._preview_label.add_area("measurement_area", "#4CAF50")
        self._preview_label.set_active_area("measurement_area")
        self._preview_label.corner_updated.connect(self._on_measurement_area_changed)
        self._preview_label.empty_clicked.connect(self._on_measurement_area_empty_clicked)

        preview_layout.addWidget(caption, stretch=0)
        preview_layout.addWidget(self._preview_label, stretch=1)

        area_card = QWidget()
        area_card.setStyleSheet(_CARD_STYLE)
        area_layout = QVBoxLayout(area_card)
        area_layout.setContentsMargins(16, 12, 16, 16)
        area_layout.setSpacing(10)

        area_layout.addWidget(_section_label("Area Grid"))

        area_top = QHBoxLayout()
        area_top.setSpacing(12)

        form = QFormLayout()
        self._grid_rows_spin = QSpinBox()
        self._grid_rows_spin.setRange(2, 50)
        self._grid_rows_spin.setValue(5)
        self._grid_cols_spin = QSpinBox()
        self._grid_cols_spin.setRange(2, 50)
        self._grid_cols_spin.setValue(4)
        form.addRow("Rows:", self._grid_rows_spin)
        form.addRow("Cols:", self._grid_cols_spin)
        area_top.addLayout(form, stretch=0)

        area_actions = QVBoxLayout()
        area_actions.setSpacing(8)
        self._generate_area_grid_btn = MaterialButton("▦  Generate Grid")
        self._generate_area_grid_btn.setStyleSheet(_BTN_TEST)
        area_actions.addWidget(self._generate_area_grid_btn)

        self._measure_area_grid_btn = MaterialButton("📐  Measure Area Grid")
        self._measure_area_grid_btn.setStyleSheet(_BTN_TEST)
        self._measure_area_grid_btn.setEnabled(False)
        area_actions.addWidget(self._measure_area_grid_btn)

        self._verify_area_grid_btn = MaterialButton("🧭  Verify Grid")
        self._verify_area_grid_btn.setStyleSheet(_BTN_TEST)
        self._verify_area_grid_btn.setEnabled(False)
        area_actions.addWidget(self._verify_area_grid_btn)

        area_actions.addStretch()
        area_top.addLayout(area_actions, stretch=1)
        area_layout.addLayout(area_top)

        area_bottom = QHBoxLayout()
        area_bottom.setSpacing(8)

        self._clear_area_grid_btn = MaterialButton("✎  Clear Area")
        self._clear_area_grid_btn.setStyleSheet(_BTN_SECONDARY)
        area_bottom.addWidget(self._clear_area_grid_btn)

        self._view_depth_map_btn = MaterialButton("📈  View Depth Map")
        self._view_depth_map_btn.setStyleSheet(_BTN_TEST)
        self._view_depth_map_btn.setEnabled(False)
        area_bottom.addWidget(self._view_depth_map_btn)

        area_layout.addLayout(area_bottom)

        layout.addWidget(preview_card, stretch=5)
        layout.addWidget(area_card, stretch=0)
        return panel

    # ── Controls panel ────────────────────────────────────────────────

    def _build_controls_panel(self) -> QWidget:
        content = QWidget()
        content.setStyleSheet(f"background: {_PANEL_BG};")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Capture ───────────────────────────────────────────────────
        layout.addWidget(_section_label("Capture"))
        self._capture_btn = MaterialButton("Capture Calibration Image")
        self._capture_btn.setStyleSheet(_BTN_SECONDARY)
        layout.addWidget(self._capture_btn)

        # overlay toggles side-by-side
        overlay_row = QHBoxLayout()
        overlay_row.setSpacing(8)
        self._crosshair_btn = MaterialButton("⊕  Crosshair")
        self._crosshair_btn.setStyleSheet(_BTN_OVERLAY_OFF)
        self._magnifier_btn = MaterialButton("🔍  Magnifier")
        self._magnifier_btn.setStyleSheet(_BTN_OVERLAY_OFF)
        overlay_row.addWidget(self._crosshair_btn)
        overlay_row.addWidget(self._magnifier_btn)
        layout.addLayout(overlay_row)

        layout.addWidget(_divider())

        # ── Calibrate ─────────────────────────────────────────────────
        layout.addWidget(_section_label("Calibrate"))
        self._calibrate_camera_btn = MaterialButton("Calibrate Camera")
        self._calibrate_camera_btn.setStyleSheet(_BTN_PRIMARY)
        layout.addWidget(self._calibrate_camera_btn)

        self._calibrate_robot_btn = MaterialButton("Calibrate Robot")
        self._calibrate_robot_btn.setStyleSheet(_BTN_PRIMARY)
        layout.addWidget(self._calibrate_robot_btn)

        self._calibrate_camera_tcp_offset_btn = MaterialButton("Calibrate Camera TCP Offset")
        self._calibrate_camera_tcp_offset_btn.setStyleSheet(_BTN_PRIMARY)
        self._calibrate_camera_tcp_offset_btn.setEnabled(False)
        layout.addWidget(self._calibrate_camera_tcp_offset_btn)

        layout.addWidget(_divider())

        self._stop_robot_btn = MaterialButton("⏹  Stop Active Task")
        self._stop_robot_btn.setStyleSheet(_BTN_DANGER)
        self._stop_robot_btn.setEnabled(False)
        layout.addWidget(self._stop_robot_btn)

        # ── Sequence ──────────────────────────────────────────────────
        layout.addWidget(_section_label("Sequence"))
        self._calibrate_sequence_btn = MaterialButton("Calibrate Camera → Robot")
        self._calibrate_sequence_btn.setStyleSheet(_BTN_SEQUENCE)
        layout.addWidget(self._calibrate_sequence_btn)

        layout.addWidget(_divider())

        # ── Test ──────────────────────────────────────────────────────
        layout.addWidget(_section_label("Test"))
        self._test_calibration_btn = MaterialButton("▶  Test Calibration")
        self._test_calibration_btn.setStyleSheet(_BTN_TEST)
        self._test_calibration_btn.setEnabled(False)
        layout.addWidget(self._test_calibration_btn)

        self._measure_marker_heights_btn = MaterialButton("📏  Measure Marker Heights")
        self._measure_marker_heights_btn.setStyleSheet(_BTN_TEST)
        self._measure_marker_heights_btn.setEnabled(False)
        layout.addWidget(self._measure_marker_heights_btn)

        self._verify_saved_model_btn = MaterialButton("🧪  Verify Saved Model")
        self._verify_saved_model_btn.setStyleSheet(_BTN_TEST)
        self._verify_saved_model_btn.setEnabled(False)
        layout.addWidget(self._verify_saved_model_btn)

        layout.addWidget(_divider())

        # ── Log ───────────────────────────────────────────────────────
        layout.addWidget(_section_label("Log"))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(_LOG_STYLE)
        self._log.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self._log, stretch=1)

        self._connect_signals()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"background: {_PANEL_BG}; border-left: 1px solid #E0E0E0;")
        scroll.setWidget(content)
        return scroll

    def _connect_signals(self) -> None:
        self._capture_btn.clicked.connect(self.capture_requested.emit)
        self._calibrate_camera_btn.clicked.connect(self.calibrate_camera_requested.emit)
        self._calibrate_robot_btn.clicked.connect(self.calibrate_robot_requested.emit)
        self._calibrate_sequence_btn.clicked.connect(self.calibrate_sequence_requested.emit)
        self._calibrate_camera_tcp_offset_btn.clicked.connect(
            self.calibrate_camera_tcp_offset_requested.emit
        )
        self._test_calibration_btn.clicked.connect(self.test_calibration_requested.emit)
        self._measure_marker_heights_btn.clicked.connect(self.measure_marker_heights_requested.emit)
        self._generate_area_grid_btn.clicked.connect(self.generate_area_grid_requested.emit)
        self._verify_area_grid_btn.clicked.connect(self.verify_area_grid_requested.emit)
        self._measure_area_grid_btn.clicked.connect(self.measure_area_grid_requested.emit)
        self._clear_area_grid_btn.clicked.connect(self.clear_measurement_area)
        self._view_depth_map_btn.clicked.connect(self.view_depth_map_requested.emit)
        self._verify_saved_model_btn.clicked.connect(self.verify_saved_model_requested.emit)
        self._crosshair_btn.clicked.connect(self._toggle_crosshair)
        self._magnifier_btn.clicked.connect(self._toggle_magnifier)
        self._stop_robot_btn.clicked.connect(self.stop_calibration_requested.emit)

    def _toggle_crosshair(self) -> None:
        self._crosshair_on = not self._crosshair_on
        self._crosshair_btn.setStyleSheet(
            _BTN_OVERLAY_ON if self._crosshair_on else _BTN_OVERLAY_OFF
        )

    def _toggle_magnifier(self) -> None:
        self._magnifier_on = not self._magnifier_on
        self._magnifier_btn.setStyleSheet(
            _BTN_OVERLAY_ON if self._magnifier_on else _BTN_OVERLAY_OFF
        )

    def _on_measurement_area_changed(self, _area: str, _idx: int, _xn: float, _yn: float) -> None:
        self._preview_label.set_grid_points([])

    def _on_measurement_area_empty_clicked(self, _area: str, _xn: float, _yn: float) -> None:
        self._preview_label.set_grid_points([])

    # ── Public API ────────────────────────────────────────────────────

    def set_stop_calibration_enabled(self, enabled: bool) -> None:
        self._stop_robot_btn.setEnabled(enabled)

    def set_test_calibration_enabled(self, enabled: bool) -> None:
        self._test_calibration_btn.setEnabled(enabled)

    def set_camera_tcp_offset_enabled(self, enabled: bool) -> None:
        self._calibrate_camera_tcp_offset_btn.setEnabled(enabled)

    def set_measure_marker_heights_enabled(self, enabled: bool) -> None:
        self._measure_marker_heights_btn.setEnabled(enabled)

    def set_measure_area_grid_enabled(self, enabled: bool) -> None:
        self._measure_area_grid_btn.setEnabled(enabled)
        self._verify_area_grid_btn.setEnabled(enabled)

    def set_verify_area_grid_busy(self, busy: bool, current: int = 0, total: int = 0) -> None:
        if busy:
            if total > 0:
                self._verify_area_grid_btn.setText(f"⏳  Verifying Grid... {current}/{total}")
            else:
                self._verify_area_grid_btn.setText("⏳  Verifying Grid...")
            return
        self._verify_area_grid_btn.setText("🧭  Verify Grid")

    def set_depth_map_enabled(self, enabled: bool) -> None:
        self._view_depth_map_btn.setEnabled(enabled)
        self._verify_saved_model_btn.setEnabled(enabled)

    def update_camera_view(self, image) -> None:
        if image is None:
            return
        frame = image
        if self._crosshair_on:
            frame = self._draw_crosshair(frame)
        if self._magnifier_on:
            frame = self._draw_magnifier(frame)
        rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._preview_label.set_frame(QPixmap.fromImage(qimg))

    def append_log(self, message: str) -> None:
        self._log.append(message)
        self._log.moveCursor(QTextCursor.MoveOperation.End)

    def clear_log(self) -> None:
        self._log.clear()

    def set_buttons_enabled(self, enabled: bool) -> None:
        for btn in (
                self._capture_btn,
                self._calibrate_camera_btn,
                self._calibrate_robot_btn,
                self._calibrate_sequence_btn,
        ):
            btn.setEnabled(enabled)
        self._generate_area_grid_btn.setEnabled(enabled)
        self._clear_area_grid_btn.setEnabled(enabled)
        self._grid_rows_spin.setEnabled(enabled)
        self._grid_cols_spin.setEnabled(enabled)

    def get_measurement_area_corners(self) -> list[tuple[float, float]]:
        return self._preview_label.get_area_corners("measurement_area")

    def clear_measurement_area(self) -> None:
        self._preview_label.clear_area("measurement_area")
        self._preview_label.set_grid_points([])

    def set_generated_grid_points(
        self,
        points: list[tuple[float, float]],
        *,
        point_labels: list[str] | None = None,
        point_statuses: dict[str, str] | None = None,
    ) -> None:
        self._preview_label.set_grid_points(
            points,
            point_labels=point_labels,
            point_statuses=point_statuses,
        )

    def set_substitute_regions(self, polygons: dict[str, list[tuple[float, float]]]) -> None:
        self._preview_label.set_substitute_regions(polygons)

    def get_area_grid_shape(self) -> tuple[int, int]:
        return int(self._grid_rows_spin.value()), int(self._grid_cols_spin.value())

    # ── Frame overlays ────────────────────────────────────────────────

    @staticmethod
    def _draw_crosshair(image: np.ndarray) -> np.ndarray:
        frame   = image.copy()
        h, w    = frame.shape[:2]
        cx, cy  = w // 2, h // 2
        cv2.line(frame, (0, cy), (w, cy), _CROSSHAIR_COLOR, _CROSSHAIR_THICKNESS)
        cv2.line(frame, (cx, 0), (cx, h), _CROSSHAIR_COLOR, _CROSSHAIR_THICKNESS)
        return frame

    @staticmethod
    def _draw_magnifier(image: np.ndarray) -> np.ndarray:
        frame  = image.copy()
        h, w   = frame.shape[:2]
        cx, cy = w // 2, h // 2
        half   = _MAGNIFY_CROP_HALF

        # Clamp crop to frame bounds
        x1 = max(0, cx - half)
        y1 = max(0, cy - half)
        x2 = min(w, cx + half)
        y2 = min(h, cy + half)

        crop   = frame[y1:y2, x1:x2]
        size   = _MAGNIFY_INSET_SIZE
        zoomed = cv2.resize(crop, (size, size), interpolation=cv2.INTER_LINEAR)

        # Crosshair on inset
        iz = size // 2
        cv2.line(zoomed, (0, iz),    (size, iz),   _CROSSHAIR_COLOR, 1)
        cv2.line(zoomed, (iz, 0),    (iz, size),   _CROSSHAIR_COLOR, 1)
        cv2.circle(zoomed, (iz, iz), 3, _CROSSHAIR_COLOR, -1)

        # Paste inset — bottom-right corner
        m  = _MAGNIFY_MARGIN
        px = w - size - m
        py = h - size - m
        if px >= 0 and py >= 0:
            frame[py:py + size, px:px + size] = zoomed
            # inset border
            cv2.rectangle(frame, (px - 1, py - 1), (px + size, py + size),
                          _MAGNIFY_BORDER, 1)

        # Source region indicator on main frame
        cv2.rectangle(frame, (x1, y1), (x2, y2), _MAGNIFY_SOURCE, 1)

        return frame
