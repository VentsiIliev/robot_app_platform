from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from src.applications.base.i_application_view import IApplicationView
from src.applications.hand_eye_calibration.service.i_hand_eye_service import HandEyeConfig

_COUNTER_BASE = (
    "QLabel {"
    "  background: #263238;"
    "  color: #B0BEC5;"
    "  border: 2px solid #455A64;"
    "  border-radius: 10px;"
    "  padding: 6px 18px;"
    "  font-size: 18pt;"
    "  font-weight: bold;"
    "}"
)
_COUNTER_FLASH = (
    "QLabel {"
    "  background: #1B5E20;"
    "  color: #A5D6A7;"
    "  border: 2px solid #43A047;"
    "  border-radius: 10px;"
    "  padding: 6px 18px;"
    "  font-size: 18pt;"
    "  font-weight: bold;"
    "}"
)


class HandEyeView(IApplicationView):

    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    save_config_requested = pyqtSignal(object)  # emits HandEyeConfig

    def __init__(self, parent=None):
        super().__init__("Hand-Eye Calibration", parent)
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.setInterval(500)
        self._flash_timer.timeout.connect(self._reset_counter_style)

    def setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # ── Settings ──────────────────────────────────────────────────────────
        settings_box = QGroupBox("Calibration Settings")
        form = QFormLayout(settings_box)

        self._board_cols = QSpinBox()
        self._board_cols.setRange(1, 50)
        self._board_cols.setValue(17)
        form.addRow("Board cols (inner):", self._board_cols)

        self._board_rows = QSpinBox()
        self._board_rows.setRange(1, 50)
        self._board_rows.setValue(11)
        form.addRow("Board rows (inner):", self._board_rows)

        self._square_size = QDoubleSpinBox()
        self._square_size.setRange(1.0, 500.0)
        self._square_size.setValue(15.0)
        self._square_size.setSuffix(" mm")
        form.addRow("Square size:", self._square_size)

        self._n_poses = QSpinBox()
        self._n_poses.setRange(4, 200)
        self._n_poses.setValue(20)
        form.addRow("Candidate poses:", self._n_poses)

        self._rx_range = QDoubleSpinBox()
        self._rx_range.setRange(0.0, 90.0)
        self._rx_range.setValue(15.0)
        self._rx_range.setSuffix(" °")
        form.addRow("RX range ±:", self._rx_range)

        self._ry_range = QDoubleSpinBox()
        self._ry_range.setRange(0.0, 90.0)
        self._ry_range.setValue(15.0)
        self._ry_range.setSuffix(" °")
        form.addRow("RY range ±:", self._ry_range)

        self._rz_range = QDoubleSpinBox()
        self._rz_range.setRange(0.0, 90.0)
        self._rz_range.setValue(15.0)
        self._rz_range.setSuffix(" °")
        form.addRow("RZ range ±:", self._rz_range)

        self._xy_range = QDoubleSpinBox()
        self._xy_range.setRange(0.0, 500.0)
        self._xy_range.setValue(60.0)
        self._xy_range.setSuffix(" mm")
        form.addRow("XY range ±:", self._xy_range)

        self._z_range = QDoubleSpinBox()
        self._z_range.setRange(0.0, 500.0)
        self._z_range.setValue(80.0)
        self._z_range.setSuffix(" mm")
        form.addRow("Z range ±:", self._z_range)

        self._probe_dx = QDoubleSpinBox()
        self._probe_dx.setRange(1.0, 100.0)
        self._probe_dx.setValue(15.0)
        self._probe_dx.setSuffix(" mm")
        form.addRow("Probe dX:", self._probe_dx)

        self._probe_dy = QDoubleSpinBox()
        self._probe_dy.setRange(1.0, 100.0)
        self._probe_dy.setValue(15.0)
        self._probe_dy.setSuffix(" mm")
        form.addRow("Probe dY:", self._probe_dy)

        self._probe_rotations = QCheckBox("Probe Rx/Ry/Rz (full 2×6 Jacobian)")
        self._probe_rotations.setChecked(True)
        form.addRow("Rotation probes:", self._probe_rotations)

        self._probe_drx = QDoubleSpinBox()
        self._probe_drx.setRange(1.0, 30.0)
        self._probe_drx.setValue(8.0)
        self._probe_drx.setSuffix(" °")
        form.addRow("Probe dRX:", self._probe_drx)

        self._probe_dry = QDoubleSpinBox()
        self._probe_dry.setRange(1.0, 30.0)
        self._probe_dry.setValue(8.0)
        self._probe_dry.setSuffix(" °")
        form.addRow("Probe dRY:", self._probe_dry)

        self._probe_drz = QDoubleSpinBox()
        self._probe_drz.setRange(1.0, 30.0)
        self._probe_drz.setValue(8.0)
        self._probe_drz.setSuffix(" °")
        form.addRow("Probe dRZ:", self._probe_drz)

        self._stab_delay = QDoubleSpinBox()
        self._stab_delay.setRange(0.0, 10.0)
        self._stab_delay.setSingleStep(0.1)
        self._stab_delay.setValue(1.0)
        self._stab_delay.setSuffix(" s")
        form.addRow("Stabilization delay (sample):", self._stab_delay)

        self._servo_stab_delay = QDoubleSpinBox()
        self._servo_stab_delay.setRange(0.0, 10.0)
        self._servo_stab_delay.setSingleStep(0.05)
        self._servo_stab_delay.setValue(0.2)
        self._servo_stab_delay.setSuffix(" s")
        form.addRow("Stabilization delay (servo):", self._servo_stab_delay)

        self._velocity = QSpinBox()
        self._velocity.setRange(1, 100)
        self._velocity.setValue(20)
        self._velocity.setSuffix(" %")
        form.addRow("Velocity:", self._velocity)

        self._acceleration = QSpinBox()
        self._acceleration.setRange(1, 100)
        self._acceleration.setValue(10)
        self._acceleration.setSuffix(" %")
        form.addRow("Acceleration:", self._acceleration)

        root.addWidget(settings_box)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._start_btn = QPushButton("Start Calibration")
        self._start_btn.setFixedHeight(36)
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setFixedHeight(36)
        self._stop_btn.setEnabled(False)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        root.addLayout(btn_row)

        # ── Sample counter badge ──────────────────────────────────────────────
        counter_row = QHBoxLayout()
        counter_row.setContentsMargins(0, 4, 0, 4)

        counter_lbl = QLabel("Samples captured:")
        counter_lbl.setStyleSheet("font-size: 11pt; font-weight: bold;")
        self._sample_counter = QLabel("0")
        self._sample_counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sample_counter.setMinimumWidth(120)
        self._sample_counter.setStyleSheet(_COUNTER_BASE)
        self._sample_counter.setCursor(Qt.CursorShape.ArrowCursor)

        counter_row.addStretch()
        counter_row.addWidget(counter_lbl)
        counter_row.addSpacing(10)
        counter_row.addWidget(self._sample_counter)
        counter_row.addStretch()
        root.addLayout(counter_row)

        # ── Log ───────────────────────────────────────────────────────────────
        log_box = QGroupBox("Log")
        log_layout = QVBoxLayout(log_box)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(180)
        log_layout.addWidget(self._log)
        root.addWidget(log_box)

        # ── Frame preview ─────────────────────────────────────────────────────
        self._preview = QLabel("No frame")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(160)
        self._preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._preview)

        # ── Wire signals ──────────────────────────────────────────────────────
        self._start_btn.clicked.connect(self._on_start_clicked)
        self._stop_btn.clicked.connect(self.stop_requested)

    def clean_up(self) -> None:
        self._flash_timer.stop()

    # ── Sample counter ────────────────────────────────────────────────────────

    def set_sample_count(self, n: int) -> None:
        self._sample_counter.setText(str(n))
        self._sample_counter.setStyleSheet(_COUNTER_FLASH)
        self._flash_timer.start()

    def _reset_counter_style(self) -> None:
        self._sample_counter.setStyleSheet(_COUNTER_BASE)

    # ── Accessors ─────────────────────────────────────────────────────────────

    def get_config(self) -> HandEyeConfig:
        return HandEyeConfig(
            chessboard_width=self._board_cols.value(),
            chessboard_height=self._board_rows.value(),
            square_size_mm=self._square_size.value(),
            n_poses=self._n_poses.value(),
            rx_range_deg=self._rx_range.value(),
            ry_range_deg=self._ry_range.value(),
            rz_range_deg=self._rz_range.value(),
            xy_range_mm=self._xy_range.value(),
            z_range_mm=self._z_range.value(),
            stabilization_delay_s=self._stab_delay.value(),
            servo_stabilization_delay_s=self._servo_stab_delay.value(),
            velocity=self._velocity.value(),
            acceleration=self._acceleration.value(),
            probe_dx_mm=self._probe_dx.value(),
            probe_dy_mm=self._probe_dy.value(),
            probe_rotations=self._probe_rotations.isChecked(),
            probe_drx_deg=self._probe_drx.value(),
            probe_dry_deg=self._probe_dry.value(),
            probe_drz_deg=self._probe_drz.value(),
        )

    def set_config(self, config: HandEyeConfig) -> None:
        self._board_cols.setValue(config.chessboard_width)
        self._board_rows.setValue(config.chessboard_height)
        self._square_size.setValue(config.square_size_mm)
        self._n_poses.setValue(config.n_poses)
        self._rx_range.setValue(config.rx_range_deg)
        self._ry_range.setValue(config.ry_range_deg)
        self._rz_range.setValue(config.rz_range_deg)
        self._xy_range.setValue(config.xy_range_mm)
        self._z_range.setValue(config.z_range_mm)
        self._stab_delay.setValue(config.stabilization_delay_s)
        self._servo_stab_delay.setValue(config.servo_stabilization_delay_s)
        self._velocity.setValue(config.velocity)
        self._acceleration.setValue(config.acceleration)
        self._probe_dx.setValue(config.probe_dx_mm)
        self._probe_dy.setValue(config.probe_dy_mm)
        self._probe_rotations.setChecked(config.probe_rotations)
        self._probe_drx.setValue(config.probe_drx_deg)
        self._probe_dry.setValue(config.probe_dry_deg)
        self._probe_drz.setValue(config.probe_drz_deg)

    def set_running(self, running: bool) -> None:
        self._start_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)

    def append_log(self, message: str) -> None:
        self._log.append(message)
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def set_frame(self, frame: np.ndarray) -> None:
        if frame is None:
            return
        h, w = frame.shape[:2]
        rgb = frame[:, :, ::-1].copy() if frame.ndim == 3 else frame
        if frame.ndim == 2:
            qimg = QImage(rgb.data, w, h, w, QImage.Format.Format_Grayscale8)
        else:
            qimg = QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self._preview.width(), self._preview.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(pix)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _on_start_clicked(self) -> None:
        self._sample_counter.setText("0")
        self._sample_counter.setStyleSheet(_COUNTER_BASE)
        self.save_config_requested.emit(self.get_config())
        self.start_requested.emit()
