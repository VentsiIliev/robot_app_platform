from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout,
)

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    APP_PAGE_TITLE_STYLE,
    BG_COLOR,
    BORDER,
    ERROR_COLOR,
    GHOST_BTN_STYLE,
    LABEL_STYLE,
    PRIMARY,
    PRIMARY_LIGHT,
    TERTIARY_TEXT,
    TEXT_COLOR,
    TEXT_ON_PRIMARY,
    TEXT_PRIMARY,
)
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.widgets.keyboard_number_field import KeyboardNumberField
from .paint_head_dial import PaintHeadDial


class _CameraPreview(QLabel):
    """Camera image with an inspection guide while no frame is available."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 240)
        self.setStyleSheet(f"background: {TEXT_PRIMARY}; border-radius: 12px;")
        self._empty_title = ""
        self._empty_detail = ""

    def set_empty_text(self, title: str, detail: str) -> None:
        self._empty_title = title
        self._empty_detail = detail
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.pixmap() and not self.pixmap().isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        guide = QPen(QColor(TERTIARY_TEXT), 1, Qt.PenStyle.DashLine)
        painter.setPen(guide)
        painter.drawLine(self.width() // 2, 0, self.width() // 2, self.height())
        painter.drawLine(0, self.height() // 2, self.width(), self.height() // 2)
        painter.setPen(QColor(TEXT_ON_PRIMARY))
        center = self.rect().adjusted(12, -22, -12, 0)
        painter.drawText(center, Qt.AlignmentFlag.AlignCenter, self._empty_title)
        painter.setPen(QColor(BORDER))
        painter.drawText(center.translated(0, 22), Qt.AlignmentFlag.AlignCenter, self._empty_detail)


class PaintAdjustmentView(IApplicationView):
    """Auxiliary preview with paint-adjustment requests."""

    more_paint_requested = pyqtSignal(int)
    less_paint_requested = pyqtSignal(int)
    adjustment_released = pyqtSignal()
    dial_drag_started = pyqtSignal()
    position_dragged = pyqtSignal(int)
    position_requested = pyqtSignal(int)
    refresh_position_requested = pyqtSignal()
    single_cycle_requested = pyqtSignal(float, float, float)
    next_section_requested = pyqtSignal(float, float, float)
    finish_dropoff_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        self._frame: QPixmap | None = None
        self._action_state = "unavailable"
        self._action_value: int | None = None
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
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self._page_title = QLabel()
        self._page_title.setStyleSheet(APP_PAGE_TITLE_STYLE)
        layout.addWidget(self._page_title)

        top = QHBoxLayout()
        top.setSpacing(12)
        camera_card = QFrame()
        camera_card.setObjectName("cameraCard")
        camera_card.setStyleSheet(
            f"QFrame#cameraCard {{ background: {TEXT_PRIMARY}; border-radius: 12px; }}"
        )
        camera_layout = QGridLayout(camera_card)
        camera_layout.setContentsMargins(0, 0, 0, 0)
        self._preview = _CameraPreview()
        camera_layout.addWidget(self._preview, 0, 0)
        self._status = QLabel()
        self._status.setStyleSheet(
            f"color: {TEXT_ON_PRIMARY}; background: {TEXT_COLOR}; border-radius: 14px;"
            "padding: 6px 12px; font-weight: bold;"
        )
        camera_layout.addWidget(
            self._status, 0, 0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
        )
        top.addWidget(camera_card, 1)

        sidebar = QVBoxLayout()
        sidebar.setSpacing(12)
        position_card, position_layout = self._card()
        self._dial_title = QLabel()
        self._dial_title.setStyleSheet(LABEL_STYLE)
        position_layout.addWidget(self._dial_title)
        self._dial = PaintHeadDial()
        self._dial.setEnabled(False)
        self._dial.drag_started.connect(self._on_dial_drag_started)
        self._dial.position_dragged.connect(self._on_dial_dragged)
        self._dial.position_requested.connect(self._on_dial_position)
        position_layout.addWidget(self._dial, 1)
        self._position_note = QLabel()
        self._position_note.setWordWrap(True)
        self._position_note.setStyleSheet(f"color: {TERTIARY_TEXT}; font-size: 9pt;")
        position_layout.addWidget(self._position_note)
        position_footer = QHBoxLayout()
        position_footer.addStretch(1)
        self._read_position_button = QPushButton()
        self._read_position_button.setMinimumWidth(180)
        self._read_position_button.setStyleSheet(GHOST_BTN_STYLE)
        self._read_position_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._read_position_button.clicked.connect(self._on_refresh_position)
        position_footer.addWidget(self._read_position_button)
        position_layout.addLayout(position_footer)
        sidebar.addWidget(position_card, 1)

        paint_card, paint_layout = self._card()
        self._step_label = QLabel()
        self._step_label.setWordWrap(True)
        self._step_label.setStyleSheet(f"color: {TERTIARY_TEXT}; font-size: 9pt; font-weight: bold;")
        self._step_input = KeyboardNumberField()
        self._step_input.setRange(1, 65535)
        self._step_input.setValue(1)
        self._step_input.setMinimumWidth(160)
        step_header = QHBoxLayout()
        step_header.addWidget(self._step_label, 1)
        step_header.addWidget(self._step_input)
        paint_layout.addLayout(step_header)
        step_row = QHBoxLayout()
        step_row.setSpacing(6)
        self._step_group = QButtonGroup(self)
        self._step_group.setExclusive(False)
        self._step_buttons = []
        for units in (1, 2, 3):
            button = QPushButton(str(units))
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(self._small_button_style())
            self._step_group.addButton(button, units)
            self._step_buttons.append(button)
            step_row.addWidget(button, 1)
        self._step_group.idClicked.connect(self._on_step_preset_clicked)
        self._step_input.valueChanged.connect(self._sync_step_buttons)
        self._sync_step_buttons(1)
        paint_layout.addLayout(step_row)
        controls = QHBoxLayout()
        controls.setSpacing(8)
        self._less_button = QPushButton()
        self._less_button.setStyleSheet(GHOST_BTN_STYLE)
        self._less_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._less_button.pressed.connect(self._on_less_paint)
        self._less_button.released.connect(self._on_adjustment_released)
        controls.addWidget(self._less_button, 1)
        self._more_button = QPushButton()
        self._more_button.setStyleSheet(ACTION_BTN_STYLE)
        self._more_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._more_button.pressed.connect(self._on_more_paint)
        self._more_button.released.connect(self._on_adjustment_released)
        controls.addWidget(self._more_button, 1)
        paint_layout.addLayout(controls)
        self._action_note = QLabel()
        self._action_note.setWordWrap(True)
        self._action_note.setStyleSheet(f"color: {TERTIARY_TEXT}; font-size: 9pt;")
        paint_layout.addWidget(self._action_note)
        sidebar.addWidget(paint_card)
        top.addLayout(sidebar)
        top.setStretch(0, 3)
        top.setStretch(1, 1)
        layout.addLayout(top, 1)

        bottom_card, bottom_layout = self._card()
        adjustment_fields = QHBoxLayout()
        adjustment_fields.setSpacing(12)
        self._length_label, self._length_input = self._adjustment_field(
            adjustment_fields, 0.1, 100.0, 10.0
        )
        self._axis_offset_label, self._axis_offset_input = self._adjustment_field(
            adjustment_fields, -200.0, 200.0, 0.0
        )
        self._perpendicular_offset_label, self._perpendicular_offset_input = self._adjustment_field(
            adjustment_fields, -200.0, 200.0, 0.0
        )
        bottom_layout.addLayout(adjustment_fields)

        cycle_row = QHBoxLayout()
        cycle_row.setSpacing(10)
        self._cycle_button = QPushButton()
        self._cycle_button.setStyleSheet(ACTION_BTN_STYLE)
        self._cycle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cycle_button.clicked.connect(self._on_single_cycle)
        cycle_row.addWidget(self._cycle_button, 1)
        self._next_button = QPushButton()
        self._next_button.setStyleSheet(ACTION_BTN_STYLE)
        self._next_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._next_button.clicked.connect(self._on_next_section)
        cycle_row.addWidget(self._next_button, 1)
        self._finish_button = QPushButton()
        self._finish_button.setStyleSheet(GHOST_BTN_STYLE)
        self._finish_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._finish_button.clicked.connect(self._on_finish_dropoff)
        cycle_row.addWidget(self._finish_button, 1)
        self._cycle_note = QLabel()
        self._cycle_note.setWordWrap(True)
        self._cycle_note.setStyleSheet(f"color: {TERTIARY_TEXT}; font-size: 9pt;")
        bottom_layout.addLayout(cycle_row)
        bottom_layout.addWidget(self._cycle_note)
        layout.addWidget(bottom_card)
        self.retranslateUi()

    @staticmethod
    def _card() -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("adjustmentCard")
        card.setStyleSheet(
            f"QFrame#adjustmentCard {{ background: {TEXT_ON_PRIMARY}; "
            f"border: 1px solid {BORDER}; border-radius: 12px; }}"
        )
        content = QVBoxLayout(card)
        content.setContentsMargins(12, 12, 12, 12)
        content.setSpacing(8)
        return card, content

    @staticmethod
    def _small_button_style() -> str:
        return (
            f"QPushButton {{ background: white; color: {TEXT_COLOR}; border: 1px solid {BORDER};"
            "border-radius: 8px; min-height: 38px; font-weight: bold; }"
            f"QPushButton:checked {{ background: {PRIMARY_LIGHT}; color: {PRIMARY};"
            f"border-color: {PRIMARY}; }}"
        )

    @staticmethod
    def _adjustment_field(row, minimum: float, maximum: float, initial: float):
        column = QVBoxLayout()
        column.setSpacing(4)
        label = QLabel()
        label.setStyleSheet(f"color: {TERTIARY_TEXT}; font-size: 9pt;")
        column.addWidget(label)
        field = KeyboardNumberField(decimal=True)
        field.setRange(minimum, maximum)
        field.setDecimals(1)
        field.setValue(initial)
        column.addWidget(field)
        row.addLayout(column, 1)
        return label, field

    def _on_step_preset_clicked(self, units: int) -> None:
        self._step_input.setValue(units)

    def _sync_step_buttons(self, value: int) -> None:
        for button in self._step_buttons:
            button.setChecked(self._step_group.id(button) == value)

    def set_frame(self, pixmap: QPixmap) -> None:
        self._frame = pixmap
        self._scale_frame()
        self._set_camera_status(self.tr("Live auxiliary camera"))

    def set_waiting_for_camera(self) -> None:
        self._frame = None
        self._preview.clear()
        self._set_camera_status(self.tr("Waiting for auxiliary camera…"))

    def _set_camera_status(self, message: str) -> None:
        self._status.setText(message)
        self._status.setMinimumWidth(self._status.fontMetrics().horizontalAdvance(message) + 32)

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

    def _on_adjustment_released(self) -> None:
        self.adjustment_released.emit()

    def _on_dial_position(self, value: int) -> None:
        self.position_requested.emit(value)

    def _on_dial_dragged(self, value: int) -> None:
        self.position_dragged.emit(value)

    def _on_dial_drag_started(self) -> None:
        self.dial_drag_started.emit()

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
        self._position_note.setStyleSheet(f"color: {TERTIARY_TEXT}; font-size: 9pt;")
        self._position_note.setToolTip("")
        self._position_note.setText(self.tr("Reading paint-head position…"))

    def set_confirmed_position(self, value: int | None) -> None:
        if value is not None:
            self._dial.set_actual(value)
        self._position_error = ""
        self._position_pending = False
        self._read_position_button.setEnabled(self._dial_enabled)
        self._position_note.setStyleSheet(f"color: {TERTIARY_TEXT}; font-size: 9pt;")
        self._position_note.setToolTip("")
        self._update_position_note()

    def set_position_error(self, message: str) -> None:
        self._position_error = message
        self._position_pending = False
        self._read_position_button.setEnabled(self._dial_enabled)
        self._position_note.setStyleSheet(f"color: {ERROR_COLOR}; font-size: 9pt; font-weight: bold;")
        self._position_note.setToolTip(message)
        self._update_position_note()

    def _update_position_note(self) -> None:
        if self._position_pending:
            text = self.tr("Reading paint-head position…")
        elif self._position_error:
            text = self.tr("Paint-head communication issue. It may be unplugged or missing.")
        elif self._dial.preview_value is not None:
            text = self.tr("Dry-run preview: {value} (not moved)").format(
                value=self._dial.format_position(self._dial.preview_value)
            )
        elif self._dial.actual_value is not None:
            text = self.tr("Last confirmed position: {value}").format(
                value=self._dial.format_position(self._dial.actual_value)
            )
        elif not self._dial_enabled:
            text = self.tr("Device disabled; position not read")
        else:
            text = self.tr("Position unknown")
        self._position_note.setText(text)

    def retranslateUi(self) -> None:
        self._page_title.setText(self.tr("Paint Adjustment — Auxiliary Camera"))
        self._preview.set_empty_text(
            self.tr("No camera image yet"),
            self.tr("Live view of the painted section appears here"),
        )
        self._step_label.setText(self.tr("Adjust paint · register units"))
        self._less_button.setText(self.tr("− Less paint"))
        self._more_button.setText(self.tr("+ More paint"))
        self._dial_title.setText(self.tr("Paint-head position"))
        self._read_position_button.setText(self.tr("Read position"))
        self._cycle_button.setText(self.tr("Start adjustment"))
        self._next_button.setText(self.tr("Paint next length"))
        self._finish_button.setText(self.tr("Finish / Dropoff"))
        self._length_label.setText(self.tr("Paint length (mm)"))
        self._axis_offset_label.setText(self.tr("Inspect along paint axis (mm)"))
        self._perpendicular_offset_label.setText(self.tr("Inspect perpendicular (mm)"))
        self._update_action_note()
        self._update_position_note()
        self._update_cycle_note()
        if self._frame is None:
            self._set_camera_status(self.tr("Waiting for auxiliary camera…"))
        else:
            self._set_camera_status(self.tr("Live auxiliary camera"))

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def clean_up(self) -> None:
        pass

    def set_paint_head_available(self, available: bool) -> None:
        self._action_state = "ready" if available else "unavailable"
        self._dial.setEnabled(available)
        self._step_input.setEnabled(available)
        for button in self._step_buttons:
            button.setEnabled(available)
        self._less_button.setEnabled(available)
        self._more_button.setEnabled(available)
        self._update_action_note()

    def set_action_pending(
        self, held_direction: str | None = None, *, keep_dial_enabled: bool = False
    ) -> None:
        self._action_state = "pending"
        self._dial.setEnabled(keep_dial_enabled)
        self._step_input.setEnabled(False)
        for button in self._step_buttons:
            button.setEnabled(False)
        self._less_button.setEnabled(held_direction == "less")
        self._more_button.setEnabled(held_direction == "more")
        self._update_action_note()

    def set_action_result(self, value: int, register: int, *, wrote: bool, relative: bool) -> None:
        self.set_paint_head_available(True)
        self._action_state = "success" if wrote else (
            "dry_run_relative" if relative else "dry_run_absolute"
        )
        self._action_value = value
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
        self._dial.cancel_drag()
        self._action_state = "error"
        self._action_error = message
        self._update_action_note()

    def _update_action_note(self) -> None:
        if self._action_state == "ready":
            text = self.tr("Ready")
        elif self._action_state == "pending":
            text = self.tr("Sending paint-head command…")
        elif self._action_state == "success":
            text = self.tr("Paint-head position: {value}").format(
                value=self._dial.format_position(self._action_value)
            )
        elif self._action_state in {"dry_run_relative", "dry_run_absolute"}:
            text = self.tr("Dry run: command simulated; no write.")
        elif self._action_state == "error":
            text = self.tr("Paint-head command failed: {error}").format(error=self._action_error)
        else:
            text = self.tr("Paint head is not configured for this profile.")
        self._action_note.setText(text)
