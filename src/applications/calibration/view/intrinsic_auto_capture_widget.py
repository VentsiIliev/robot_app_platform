from __future__ import annotations

from dataclasses import replace

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from pl_gui.settings.settings_view.styles import BORDER, PRIMARY, TEXT_COLOR
from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton
from src.applications.base.app_styles import APP_DANGER_BUTTON_STYLE, APP_PRIMARY_BUTTON_STYLE
from src.applications.base.widgets.keyboard_number_field import KeyboardNumberField
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
        self._config = IntrinsicCaptureConfig()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._settings_form = QWidget()
        self._settings_grid = QGridLayout(self._settings_form)
        self._settings_grid.setContentsMargins(4, 12, 4, 4)
        self._settings_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._settings_grid.setHorizontalSpacing(16)
        self._settings_grid.setVerticalSpacing(16)
        for column in range(3):
            self._settings_grid.setColumnStretch(column, 1)
        self._field_index = 0
        self._field_cells: list[QWidget] = []
        self._charuco_fields: list[QWidget] = []
        self._labels: list[tuple[QLabel, str]] = []

        board_type_row = QHBoxLayout()
        self._rb_chessboard = QRadioButton("Chessboard")
        self._rb_charuco = QRadioButton("CharuCo")
        for radio in (self._rb_chessboard, self._rb_charuco):
            radio.setMinimumHeight(44)
            radio.setCursor(Qt.CursorShape.PointingHandCursor)
            radio.setStyleSheet("QRadioButton::indicator { width: 22px; height: 22px; }")
        self._rb_charuco.setChecked(True)
        self._board_group = QButtonGroup(self)
        self._board_group.addButton(self._rb_chessboard)
        self._board_group.addButton(self._rb_charuco)
        board_type_row.addWidget(self._rb_chessboard)
        board_type_row.addWidget(self._rb_charuco)
        board_type_row.addStretch(1)
        board_type = QWidget()
        board_type.setLayout(board_type_row)
        self._add_field("Board type", board_type)

        self._board_cols = KeyboardNumberField()
        self._board_cols.setRange(0, 50)
        self._board_cols.setSpecialValueText("auto")
        self._add_field("Board cols", self._board_cols)

        self._board_rows = KeyboardNumberField()
        self._board_rows.setRange(0, 50)
        self._board_rows.setSpecialValueText("auto")
        self._add_field("Board rows", self._board_rows)

        self._square_size = KeyboardNumberField(decimal=True)
        self._square_size.setRange(0.0, 200.0)
        self._square_size.setSuffix(" mm")
        self._square_size.setSpecialValueText("auto")
        self._add_field("Square size", self._square_size)

        self._charuco_dict = QComboBox()
        self._charuco_dict.setMinimumHeight(48)
        self._charuco_dict.setCursor(Qt.CursorShape.PointingHandCursor)
        self._charuco_dict.setStyleSheet(
            f"QComboBox {{ background: white; color: {TEXT_COLOR}; border: 1px solid {BORDER}; "
            "border-radius: 8px; padding: 0 10px; }"
        )
        for name in ARUCO_DICT_OPTIONS:
            self._charuco_dict.addItem(name)
        self._charuco_fields.append(self._add_field("ArUco dict", self._charuco_dict))

        self._marker_size_mm = KeyboardNumberField(decimal=True)
        self._marker_size_mm.setRange(0.0, 200.0)
        self._marker_size_mm.setSuffix(" mm")
        self._marker_size_mm.setSpecialValueText("auto")
        self._charuco_fields.append(self._add_field("Marker size", self._marker_size_mm))

        self._grid_rows = KeyboardNumberField()
        self._grid_rows.setRange(1, 10)
        self._grid_rows.setValue(3)
        self._add_field("Grid rows", self._grid_rows)

        self._grid_cols = KeyboardNumberField()
        self._grid_cols.setRange(1, 10)
        self._grid_cols.setValue(3)
        self._add_field("Grid cols", self._grid_cols)

        self._tilt_deg = KeyboardNumberField(decimal=True)
        self._tilt_deg.setRange(0.0, 30.0)
        self._tilt_deg.setValue(5.0)
        self._tilt_deg.setSuffix(" °")
        self._add_field("Tilt angle", self._tilt_deg)

        self._z_delta_mm = KeyboardNumberField(decimal=True)
        self._z_delta_mm.setRange(0.0, 200.0)
        self._z_delta_mm.setValue(40.0)
        self._z_delta_mm.setSuffix(" mm")
        self._add_field("Z delta", self._z_delta_mm)

        self._sweep_x_mm = KeyboardNumberField(decimal=True)
        self._sweep_x_mm.setRange(10.0, 500.0)
        self._sweep_x_mm.setValue(100.0)
        self._sweep_x_mm.setSuffix(" mm")
        self._charuco_fields.append(self._add_field("Sweep X half-range", self._sweep_x_mm))

        self._sweep_y_mm = KeyboardNumberField(decimal=True)
        self._sweep_y_mm.setRange(10.0, 500.0)
        self._sweep_y_mm.setValue(100.0)
        self._sweep_y_mm.setSuffix(" mm")
        self._charuco_fields.append(self._add_field("Sweep Y half-range", self._sweep_y_mm))

        self._min_corners = KeyboardNumberField()
        self._min_corners.setRange(4, 100)
        self._min_corners.setValue(6)
        self._charuco_fields.append(self._add_field("Min corners/frame", self._min_corners))

        self._rz_deg = KeyboardNumberField(decimal=True)
        self._rz_deg.setRange(0.0, 45.0)
        self._rz_deg.setValue(15.0)
        self._rz_deg.setSuffix(" °")
        self._charuco_fields.append(self._add_field("RZ yaw variants (±)", self._rz_deg))

        self._compute_hand_eye = QCheckBox("Enabled")
        self._compute_hand_eye.setChecked(True)
        self._compute_hand_eye.setMinimumHeight(48)
        self._compute_hand_eye.setCursor(Qt.CursorShape.PointingHandCursor)
        self._compute_hand_eye.setStyleSheet("QCheckBox::indicator { width: 22px; height: 22px; }")
        self._charuco_fields.append(self._add_field("Auto hand-eye", self._compute_hand_eye))

        self._stabilization_delay = KeyboardNumberField(decimal=True)
        self._stabilization_delay.setRange(0.0, 5.0)
        self._stabilization_delay.setSingleStep(0.1)
        self._stabilization_delay.setValue(0.5)
        self._stabilization_delay.setSuffix(" s")
        self._add_field("Stabilization delay", self._stabilization_delay)

        self._velocity = KeyboardNumberField()
        self._velocity.setRange(1, 100)
        self._velocity.setValue(20)
        self._velocity.setSuffix(" %")
        self._add_field("Velocity", self._velocity)

        self._acceleration = KeyboardNumberField()
        self._acceleration.setRange(1, 100)
        self._acceleration.setValue(10)
        self._acceleration.setSuffix(" %")
        self._add_field("Acceleration", self._acceleration)

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
        self.retranslateUi()

    def _add_field(self, title: str, editor: QWidget) -> QWidget:
        cell = QWidget()
        cell_layout = QVBoxLayout(cell)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        cell_layout.setSpacing(6)
        label = QLabel(title)
        label.setStyleSheet(f"color: {PRIMARY}; font-size: 9pt; background: transparent;")
        self._labels.append((label, title))
        cell_layout.addWidget(label)
        cell_layout.addWidget(editor)
        self._settings_grid.addWidget(cell, self._field_index // 3, self._field_index % 3)
        self._field_cells.append(cell)
        self._field_index += 1
        return cell

    def settings_widget(self) -> QWidget:
        return self._settings_form

    def setEnabled(self, enabled: bool) -> None:
        super().setEnabled(enabled)
        if hasattr(self, "_settings_form"):
            self._settings_form.setEnabled(enabled)

    def retranslateUi(self) -> None:
        for label, source in self._labels:
            label.setText(self.tr(source) or source)
        self._rb_chessboard.setText(self.tr("Chessboard") or "Chessboard")
        self._compute_hand_eye.setText(self.tr("Enabled") or "Enabled")
        self._start_btn.setText(self.tr("Auto Capture") or "Auto Capture")
        self._stop_btn.setText(self.tr("Stop Auto Capture") or "Stop Auto Capture")

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange and hasattr(self, "_labels"):
            self.retranslateUi()
        super().changeEvent(event)

    def get_config(self) -> IntrinsicCaptureConfig:
        return replace(
            self._config,
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
        self._config = config
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
        for cell in self._field_cells:
            self._settings_grid.removeWidget(cell)
        visible_cells = [cell for cell in self._field_cells if charuco or cell not in self._charuco_fields]
        for cell in self._field_cells:
            cell.setVisible(cell in visible_cells)
        for index, cell in enumerate(visible_cells):
            self._settings_grid.addWidget(cell, index // 3, index % 3)
