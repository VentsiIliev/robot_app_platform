import cv2

from PyQt6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QWidget, QLabel,
    QTextEdit, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QImage, QPixmap, QTextCursor

from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton
from pl_gui.utils.utils_widgets.clickable_label import ClickableLabel
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

    def __init__(self, parent=None):
        super().__init__("Calibration", parent)

    def setup_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_preview_panel(),  stretch=3)
        root.addWidget(self._build_controls_panel(), stretch=2)

    def clean_up(self) -> None:
        pass

    # ── Preview panel (left) ──────────────────────────────────────────

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

        self._preview_label = ClickableLabel()
        self._preview_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        layout.addWidget(caption, stretch=0)
        layout.addWidget(self._preview_label, stretch=1)
        return panel

    # ── Controls panel (right) ───────────────────────────────────────

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

        layout.addWidget(_divider())

        # ── Individual calibrations ───────────────────────────────────
        layout.addWidget(_section_label("Calibrate"))
        self._calibrate_camera_btn = MaterialButton("Calibrate Camera")
        self._calibrate_camera_btn.setStyleSheet(_BTN_PRIMARY)
        layout.addWidget(self._calibrate_camera_btn)

        self._calibrate_robot_btn = MaterialButton("Calibrate Robot")
        self._calibrate_robot_btn.setStyleSheet(_BTN_PRIMARY)
        layout.addWidget(self._calibrate_robot_btn)

        layout.addWidget(_divider())

        # ── Sequence ─────────────────────────────────────────────────
        layout.addWidget(_section_label("Sequence"))
        self._calibrate_sequence_btn = MaterialButton("Calibrate Camera → Robot")
        self._calibrate_sequence_btn.setStyleSheet(_BTN_SEQUENCE)
        layout.addWidget(self._calibrate_sequence_btn)

        layout.addWidget(_divider())

        # ── Log area ──────────────────────────────────────────────────
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

    # ── Public API ────────────────────────────────────────────────────

    def update_camera_view(self, image) -> None:
        if image is None:
            return
        rgb  = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
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
