import numpy as np
import cv2
from PyQt6.QtGui import QImage, QPixmap, QWheelEvent
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QObject, QPoint
from PyQt6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QWidget, QSizePolicy, QPlainTextEdit, QSplitter,
    QDoubleSpinBox, QFrame, QScrollArea,
)

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE, BG_COLOR, BORDER, LABEL_STYLE, PRIMARY,
)
from src.applications.base.i_application_view import IApplicationView

_LOG_STYLE = """
QPlainTextEdit {
    background: #1E1E1E; color: #D4D4D4;
    font-family: monospace; font-size: 9pt;
    border: 1px solid #333; border-radius: 4px;
}
"""

_TCP_ON_STYLE  = "QPushButton { background: #2E7D32; color: white; border-radius: 4px; font-size: 9pt; padding: 4px 8px; } QPushButton:hover { background: #388E3C; }"
_TCP_OFF_STYLE = ACTION_BTN_STYLE

_ZOOM_BTN_STYLE = (
    "QPushButton { border: 1px solid #CCC; border-radius: 3px; background: white;"
    " font-size: 11pt; font-weight: bold; min-width: 24px; max-width: 24px;"
    " min-height: 24px; max-height: 24px; }"
    "QPushButton:hover { background: #EDE7F6; border-color: #905BA9; }"
    "QPushButton:pressed { background: #D7C8EC; }"
)

_OVERLAY_OFF_STYLE = ACTION_BTN_STYLE
_OVERLAY_ON_STYLE  = (
    "QPushButton { background: #E8F5E9; color: #2E7D32; border: 1px solid #4CAF50;"
    " border-radius: 4px; font-size: 9pt; padding: 4px 8px; }"
    "QPushButton:hover { background: #DCEDC8; }"
)

# ── Magnifier tunables ────────────────────────────────────────────────────────
_MAG_CROP_HALF   = 60    # px from center to crop edge
_MAG_INSET_SIZE  = 300   # output inset square (px)
_MAG_MARGIN      = 8     # inset distance from frame edge
_MAG_BORDER      = (220, 220, 220)
_MAG_SOURCE      = (0, 200, 255)
_MAG_CROSS_COLOR = (0, 255, 80)


# ── Zoomable + pannable image widget ─────────────────────────────────────────

