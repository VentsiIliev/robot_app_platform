import cv2
import numpy as np

from PyQt6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QWidget, QLabel,
    QTextEdit, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QImage, QPixmap, QTextCursor

from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton
from pl_gui.utils.utils_widgets.camera_view import CameraView
from src.applications.base.drawer_toggle import DrawerToggle
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.robot_jog_widget import RobotJogWidget

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

_MAGNIFY_CROP_HALF   = 60              # px from center to crop edge
_MAGNIFY_INSET_SIZE  = 210             # output inset square (px)
_MAGNIFY_MARGIN      = 10              # inset distance from frame edge
_MAGNIFY_BORDER      = (230, 230, 230) # BGR inset border
_MAGNIFY_SOURCE      = (0, 200, 255)   # BGR source-region indicator


def _divider() -> QWidget:
    d = QWidget()
    d.setFixedHeight(1)
    d.setStyleSheet(_DIVIDER_CSS)
    return d


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(_SECTION_LBL)
    return lbl


class CalibrationView(IApplicationView):

    capture_requested            = pyqtSignal()
    calibrate_camera_requested   = pyqtSignal()
    calibrate_robot_requested    = pyqtSignal()
    calibrate_sequence_requested = pyqtSignal()
    stop_calibration_requested   = pyqtSignal()
    test_calibration_requested   = pyqtSignal()
    view_depth_map_requested     = pyqtSignal()
    jog_requested              = pyqtSignal(str, str, str, float)
    jog_stopped                = pyqtSignal(str)

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

        self._drawer = DrawerToggle(self, side="right", width=320)
        self._jog_widget = RobotJogWidget()
        self._drawer.add_widget(self._jog_widget)

        self._jog_widget.jog_requested.connect(self.jog_requested)
        self._jog_widget.jog_stopped.connect(self.jog_stopped)

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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        caption = QLabel("Camera Preview")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption.setFixedHeight(24)
        caption.setStyleSheet(_CAPTION)

        self._preview_label = CameraView()
        self._preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        layout.addWidget(caption,             stretch=0)
        layout.addWidget(self._preview_label, stretch=1)
        return panel

    # ── Controls panel ────────────────────────────────────────────────

    def _build_controls_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {_PANEL_BG}; border-left: 1px solid #E0E0E0;")
        layout = QVBoxLayout(panel)
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

        layout.addWidget(_divider())

        self._stop_robot_btn = MaterialButton("⏹  Stop Robot Calibration")
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

        self._view_depth_map_btn = MaterialButton("📈  View Depth Map")
        self._view_depth_map_btn.setStyleSheet(_BTN_TEST)
        self._view_depth_map_btn.setEnabled(True)
        layout.addWidget(self._view_depth_map_btn)

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
        return panel

    def _connect_signals(self) -> None:
        self._capture_btn.clicked.connect(self.capture_requested.emit)
        self._calibrate_camera_btn.clicked.connect(self.calibrate_camera_requested.emit)
        self._calibrate_robot_btn.clicked.connect(self.calibrate_robot_requested.emit)
        self._calibrate_sequence_btn.clicked.connect(self.calibrate_sequence_requested.emit)
        self._test_calibration_btn.clicked.connect(self.test_calibration_requested.emit)
        self._view_depth_map_btn.clicked.connect(self.view_depth_map_requested.emit)
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

    # ── Public API ────────────────────────────────────────────────────

    def set_stop_calibration_enabled(self, enabled: bool) -> None:
        self._stop_robot_btn.setEnabled(enabled)

    def set_test_calibration_enabled(self, enabled: bool) -> None:
        self._test_calibration_btn.setEnabled(enabled)

    def set_depth_map_enabled(self, enabled: bool) -> None:
        self._view_depth_map_btn.setEnabled(enabled)

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

    def set_jog_position(self, pos: list) -> None:
        self._jog_widget.set_position(pos)