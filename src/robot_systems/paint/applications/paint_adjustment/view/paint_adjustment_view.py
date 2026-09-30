from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QButtonGroup, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    BG_COLOR,
    BORDER,
    GHOST_BTN_STYLE,
    LABEL_STYLE,
)
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.widgets.custom_virtual_keyboard import KeyboardDoubleSpinBox, KeyboardSpinBox
from .paint_head_dial import PaintHeadDial


class PaintAdjustmentView(IApplicationView):
    """Auxiliary preview with paint-adjustment requests."""

    more_paint_requested = pyqtSignal(int)
    less_paint_requested = pyqtSignal(int)
    setting_requested = pyqtSignal(int)
    refresh_position_requested = pyqtSignal()
    single_cycle_requested = pyqtSignal(float, float, float)
    next_section_requested = pyqtSignal(float, float, float)
    finish_dropoff_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        self._frame: QPixmap | None = None
        self._action_state = "unavailable"
        self._action_value: int | None = None
        self._action_register: int | None = None
        self._action_error = ""
        self._position_error = ""
        self._position_pending = False
        self._dial_enabled = False
        self._cycle_state = "idle"
        self._cycle_message = ""
        self._adjustment_phase = "idle"
        self._adjustment_progress = (0.0, 0.0)
        super().__init__("PaintAdjustment", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._title = QLabel()
        self._title.setStyleSheet(LABEL_STYLE)
        layout.addWidget(self._title)

        self._preview = QLabel()
        self._preview.setMinimumSize(320, 240)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet(f"border: 1px solid {BORDER};")
        preview_row = QHBoxLayout()
        preview_row.addWidget(self._preview, 3)
        dial_column = QVBoxLayout()
        self._dial_title = QLabel()
        self._dial_title.setStyleSheet(LABEL_STYLE)
        dial_column.addWidget(self._dial_title)
        self._dial = PaintHeadDial()
        dial_column.addWidget(self._dial, 1)
        self._position_note = QLabel()
        self._position_note.setWordWrap(True)
        dial_column.addWidget(self._position_note)
        self._read_position_button = QPushButton()
        self._read_position_button.setStyleSheet(GHOST_BTN_STYLE)
        self._read_position_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._read_position_button.clicked.connect(self._on_refresh_position)
        dial_column.addWidget(self._read_position_button)
        preview_row.addLayout(dial_column, 1)
        layout.addLayout(preview_row, 1)

        controls = QHBoxLayout()
        self._step_label = QLabel()
        self._step_label.setStyleSheet(LABEL_STYLE)
        controls.addWidget(self._step_label)
        self._step_input = KeyboardSpinBox()
        self._step_input.setMinimum(1)
        self._step_input.setMaximum(2_147_483_647)
        self._step_input.setValue(1)
        controls.addWidget(self._step_input)
        self._less_button = QPushButton()
        self._less_button.setStyleSheet(GHOST_BTN_STYLE)
        self._less_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._less_button.clicked.connect(self._on_less_paint)
        controls.addWidget(self._less_button)
        self._more_button = QPushButton()
        self._more_button.setStyleSheet(ACTION_BTN_STYLE)
        self._more_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._more_button.clicked.connect(self._on_more_paint)
        controls.addWidget(self._more_button)
        layout.addLayout(controls)

        presets = QVBoxLayout()
        self._presets_label = QLabel()
        self._presets_label.setStyleSheet(LABEL_STYLE)
        presets.addWidget(self._presets_label)
        self._preset_group = QButtonGroup(self)
        self._preset_group.idClicked.connect(self._on_preset_clicked)
        self._preset_buttons: list[QPushButton] = []
        self._presets_grid = QGridLayout()
        self._presets_grid.setSpacing(8)
        presets.addLayout(self._presets_grid)
        layout.addLayout(presets)

        adjustment_fields = QHBoxLayout()
        self._length_label = QLabel()
        adjustment_fields.addWidget(self._length_label)
        self._length_input = KeyboardDoubleSpinBox()
        self._length_input.setRange(0.1, 100.0)
        self._length_input.setDecimals(1)
        self._length_input.setValue(10.0)
        adjustment_fields.addWidget(self._length_input)
        self._axis_offset_label = QLabel()
        adjustment_fields.addWidget(self._axis_offset_label)
        self._axis_offset_input = KeyboardDoubleSpinBox()
        self._axis_offset_input.setRange(-200.0, 200.0)
        self._axis_offset_input.setDecimals(1)
        adjustment_fields.addWidget(self._axis_offset_input)
        self._perpendicular_offset_label = QLabel()
        adjustment_fields.addWidget(self._perpendicular_offset_label)
        self._perpendicular_offset_input = KeyboardDoubleSpinBox()
        self._perpendicular_offset_input.setRange(-200.0, 200.0)
        self._perpendicular_offset_input.setDecimals(1)
        adjustment_fields.addWidget(self._perpendicular_offset_input)
        layout.addLayout(adjustment_fields)

        cycle_row = QHBoxLayout()
        self._cycle_button = QPushButton()
        self._cycle_button.setStyleSheet(ACTION_BTN_STYLE)
        self._cycle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cycle_button.clicked.connect(self._on_single_cycle)
        cycle_row.addWidget(self._cycle_button)
        self._next_button = QPushButton()
        self._next_button.setStyleSheet(ACTION_BTN_STYLE)
        self._next_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_button.clicked.connect(self._on_next_section)
        cycle_row.addWidget(self._next_button)
        self._finish_button = QPushButton()
        self._finish_button.setStyleSheet(GHOST_BTN_STYLE)
        self._finish_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._finish_button.clicked.connect(self._on_finish_dropoff)
        cycle_row.addWidget(self._finish_button)
        self._cycle_note = QLabel()
        self._cycle_note.setWordWrap(True)
        cycle_row.addWidget(self._cycle_note, 1)
        layout.addLayout(cycle_row)

        self._action_note = QLabel()
        layout.addWidget(self._action_note)

        self._status = QLabel()
        self._status.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._status)
        self.retranslateUi()

    def set_preset_count(self, count: int) -> None:
        """Rebuild only when the live configured count changes."""
        if len(self._preset_buttons) == count:
            return
        for button in self._preset_buttons:
            self._preset_group.removeButton(button)
            self._presets_grid.removeWidget(button)
            button.deleteLater()
        self._preset_buttons.clear()
        for setting in range(1, count + 1):
            button = QPushButton()
            button.setStyleSheet(GHOST_BTN_STYLE)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._preset_group.addButton(button, setting)
            self._preset_buttons.append(button)
            self._presets_grid.addWidget(button, (setting - 1) // 6, (setting - 1) % 6)
            button.setEnabled(self._more_button.isEnabled())
            button.setText(self.tr("Setting {number}").format(number=setting))

    def set_frame(self, pixmap: QPixmap) -> None:
        self._frame = pixmap
        self._scale_frame()
        self._status.setText(self.tr("Live auxiliary camera"))

    def set_waiting_for_camera(self) -> None:
        self._frame = None
        self._preview.clear()
        self._status.setText(self.tr("Waiting for auxiliary camera…"))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._scale_frame()

    def _scale_frame(self) -> None:
        if self._frame is not None:
            self._preview.setPixmap(
                self._frame.scaled(
                    self._preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def _on_less_paint(self) -> None:
        self.less_paint_requested.emit(self._step_input.value())

    def _on_more_paint(self) -> None:
        self.more_paint_requested.emit(self._step_input.value())

    def _on_preset_clicked(self, setting: int) -> None:
        self.setting_requested.emit(setting)

    def _on_refresh_position(self) -> None:
        self.refresh_position_requested.emit()

    def _on_single_cycle(self) -> None:
        self.single_cycle_requested.emit(*self._adjustment_values())

    def _on_next_section(self) -> None:
        self.next_section_requested.emit(*self._adjustment_values())

    def _on_finish_dropoff(self) -> None:
        self.finish_dropoff_requested.emit()

    def _adjustment_values(self) -> tuple[float, float, float]:
        return (
            self._length_input.value(),
            self._axis_offset_input.value(),
            self._perpendicular_offset_input.value(),
        )

    def set_adjustment_options(self, length: float, axis: float, perpendicular: float) -> None:
        self._length_input.setValue(length)
        self._axis_offset_input.setValue(axis)
        self._perpendicular_offset_input.setValue(perpendicular)

    def set_adjustment_status(self, phase: str, travelled: float, total: float) -> None:
        self._adjustment_phase = phase
        self._adjustment_progress = (travelled, total)
        self._update_cycle_controls()
        self._update_cycle_note()

    def _update_cycle_controls(self) -> None:
        running_inspect = self._cycle_state == "running" and self._adjustment_phase == "inspect"
        travelled, total = self._adjustment_progress
        self._next_button.setEnabled(running_inspect and travelled < total - 1e-6)
        self._finish_button.setEnabled(running_inspect and travelled > 1e-6)

    def set_cycle_state(self, state: str, message: str = "") -> None:
        self._cycle_state = state
        self._cycle_message = message
        self._cycle_button.setEnabled(state in {"idle", "stopped"})
        self._update_cycle_controls()
        self._update_cycle_note()

    def set_cycle_start_pending(self) -> None:
        self.set_cycle_state("starting")

    def set_cycle_start_failed(self) -> None:
        self.set_cycle_state("idle", self.tr("Could not start; check process status on Dashboard."))


    def _update_cycle_note(self) -> None:
        if self._cycle_message:
            text = self._cycle_message
        elif self._cycle_state == "running" and self._adjustment_phase == "waiting_for_workpiece":
            text = self.tr("No workpiece found. Waiting for a workpiece. Stop from Dashboard.")
        elif self._cycle_state == "running" and self._adjustment_phase == "inspect":
            travelled, total = self._adjustment_progress
            text = self.tr("Painted {travelled:.1f} / {total:.1f} mm. Inspect, then paint next or finish.").format(
                travelled=travelled, total=total
            )
        elif self._cycle_state == "running":
            text = self.tr("Adjustment motion in progress. Stop or pause it from Dashboard.")
        elif self._cycle_state == "paused":
            text = self.tr("Paint cycle paused. Resume or stop it from Dashboard.")
        elif self._cycle_state == "starting":
            text = self.tr("Starting one paint cycle…")
        elif self._cycle_state == "error":
            text = self.tr("Paint process error; reset it from Dashboard.")
        else:
            text = self.tr("Set inspection offsets before Start. Magazine load stays off.")
        self._cycle_note.setText(text)

    def set_dial_config(self, minimum: int, spacing: int, count: int, enabled: bool) -> None:
        self._dial.configure(minimum, spacing, count)
        self._dial_enabled = enabled
        self._read_position_button.setEnabled(enabled)
        self._update_position_note()

    def set_position_pending(self) -> None:
        self._position_error = ""
        self._position_pending = True
        self._read_position_button.setEnabled(False)
        self._position_note.setText(self.tr("Reading paint-head position…"))

    def set_confirmed_position(self, value: int | None) -> None:
        if value is not None:
            self._dial.set_actual(value)
        self._position_error = ""
        self._position_pending = False
        self._read_position_button.setEnabled(self._dial_enabled)
        self._update_position_note()

    def set_position_error(self, message: str) -> None:
        self._position_error = message
        self._position_pending = False
        self._read_position_button.setEnabled(self._dial_enabled)
        self._update_position_note()

    def _update_position_note(self) -> None:
        if self._position_pending:
            text = self.tr("Reading paint-head position…")
        elif self._position_error:
            text = self.tr("Position read failed: {error}").format(error=self._position_error)
        elif self._dial.preview_value is not None:
            text = self.tr("Dry-run preview: {value} (not moved)").format(
                value=self._dial.preview_value
            )
        elif self._dial.actual_value is not None:
            text = self.tr("Last confirmed position: {value}").format(
                value=self._dial.actual_value
            )
        elif not self._dial_enabled:
            text = self.tr("Device disabled; position not read")
        else:
            text = self.tr("Position unknown")
        self._position_note.setText(text)

    def retranslateUi(self) -> None:
        self._title.setText(self.tr("Paint Adjustment — Auxiliary Camera"))
        self._step_label.setText(self.tr("Move by (degrees)"))
        self._less_button.setText(self.tr("− Less paint"))
        self._more_button.setText(self.tr("+ More paint"))
        self._presets_label.setText(self.tr("Go to setting"))
        self._dial_title.setText(self.tr("Paint-head position"))
        self._read_position_button.setText(self.tr("Read position"))
        self._cycle_button.setText(self.tr("Start paint adjustment"))
        self._next_button.setText(self.tr("Paint next length"))
        self._finish_button.setText(self.tr("Finish / Dropoff"))
        self._length_label.setText(self.tr("Paint length (mm)"))
        self._axis_offset_label.setText(self.tr("Inspect paint-axis (mm)"))
        self._perpendicular_offset_label.setText(self.tr("Inspect perpendicular (mm)"))
        for setting, button in enumerate(self._preset_buttons, start=1):
            button.setText(self.tr("Setting {number}").format(number=setting))
        self._update_action_note()
        self._update_position_note()
        self._update_cycle_note()
        if self._frame is None:
            self._status.setText(self.tr("Waiting for auxiliary camera…"))
        else:
            self._status.setText(self.tr("Live auxiliary camera"))

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def clean_up(self) -> None:
        pass

    def set_paint_head_available(self, available: bool) -> None:
        self._action_state = "ready" if available else "unavailable"
        self._step_input.setEnabled(available)
        self._less_button.setEnabled(available)
        self._more_button.setEnabled(available)
        for button in self._preset_buttons:
            button.setEnabled(available)
        self._update_action_note()

    def set_action_pending(self) -> None:
        self._action_state = "pending"
        self._step_input.setEnabled(False)
        self._less_button.setEnabled(False)
        self._more_button.setEnabled(False)
        for button in self._preset_buttons:
            button.setEnabled(False)
        self._update_action_note()

    def set_action_result(self, value: int, register: int, *, wrote: bool, relative: bool) -> None:
        self.set_paint_head_available(True)
        self._action_state = "success" if wrote else (
            "dry_run_relative" if relative else "dry_run_absolute"
        )
        self._action_value = value
        self._action_register = register
        if wrote:
            self._dial.set_actual(value)
        elif relative:
            actual = self._dial.actual_value
            self._dial.set_preview(None if actual is None else actual + value)
        else:
            self._dial.set_preview(value)
        self._update_action_note()
        self._update_position_note()

    def set_action_error(self, message: str) -> None:
        self.set_paint_head_available(True)
        self._action_state = "error"
        self._action_error = message
        self._update_action_note()

    def _update_action_note(self) -> None:
        if self._action_state == "ready":
            text = self.tr("Ready")
        elif self._action_state == "pending":
            text = self.tr("Sending paint-head command…")
        elif self._action_state == "success":
            text = self.tr("Paint-head position: {value}").format(value=self._action_value)
        elif self._action_state == "dry_run_relative":
            text = self.tr("Dry run: register {register} delta {value:+d}; no write.").format(
                register=self._action_register, value=self._action_value
            )
        elif self._action_state == "dry_run_absolute":
            text = self.tr("Dry run: would write {value} to register {register}.").format(
                value=self._action_value, register=self._action_register
            )
        elif self._action_state == "error":
            text = self.tr("Paint-head command failed: {error}").format(error=self._action_error)
        else:
            text = self.tr("Paint head is not configured for this profile.")
        self._action_note.setText(text)