class _ZoomableImageWidget(QWidget):
    _ZOOM_STEP = 1.30
    _ZOOM_MIN  = 0.05
    _ZOOM_MAX  = 12.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frame        = None
        self._zoom         = 1.0
        self._pan_active   = False
        self._pan_start    = QPoint()
        self._scroll_start = QPoint()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QHBoxLayout()
        bar.setContentsMargins(6, 4, 6, 2)
        bar.setSpacing(4)

        self._out_btn   = QPushButton("−")
        self._in_btn    = QPushButton("+")
        self._reset_btn = QPushButton("⊙")
        self._pct_label = QLabel("—")

        for btn in (self._out_btn, self._in_btn, self._reset_btn):
            btn.setStyleSheet(_ZOOM_BTN_STYLE)

        self._pct_label.setStyleSheet(
            "font-size: 9pt; color: #555; background: transparent; min-width: 40px;"
        )

        bar.addWidget(self._make_label("Zoom:"))
        bar.addWidget(self._out_btn)
        bar.addWidget(self._in_btn)
        bar.addWidget(self._reset_btn)
        bar.addSpacing(6)
        bar.addWidget(self._pct_label)
        bar.addStretch()

        self._out_btn.clicked.connect(self.zoom_out)
        self._in_btn.clicked.connect(self.zoom_in)
        self._reset_btn.clicked.connect(self.reset_zoom)

        self._scroll = QScrollArea()
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setWidgetResizable(False)
        self._scroll.setStyleSheet(
            "QScrollArea { border: none; background: #F0F0F0; }"
            "QScrollBar:vertical   { width:  8px; }"
            "QScrollBar:horizontal { height: 8px; }"
        )

        self._img_label = QLabel("No capture")
        self._img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_label.setStyleSheet("background: #F0F0F0; border: none; color: #888;")
        self._scroll.setWidget(self._img_label)

        vp = self._scroll.viewport()
        vp.installEventFilter(self)
        vp.setCursor(Qt.CursorShape.OpenHandCursor)

        layout.addLayout(bar)
        layout.addWidget(self._scroll, stretch=1)

    def set_frame(self, frame: np.ndarray) -> None:
        self._frame = frame.copy()
        self._render()

    def zoom_in(self) -> None:
        self._set_zoom(self._zoom * self._ZOOM_STEP)

    def zoom_out(self) -> None:
        self._set_zoom(self._zoom / self._ZOOM_STEP)

    def reset_zoom(self) -> None:
        self._set_zoom(1.0)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if obj is not self._scroll.viewport():
            return super().eventFilter(obj, event)

        t = event.type()

        if t == QEvent.Type.Wheel:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            return True

        if t == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:  # type: ignore[attr-defined]
                self._pan_active   = True
                self._pan_start    = event.pos()  # type: ignore[attr-defined]
                self._scroll_start = QPoint(
                    self._scroll.horizontalScrollBar().value(),
                    self._scroll.verticalScrollBar().value(),
                )
                self._scroll.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
                return True

        if t == QEvent.Type.MouseMove and self._pan_active:
            delta = event.pos() - self._pan_start  # type: ignore[attr-defined]
            self._scroll.horizontalScrollBar().setValue(self._scroll_start.x() - delta.x())
            self._scroll.verticalScrollBar().setValue(self._scroll_start.y() - delta.y())
            return True

        if t == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:  # type: ignore[attr-defined]
                self._pan_active = False
                self._scroll.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
                return True

        return super().eventFilter(obj, event)

    def _set_zoom(self, z: float) -> None:
        self._zoom = max(self._ZOOM_MIN, min(self._ZOOM_MAX, z))
        self._render()

    def _render(self) -> None:
        if self._frame is None:
            self._img_label.setText("No capture")
            self._img_label.resize(200, 160)
            self._pct_label.setText("—")
            return

        rgb = cv2.cvtColor(self._frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(bytes(rgb.data), w, h, ch * w, QImage.Format.Format_RGB888)

        new_w = max(1, int(w * self._zoom))
        new_h = max(1, int(h * self._zoom))
        scaled = QPixmap.fromImage(qimg).scaled(
            new_w, new_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self._img_label.setPixmap(scaled)
        self._img_label.resize(scaled.width(), scaled.height())
        self._pct_label.setText(f"{self._zoom * 100:.0f}%")

    @staticmethod
    def _make_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 9pt; color: #555; background: transparent;")
        return lbl


# ── View ──────────────────────────────────────────────────────────────────────

class PickTargetView(IApplicationView):

    capture_requested             = pyqtSignal()
    move_requested                = pyqtSignal()
    calibration_pos_requested     = pyqtSignal()
    target_changed                = pyqtSignal(str)
    pickup_plane_toggled          = pyqtSignal(bool)
    pickup_plane_rz_changed       = pyqtSignal(float)
    execute_trajectory_requested  = pyqtSignal()

    def __init__(self, parent=None):
        self._magnifier_on = False
        self._move_available = False
        self._pickup_plane_mode = False
        self._trajectory_available = False
        self._target_cycle = ["camera_center", "tool", "gripper"]
        self._target_index = 0
        super().__init__("PickTarget", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        left_split = QSplitter(Qt.Orientation.Vertical)
        left_split.addWidget(self._build_image_panel("Live Feed", "_feed_label"))
        left_split.addWidget(self._build_zoomable_capture_panel())
        left_split.setStretchFactor(0, 1)
        left_split.setStretchFactor(1, 1)

        right = self._build_control_panel()
        right.setFixedWidth(380)

        root.addWidget(left_split, stretch=1)
        root.addWidget(right)

    # ── Builders ──────────────────────────────────────────────────────

    def _build_image_panel(self, title: str, attr: str, placeholder: str = "No feed") -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: white; border: 1px solid {BORDER}; border-radius: 6px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        hdr = QLabel(title)
        hdr.setStyleSheet(LABEL_STYLE)
        hdr.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(hdr)

        label = QLabel(placeholder)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            f"color: #888; background: #F0F0F0; border: 1px solid {BORDER}; border-radius: 4px;"
        )
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        setattr(self, attr, label)
        layout.addWidget(label, stretch=1)
        return panel

    def _build_zoomable_capture_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: white; border: 1px solid {BORDER}; border-radius: 6px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        hdr = QLabel("Captured")
        hdr.setStyleSheet(LABEL_STYLE)
        hdr.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        layout.addWidget(hdr)

        self._zoom_widget = _ZoomableImageWidget()
        self._zoom_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._zoom_widget, stretch=1)
        return panel

    def _build_control_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: white; border: 1px solid {BORDER}; border-radius: 6px;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        hdr = QLabel("Controls")
        hdr.setStyleSheet(LABEL_STYLE)
        layout.addWidget(hdr)

        btn_row = QHBoxLayout()
        self._capture_btn = QPushButton("◉ Capture")
        self._capture_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._capture_btn.clicked.connect(self.capture_requested)
        btn_row.addWidget(self._capture_btn)

        self._move_btn = QPushButton("▶ Move")
        self._move_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._move_btn.setEnabled(False)
        self._move_btn.clicked.connect(self.move_requested)
        btn_row.addWidget(self._move_btn)
        layout.addLayout(btn_row)

        # ── Execute Trajectory ────────────────────────────────────────
        self._traj_btn = QPushButton("⬡ Execute Trajectory")
        self._traj_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._traj_btn.setEnabled(False)
        self._traj_btn.clicked.connect(self.execute_trajectory_requested)
        layout.addWidget(self._traj_btn)

        _spin_style = (
            "QDoubleSpinBox { border: 1px solid #CCC; border-radius: 3px;"
            " padding: 2px 4px; font-size: 9pt; }"
        )
        traj_params = QHBoxLayout()
        traj_params.setSpacing(4)

        vel_lbl = QLabel("Vel:")
        vel_lbl.setStyleSheet("font-size: 9pt; color: #555; background: transparent;")
        self._traj_vel_spin = QDoubleSpinBox()
        self._traj_vel_spin.setRange(0.01, 1.0)
        self._traj_vel_spin.setSingleStep(0.05)
        self._traj_vel_spin.setDecimals(2)
        self._traj_vel_spin.setValue(0.10)
        self._traj_vel_spin.setFixedWidth(68)
        self._traj_vel_spin.setStyleSheet(_spin_style)

        acc_lbl = QLabel("Acc:")
        acc_lbl.setStyleSheet("font-size: 9pt; color: #555; background: transparent;")
        self._traj_acc_spin = QDoubleSpinBox()
        self._traj_acc_spin.setRange(0.01, 1.0)
        self._traj_acc_spin.setSingleStep(0.05)
        self._traj_acc_spin.setDecimals(2)
        self._traj_acc_spin.setValue(0.10)
        self._traj_acc_spin.setFixedWidth(68)
        self._traj_acc_spin.setStyleSheet(_spin_style)

        z_lbl = QLabel("Z:")
        z_lbl.setStyleSheet("font-size: 9pt; color: #555; background: transparent;")
        self._traj_z_spin = QDoubleSpinBox()
        self._traj_z_spin.setRange(50.0, 800.0)
        self._traj_z_spin.setSingleStep(10.0)
        self._traj_z_spin.setDecimals(1)
        self._traj_z_spin.setValue(300.0)
        self._traj_z_spin.setSuffix(" mm")
        self._traj_z_spin.setFixedWidth(80)
        self._traj_z_spin.setStyleSheet(_spin_style)

        for w in (vel_lbl, self._traj_vel_spin, acc_lbl, self._traj_acc_spin, z_lbl, self._traj_z_spin):
            traj_params.addWidget(w)
        traj_params.addStretch()
        layout.addLayout(traj_params)

        rz_row = QHBoxLayout()
        rz_lbl = QLabel("Pickup RZ:")
        rz_lbl.setStyleSheet("font-size: 9pt; color: #555; background: transparent;")
        self._pickup_rz_spin = QDoubleSpinBox()
        self._pickup_rz_spin.setRange(-180.0, 180.0)
        self._pickup_rz_spin.setSingleStep(5.0)
        self._pickup_rz_spin.setDecimals(1)
        self._pickup_rz_spin.setValue(90.0)
        self._pickup_rz_spin.setSuffix(" deg")
        self._pickup_rz_spin.setFixedWidth(96)
        self._pickup_rz_spin.setStyleSheet(_spin_style)
        self._pickup_rz_spin.valueChanged.connect(self.pickup_plane_rz_changed)
        rz_row.addWidget(rz_lbl)
        rz_row.addWidget(self._pickup_rz_spin)
        rz_row.addStretch()
        layout.addLayout(rz_row)

        row2 = QHBoxLayout()
        self._target_btn = QPushButton("Target: CAMERA")
        self._target_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._target_btn.clicked.connect(self._cycle_target)
        row2.addWidget(self._target_btn)

        self._pickup_plane_btn = QPushButton("Plane: CALIB")
        self._pickup_plane_btn.setCheckable(True)
        self._pickup_plane_btn.setStyleSheet(_TCP_OFF_STYLE)
        self._pickup_plane_btn.toggled.connect(self._on_pickup_plane_toggled)
        row2.addWidget(self._pickup_plane_btn)

        self._calib_btn = QPushButton("↩ Start")
        self._calib_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._calib_btn.clicked.connect(self.calibration_pos_requested)
        row2.addWidget(self._calib_btn)
        layout.addLayout(row2)

        # ── Overlays ──────────────────────────────────────────────────
        self._magnifier_btn = QPushButton("🔍 Magnifier")
        self._magnifier_btn.setCheckable(True)
        self._magnifier_btn.setStyleSheet(_OVERLAY_OFF_STYLE)
        self._magnifier_btn.toggled.connect(self._on_magnifier_toggled)
        layout.addWidget(self._magnifier_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(sep)

        delay_row = QHBoxLayout()
        delay_lbl = QLabel("Move delay:")
        delay_lbl.setStyleSheet("font-size: 9pt; color: #555; background: transparent;")
        delay_row.addWidget(delay_lbl)

        self._delay_spin = QDoubleSpinBox()
        self._delay_spin.setRange(0.0, 30.0)
        self._delay_spin.setSingleStep(0.5)
        self._delay_spin.setDecimals(1)
        self._delay_spin.setValue(0.0)
        self._delay_spin.setSuffix(" s")
        self._delay_spin.setFixedWidth(80)
        self._delay_spin.setStyleSheet(
            "QDoubleSpinBox { border: 1px solid #CCC; border-radius: 3px;"
            " padding: 2px 4px; font-size: 9pt; }"
        )
        delay_row.addWidget(self._delay_spin)
        delay_row.addStretch()
        layout.addLayout(delay_row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {BORDER};")
        layout.addWidget(sep2)

        log_hdr_row = QHBoxLayout()
        log_hdr = QLabel("Log")
        log_hdr.setStyleSheet(LABEL_STYLE)
        log_hdr_row.addWidget(log_hdr)
        log_hdr_row.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedHeight(24)
        clear_btn.setStyleSheet(
            f"QPushButton {{ background: white; color: {PRIMARY}; border: 1px solid {PRIMARY};"
            f" border-radius: 3px; font-size: 9pt; padding: 0 8px; }}"
            f"QPushButton:hover {{ background: #EDE7F6; }}"
        )
        clear_btn.clicked.connect(self._on_clear_log)
        log_hdr_row.addWidget(clear_btn)
        layout.addLayout(log_hdr_row)

        self._log_text = QPlainTextEdit()
        self._log_text.setStyleSheet(_LOG_STYLE)
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumBlockCount(500)
        layout.addWidget(self._log_text, stretch=1)

        return panel

    # ── Public API ────────────────────────────────────────────────────

    def update_camera_frame(self, frame: np.ndarray) -> None:
        annotated = frame.copy()
        h, w = annotated.shape[:2]
        cx, cy = w // 2, h // 2
        cv2.line(annotated, (0, cy), (w, cy), (0, 200, 0), 1)
        cv2.line(annotated, (cx, 0), (cx, h), (0, 200, 0), 1)
        if self._magnifier_on:
            annotated = self._draw_magnifier(annotated)
        self._set_frame(self._feed_label, annotated)  # type: ignore[attr-defined]

    def update_captured_frame(self, frame: np.ndarray) -> None:
        self._zoom_widget.set_frame(frame)

    def append_log(self, text: str) -> None:
        self._log_text.appendPlainText(text)

    def set_move_enabled(self, enabled: bool) -> None:
        self._move_available = enabled
        self._move_btn.setEnabled(enabled)

    def set_trajectory_enabled(self, enabled: bool) -> None:
        self._trajectory_available = enabled
        self._traj_btn.setEnabled(enabled and not self._pickup_plane_mode)

    def set_busy(self, busy: bool) -> None:
        self._capture_btn.setEnabled(not busy)
        self._move_btn.setEnabled(not busy and self._move_available)
        self._calib_btn.setEnabled(not busy)
        self._traj_btn.setEnabled(
            not busy and self._trajectory_available and not self._pickup_plane_mode
        )

    def get_move_delay(self) -> float:
        return self._delay_spin.value()

    def get_trajectory_vel(self) -> float:
        return self._traj_vel_spin.value()

    def get_trajectory_acc(self) -> float:
        return self._traj_acc_spin.value()

    def get_trajectory_z(self) -> float:
        return self._traj_z_spin.value()

    def get_pickup_plane_rz(self) -> float:
        return self._pickup_rz_spin.value()

    def get_target(self) -> str:
        return self._target_cycle[self._target_index]

    # ── Private ───────────────────────────────────────────────────────

    def _cycle_target(self) -> None:
        self._target_index = (self._target_index + 1) % len(self._target_cycle)
        target = self._target_cycle[self._target_index]
        label = {
            "camera_center": "Target: CAMERA",
            "tool": "Target: TOOL",
            "gripper": "Target: GRIPPER",
        }[target]
        self._target_btn.setText(label)
        self.target_changed.emit(target)

    def _on_pickup_plane_toggled(self, checked: bool) -> None:
        self._pickup_plane_mode = checked
        self._pickup_plane_btn.setText("Plane: PICKUP" if checked else "Plane: CALIB")
        self._pickup_plane_btn.setStyleSheet(_TCP_ON_STYLE if checked else _TCP_OFF_STYLE)
        self._traj_btn.setEnabled(self._trajectory_available and not checked)
        self.pickup_plane_toggled.emit(checked)

    def _on_magnifier_toggled(self, checked: bool) -> None:
        self._magnifier_on = checked
        self._magnifier_btn.setStyleSheet(_OVERLAY_ON_STYLE if checked else _OVERLAY_OFF_STYLE)

    def _set_frame(self, label: QLabel, frame: np.ndarray) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(bytes(rgb.data), w, h, ch * w, QImage.Format.Format_RGB888)
        px = QPixmap.fromImage(qimg).scaled(
            label.width(), label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        label.setPixmap(px)

    @staticmethod
    def _draw_magnifier(frame: np.ndarray) -> np.ndarray:
        out    = frame.copy()
        h, w   = out.shape[:2]
        cx, cy = w // 2, h // 2
        half   = _MAG_CROP_HALF

        x1 = max(0, cx - half)
        y1 = max(0, cy - half)
        x2 = min(w, cx + half)
        y2 = min(h, cy + half)

        crop   = out[y1:y2, x1:x2]
        size   = _MAG_INSET_SIZE
        zoomed = cv2.resize(crop, (size, size), interpolation=cv2.INTER_LINEAR)

        # crosshair on the inset
        iz = size // 2
        cv2.line(zoomed,   (0, iz),    (size, iz),   _MAG_CROSS_COLOR, 1)
        cv2.line(zoomed,   (iz, 0),    (iz, size),   _MAG_CROSS_COLOR, 1)
        cv2.circle(zoomed, (iz, iz),   3,            _MAG_CROSS_COLOR, -1)

        # paste inset — bottom-right corner
        m  = _MAG_MARGIN
        px = w - size - m
        py = h - size - m
        if px >= 0 and py >= 0:
            out[py:py + size, px:px + size] = zoomed
            cv2.rectangle(out, (px - 1, py - 1), (px + size, py + size), _MAG_BORDER, 1)

        # source region box on main frame
        cv2.rectangle(out, (x1, y1), (x2, y2), _MAG_SOURCE, 1)

        return out

    def _on_clear_log(self) -> None:
        self._log_text.clear()

    def clean_up(self) -> None:
        pass
