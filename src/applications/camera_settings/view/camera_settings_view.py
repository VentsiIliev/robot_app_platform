import cv2
from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget, QLabel
from PyQt6.QtCore import pyqtSignal, pyqtSlot, Qt
from PyQt6.QtGui import QImage, QPixmap

from pl_gui.settings.settings_view.settings_view import SettingsView
from pl_gui.utils.utils_widgets.camera_view import CameraView
from src.applications.base.i_application_view import IApplicationView
from src.applications.camera_settings.view.camera_controls_widget import CameraControlsWidget

_STATE_COLORS = {
    "IDLE":         ("#8888AA", "#1A1A2E"),
    "INITIALIZING": ("#00CCFF", "#0D1B2A"),
    "STARTED":      ("#44FF88", "#0D1F18"),
    "PAUSED":       ("#FFCC00", "#1F1A00"),
    "STOPPED":      ("#FF8C32", "#1F1000"),
    "ERROR":        ("#FF4466", "#1F0010"),
    "UNKNOWN":      ("#555577", "#12121F"),
}
_STATE_LABEL_STYLE = """
    QLabel {{
        color: {fg};
        background: {bg};
        border-bottom: 2px solid {fg};
        font-size: 9pt;
        font-weight: bold;
        letter-spacing: 1px;
        padding: 4px 10px;
    }}
"""
_CAPTION_STYLE = "color: #666688; font-size: 8pt; background: transparent; padding: 2px 6px;"


class CameraSettingsView(IApplicationView):
    SHOW_JOG_WIDGET = True
    JOG_FRAME_SELECTOR_ENABLED = True

    raw_mode_toggled               = pyqtSignal(bool)
    value_changed_signal           = pyqtSignal(str, object, str)
    save_requested                 = pyqtSignal(dict)
    vision_state_changed           = pyqtSignal(str)

    def __init__(
        self,
        settings_view: SettingsView,
        parent=None,
    ):
        self._settings_view = settings_view
        super().__init__("CameraSettings", parent)

    def setup_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_left_panel(), stretch=1)  # ← back to 1
        root.addWidget(self._settings_view, stretch=2)
        self._connect_signals()
        self.vision_state_changed.connect(self._on_vision_state_changed)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── State bar ─────────────────────────────────────────────────────
        fg, bg = _STATE_COLORS["UNKNOWN"]
        self._state_label = QLabel("● UNKNOWN")
        self._state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state_label.setFixedHeight(28)
        self._state_label.setStyleSheet(_STATE_LABEL_STYLE.format(fg=fg, bg=bg))
        layout.addWidget(self._state_label, stretch=0)

        # ── Live feed ─────────────────────────────────────────────────────
        live_caption = QLabel("Live")
        live_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        live_caption.setStyleSheet(_CAPTION_STYLE)
        live_caption.setFixedHeight(16)
        self._preview_label = CameraView()
        self._preview_label.setMaximumHeight(280)
        layout.addWidget(live_caption, stretch=0)
        layout.addWidget(self._preview_label, stretch=1)

        # ── Threshold feed ────────────────────────────────────────────────
        thresh_caption = QLabel("Threshold")
        thresh_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thresh_caption.setStyleSheet(_CAPTION_STYLE)
        thresh_caption.setFixedHeight(16)
        self._threshold_label = CameraView()
        self._threshold_label.setMaximumHeight(280)
        layout.addWidget(thresh_caption, stretch=0)
        layout.addWidget(self._threshold_label, stretch=1)

        # ── Controls ──────────────────────────────────────────────────────
        self._controls = CameraControlsWidget()
        layout.addWidget(self._controls, stretch=0)

        self._left_layout = layout
        return panel

    def clean_up(self) -> None:
        pass


    def _connect_signals(self) -> None:
        self._controls.raw_mode_toggled.connect(self.raw_mode_toggled.emit)
        self._settings_view.value_changed_signal.connect(self.value_changed_signal.emit)
        self._settings_view.save_requested.connect(self.save_requested.emit)

    @pyqtSlot(str)
    def _on_vision_state_changed(self, state: str) -> None:
        fg, bg = _STATE_COLORS.get(state.upper(), _STATE_COLORS["UNKNOWN"])
        self._state_label.setStyleSheet(_STATE_LABEL_STYLE.format(fg=fg, bg=bg))
        self._state_label.setText(f"● {state.upper()}")

    # ── Public setters ────────────────────────────────────────────────

    def set_vision_state(self, state: str) -> None:
        self.vision_state_changed.emit(state)

    def update_camera_view(self, image) -> None:
        if self._preview_label is None:
            return
        rgb  = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._preview_label.set_frame(QPixmap.fromImage(qimg))

    def update_threshold_view(self, image) -> None:
        # threshold image arrives as single-channel grayscale numpy array
        if image is None:
            return
        if len(image.shape) == 2:
            # grayscale → RGB for QImage
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        h, w, ch = image.shape
        qimg = QImage(image.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._threshold_label.set_frame(QPixmap.fromImage(qimg))

    # ── Properties ───────────────────────────────────────────────────

    @property
    def preview_label(self) -> CameraView | None:
        return self._preview_label

    @property
    def controls(self) -> CameraControlsWidget:
        return self._controls

    @property
    def settings_view(self) -> SettingsView:
        return self._settings_view
