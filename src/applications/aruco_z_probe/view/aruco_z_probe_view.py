from __future__ import annotations

import numpy as np
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pl_gui.settings.settings_view.styles import ACTION_BTN_STYLE, LABEL_STYLE
from src.applications.base.i_application_view import IApplicationView

_LOG_STYLE = """
QTextEdit {
    background: #1E1E1E; color: #D4D4D4;
    font-family: monospace; font-size: 9pt;
    border: 1px solid #333; border-radius: 4px;
}
"""

_STOP_STYLE = (
    "QPushButton { background: #C62828; color: white; border-radius: 4px;"
    " font-size: 9pt; padding: 4px 8px; }"
    "QPushButton:hover { background: #D32F2F; }"
    "QPushButton:disabled { background: #555; color: #888; }"
)


class ArucoZProbeView(IApplicationView):

    calibration_pos_requested = pyqtSignal()
    sweep_requested           = pyqtSignal()
    stop_requested            = pyqtSignal()
    predict_requested         = pyqtSignal()
    verify_requested          = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("ArUco Z Probe", parent)

    def setup_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── Left: camera feed ───────────────────────────────────────────
        self._camera_label = QLabel("No camera frame")
        self._camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._camera_label.setMinimumSize(480, 360)
        self._camera_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._camera_label.setStyleSheet("background: #111; color: #888; border: 1px solid #333;")
        splitter.addWidget(self._camera_label)

        # ── Right: controls + log ───────────────────────────────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 4, 4, 4)
        right_layout.setSpacing(8)

        # Parameters
        def _row(label_text: str, widget: QWidget) -> QHBoxLayout:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet(LABEL_STYLE)
            lbl.setFixedWidth(160)
            row.addWidget(lbl)
            row.addWidget(widget)
            return row

        self._marker_id_spin = QSpinBox()
        self._marker_id_spin.setRange(0, 999)
        self._marker_id_spin.setValue(4)
        right_layout.addLayout(_row("Marker ID:", self._marker_id_spin))

        self._min_z_spin = QDoubleSpinBox()
        self._min_z_spin.setRange(-200.0, 900.0)
        self._min_z_spin.setDecimals(1)
        self._min_z_spin.setSuffix(" mm")
        self._min_z_spin.setValue(300.0)
        right_layout.addLayout(_row("Min Z:", self._min_z_spin))

        self._sample_count_spin = QSpinBox()
        self._sample_count_spin.setRange(1, 100)
        self._sample_count_spin.setValue(10)
        right_layout.addLayout(_row("Sample Count:", self._sample_count_spin))

        self._detection_attempts_spin = QSpinBox()
        self._detection_attempts_spin.setRange(1, 50)
        self._detection_attempts_spin.setValue(50)
        right_layout.addLayout(_row("Detection Attempts:", self._detection_attempts_spin))

        self._stabilization_delay_spin = QDoubleSpinBox()
        self._stabilization_delay_spin.setRange(0.0, 10.0)
        self._stabilization_delay_spin.setDecimals(2)
        self._stabilization_delay_spin.setSuffix(" s")
        self._stabilization_delay_spin.setSingleStep(0.05)
        self._stabilization_delay_spin.setValue(0.3)
        right_layout.addLayout(_row("Stabilization Delay:", self._stabilization_delay_spin))

        # Buttons
        self._calib_btn = QPushButton("Go to Calibration")
        self._calib_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._calib_btn.clicked.connect(self.calibration_pos_requested)
        right_layout.addWidget(self._calib_btn)

        self._sweep_btn = QPushButton("Start Sweep")
        self._sweep_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._sweep_btn.clicked.connect(self.sweep_requested)
        right_layout.addWidget(self._sweep_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setStyleSheet(_STOP_STYLE)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self.stop_requested)
        right_layout.addWidget(self._stop_btn)

        # ── Query section ───────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #444;")
        right_layout.addWidget(sep)

        self._query_z_spin = QDoubleSpinBox()
        self._query_z_spin.setRange(-200.0, 900.0)
        self._query_z_spin.setDecimals(1)
        self._query_z_spin.setSuffix(" mm")
        self._query_z_spin.setValue(300.0)
        right_layout.addLayout(_row("Query Z:", self._query_z_spin))

        self._predict_btn = QPushButton("Predict Shift")
        self._predict_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._predict_btn.setEnabled(False)
        self._predict_btn.clicked.connect(self.predict_requested)
        right_layout.addWidget(self._predict_btn)

        self._verify_btn = QPushButton("Run Verification")
        self._verify_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._verify_btn.setEnabled(False)
        self._verify_btn.clicked.connect(self.verify_requested)
        right_layout.addWidget(self._verify_btn)

        self._prediction_label = QLabel("—")
        self._prediction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prediction_label.setStyleSheet(
            "font-family: monospace; font-size: 9pt;"
            " background: #1E1E1E; color: #D4D4D4;"
            " border: 1px solid #333; border-radius: 4px; padding: 4px;"
        )
        right_layout.addWidget(self._prediction_label)

        # Log
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(_LOG_STYLE)
        right_layout.addWidget(self._log, stretch=1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        root.addWidget(splitter)

    def clean_up(self) -> None:
        pass

    # ── Public API ───────────────────────────────────────────────────────

    def update_camera_frame(self, frame: np.ndarray) -> None:
        if frame is None:
            return
        if len(frame.shape) == 2:
            h, w = frame.shape
            qimg = QImage(frame.data, w, h, w, QImage.Format.Format_Grayscale8)
        else:
            h, w, ch = frame.shape
            bytes_per_line = ch * w
            rgb = frame[..., ::-1].copy() if ch == 3 else frame
            qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg).scaled(
            self._camera_label.width(),
            self._camera_label.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._camera_label.setPixmap(pixmap)

    def get_marker_id(self) -> int:
        return self._marker_id_spin.value()

    def get_min_z(self) -> float:
        return self._min_z_spin.value()

    def get_sample_count(self) -> int:
        return self._sample_count_spin.value()

    def get_detection_attempts(self) -> int:
        return self._detection_attempts_spin.value()

    def get_stabilization_delay(self) -> float:
        return self._stabilization_delay_spin.value()

    def append_log(self, text: str) -> None:
        self._log.append(text)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )

    def get_query_z(self) -> float:
        return self._query_z_spin.value()

    def set_model_ready(self, ready: bool) -> None:
        self._predict_btn.setEnabled(ready)
        self._verify_btn.setEnabled(ready)
        if not ready:
            self._prediction_label.setText("—")

    def show_prediction(self, z: float, dx: float, dy: float) -> None:
        self._prediction_label.setText(
            f"z = {z:.1f} mm  →  dx = {dx:+.2f} px   dy = {dy:+.2f} px"
        )

    def set_busy(self, busy: bool) -> None:
        self._calib_btn.setEnabled(not busy)
        self._sweep_btn.setEnabled(not busy)
        self._stop_btn.setEnabled(busy)
        self._marker_id_spin.setEnabled(not busy)
        self._min_z_spin.setEnabled(not busy)
        self._sample_count_spin.setEnabled(not busy)
        self._detection_attempts_spin.setEnabled(not busy)
        self._stabilization_delay_spin.setEnabled(not busy)
        # keep predict/verify enabled state tied to model_ready, not busy
        if busy:
            self._predict_btn.setEnabled(False)
            self._verify_btn.setEnabled(False)
