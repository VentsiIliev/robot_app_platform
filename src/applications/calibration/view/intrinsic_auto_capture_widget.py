from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton
from src.applications.base.app_styles import APP_DANGER_BUTTON_STYLE, APP_PRIMARY_BUTTON_STYLE
from src.applications.intrinsic_calibration_capture.service.i_intrinsic_capture_service import (
    ARUCO_DICT_OPTIONS,
    IntrinsicCaptureConfig,
)


class IntrinsicAutoCaptureWidget(QWidget):
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    config_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        layout.addLayout(form)

        board_type_row = QHBoxLayout()
        self._rb_chessboard = QRadioButton("Chessboard")
        self._rb_charuco = QRadioButton("CharuCo")
        self._rb_charuco.setChecked(True)
        self._board_group = QButtonGroup(self)
        self._board_group.addButton(self._rb_chessboard)
        self._board_group.addButton(self._rb_charuco)
        board_type_row.addWidget(self._rb_chessboard)
        board_type_row.addWidget(self._rb_charuco)
        board_type_row.addStretch(1)
        form.addRow("Board type:", board_type_row)

        self._board_cols = QSpinBox()
        self._board_cols.setRange(0, 50)
        self._board_cols.setSpecialValueText("auto")
        form.addRow("Board cols:", self._board_cols)

        self._board_rows = QSpinBox()
        self._board_rows.setRange(0, 50)
        self._board_rows.setSpecialValueText("auto")
        form.addRow("Board rows:", self._board_rows)

        self._square_size = QDoubleSpinBox()
        self._square_size.setRange(0.0, 200.0)
        self._square_size.setSuffix(" mm")
        self._square_size.setSpecialValueText("auto")
        form.addRow("Square size:", self._square_size)

        self._charuco_dict_label = QLabel("ArUco dict:")
        self._charuco_dict = QComboBox()
        for name in ARUCO_DICT_OPTIONS:
            self._charuco_dict.addItem(name)
        form.addRow(self._charuco_dict_label, self._charuco_dict)

        self._marker_size_label = QLabel("Marker size:")
        self._marker_size_mm = QDoubleSpinBox()
        self._marker_size_mm.setRange(0.0, 200.0)
        self._marker_size_mm.setSuffix(" mm")
        self._marker_size_mm.setSpecialValueText("auto")
        form.addRow(self._marker_size_label, self._marker_size_mm)

        self._grid_rows = QSpinBox()
        self._grid_rows.setRange(1, 10)
        self._grid_rows.setValue(3)
        form.addRow("Grid rows:", self._grid_rows)

        self._grid_cols = QSpinBox()
        self._grid_cols.setRange(1, 10)
        self._grid_cols.setValue(3)
        form.addRow("Grid cols:", self._grid_cols)

        self._tilt_deg = QDoubleSpinBox()
        self._tilt_deg.setRange(0.0, 30.0)
        self._tilt_deg.setValue(5.0)
        self._tilt_deg.setSuffix(" °")
        form.addRow("Tilt angle:", self._tilt_deg)

        self._z_delta_mm = QDoubleSpinBox()
        self._z_delta_mm.setRange(0.0, 200.0)
        self._z_delta_mm.setValue(40.0)
        self._z_delta_mm.setSuffix(" mm")
        form.addRow("Z delta:", self._z_delta_mm)

        self._sweep_x_label = QLabel("Sweep X half-range:")
        self._sweep_x_mm = QDoubleSpinBox()
        self._sweep_x_mm.setRange(10.0, 500.0)
        self._sweep_x_mm.setValue(100.0)
        self._sweep_x_mm.setSuffix(" mm")
        form.addRow(self._sweep_x_label, self._sweep_x_mm)

        self._sweep_y_label = QLabel("Sweep Y half-range:")
        self._sweep_y_mm = QDoubleSpinBox()
        self._sweep_y_mm.setRange(10.0, 500.0)
        self._sweep_y_mm.setValue(100.0)
        self._sweep_y_mm.setSuffix(" mm")
        form.addRow(self._sweep_y_label, self._sweep_y_mm)

        self._min_corners_label = QLabel("Min corners/frame:")
        self._min_corners = QSpinBox()
        self._min_corners.setRange(4, 100)
        self._min_corners.setValue(6)
        form.addRow(self._min_corners_label, self._min_corners)

        self._rz_deg_label = QLabel("RZ yaw variants (±):")
        self._rz_deg = QDoubleSpinBox()
        self._rz_deg.setRange(0.0, 45.0)
        self._rz_deg.setValue(15.0)
        self._rz_deg.setSuffix(" °")
        form.addRow(self._rz_deg_label, self._rz_deg)

        self._compute_hand_eye_label = QLabel("Auto hand-eye:")
        self._compute_hand_eye = QCheckBox("Enabled")
        self._compute_hand_eye.setChecked(True)
        form.addRow(self._compute_hand_eye_label, self._compute_hand_eye)

        self._stabilization_delay = QDoubleSpinBox()
        self._stabilization_delay.setRange(0.0, 5.0)
        self._stabilization_delay.setSingleStep(0.1)
        self._stabilization_delay.setValue(0.5)
        self._stabilization_delay.setSuffix(" s")
        form.addRow("Stabilization delay:", self._stabilization_delay)

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

        button_row = QHBoxLayout()
        self._start_btn = MaterialButton("Auto Capture")
        self._start_btn.setStyleSheet(APP_PRIMARY_BUTTON_STYLE)
        self._stop_btn = MaterialButton("Stop Auto Capture")
        self._stop_btn.setStyleSheet(APP_DANGER_BUTTON_STYLE)
        self._stop_btn.setEnabled(False)
        button_row.addWidget(self._start_btn)
        button_row.addWidget(self._stop_btn)
        layout.addLayout(button_row)

        self._rb_chessboard.toggled.connect(self._on_board_type_changed)
        self._start_btn.clicked.connect(self.start_requested.emit)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        self._on_board_type_changed(self._rb_chessboard.isChecked())

    def get_config(self) -> IntrinsicCaptureConfig:
        return IntrinsicCaptureConfig(
            board_type="charuco" if self._rb_charuco.isChecked() else "chessboard",
            chessboard_width=self._board_cols.value(),
            chessboard_height=self._board_rows.value(),
            square_size_mm=self._square_size.value(),
            aruco_dict=self._charuco_dict.currentText(),
            marker_size_mm=self._marker_size_mm.value(),
            grid_rows=self._grid_rows.value(),
            grid_cols=self._grid_cols.value(),
            tilt_deg=self._tilt_deg.value(),
            z_delta_mm=self._z_delta_mm.value(),
            stabilization_delay_s=self._stabilization_delay.value(),
            velocity=self._velocity.value(),
            acceleration=self._acceleration.value(),
            charuco_sweep_x_mm=self._sweep_x_mm.value(),
            charuco_sweep_y_mm=self._sweep_y_mm.value(),
            charuco_min_corners=self._min_corners.value(),
            charuco_rz_deg=self._rz_deg.value(),
            charuco_compute_hand_eye=self._compute_hand_eye.isChecked(),
        )

    def set_config(self, config: IntrinsicCaptureConfig) -> None:
        self._rb_charuco.setChecked(config.board_type == "charuco")
        self._rb_chessboard.setChecked(config.board_type != "charuco")
        self._board_cols.setValue(config.chessboard_width)
        self._board_rows.setValue(config.chessboard_height)
        self._square_size.setValue(config.square_size_mm)
        self._charuco_dict.setCurrentText(config.aruco_dict)
        self._marker_size_mm.setValue(config.marker_size_mm)
        self._grid_rows.setValue(config.grid_rows)
        self._grid_cols.setValue(config.grid_cols)
        self._tilt_deg.setValue(config.tilt_deg)
        self._z_delta_mm.setValue(config.z_delta_mm)
        self._stabilization_delay.setValue(config.stabilization_delay_s)
        self._velocity.setValue(config.velocity)
        self._acceleration.setValue(config.acceleration)
        self._sweep_x_mm.setValue(config.charuco_sweep_x_mm)
        self._sweep_y_mm.setValue(config.charuco_sweep_y_mm)
        self._min_corners.setValue(config.charuco_min_corners)
        self._rz_deg.setValue(config.charuco_rz_deg)
        self._compute_hand_eye.setChecked(config.charuco_compute_hand_eye)
        self._on_board_type_changed(self._rb_chessboard.isChecked())

    def set_running(self, running: bool) -> None:
        self._start_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)

    def _on_board_type_changed(self, chessboard_selected: bool) -> None:
        charuco = not chessboard_selected
        for widget in (
            self._charuco_dict_label, self._charuco_dict,
            self._marker_size_label, self._marker_size_mm,
            self._sweep_x_label, self._sweep_x_mm,
            self._sweep_y_label, self._sweep_y_mm,
            self._min_corners_label, self._min_corners,
            self._rz_deg_label, self._rz_deg,
            self._compute_hand_eye_label, self._compute_hand_eye,
        ):
            widget.setVisible(charuco)
