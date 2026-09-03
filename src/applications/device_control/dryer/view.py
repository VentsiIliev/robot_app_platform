from __future__ import annotations

import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    BG_COLOR,
    BORDER,
    ERROR_COLOR,
    GHOST_BTN_STYLE,
    LABEL_STYLE,
    PRIMARY,
    PRIMARY_LIGHT,
    SAVE_BUTTON_STYLE,
    TAB_WIDGET_STYLE,
    TERTIARY_TEXT,
    TEXT_COLOR,
    TOUCH_SCROLL_AREA_STYLE,
)
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.keyboard_settings_view import build_with_keyboard_setting_handlers
from src.applications.base.widgets.custom_virtual_keyboard import (
    KeyboardDoubleSpinBox,
    KeyboardSpinBox,
)
from src.applications.device_control.dryer.mapper import DryerConfigMapper
from src.applications.device_control.dryer.schema import REGISTER_GROUP, TIMING_GROUP
from src.engine.hardware.dryer.models.dryer_state import DryerState


_logger = logging.getLogger(__name__)


_STATUS_STYLE = f"""
QLabel {{
    background: white;
    color: {TEXT_COLOR};
    border: 2px solid {BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 11pt;
    font-weight: bold;
    min-height: 38px;
}}
"""

_STATUS_ACTIVE = f"""
QLabel {{
    background: {PRIMARY_LIGHT};
    color: {PRIMARY};
    border: 2px solid {PRIMARY};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 11pt;
    font-weight: bold;
    min-height: 38px;
}}
"""

_STATUS_MUTED = f"""
QLabel {{
    background: white;
    color: {TERTIARY_TEXT};
    border: 2px solid {BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 11pt;
    font-weight: bold;
    min-height: 38px;
}}
"""

_STATUS_ERROR = f"""
QLabel {{
    background: white;
    color: {ERROR_COLOR};
    border: 2px solid {ERROR_COLOR};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 11pt;
    font-weight: bold;
    min-height: 38px;
}}
"""


def _make_scroll(widget: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setStyleSheet(TOUCH_SCROLL_AREA_STYLE)
    scroll.setWidget(widget)
    return scroll


class DryerControlPanel(IApplicationView):
    save_requested = pyqtSignal(dict)
    refresh_status_requested = pyqtSignal()
    move_servos_requested = pyqtSignal()
    open_plate_requested = pyqtSignal()
    close_plate_requested = pyqtSignal()
    next_position_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("DryerControlPanel", parent)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._setting_inputs: dict[str, KeyboardSpinBox | KeyboardDoubleSpinBox] = {}
        build_with_keyboard_setting_handlers(self._build_setting_tables)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(TAB_WIDGET_STYLE)
        self._tabs.addTab(_make_scroll(self._build_settings_tab()), "Settings")
        self._tabs.addTab(_make_scroll(self._build_test_tab()), "Test")

        self._save_btn = QPushButton("Save")
        self._save_btn.setStyleSheet(SAVE_BUTTON_STYLE)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._on_save)

        content = QWidget()
        content.setStyleSheet(f"background: {BG_COLOR};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)
        content_layout.addWidget(self._tabs)
        content_layout.addWidget(self._save_btn)

        layout.addWidget(content)
        layout.addWidget(self._build_status_bar())

    def _build_setting_tables(self) -> None:
        self._register_table = self._make_settings_table(REGISTER_GROUP)
        self._timing_table = self._make_settings_table(TIMING_GROUP)

    def _make_settings_table(self, group) -> QTableWidget:
        table = QTableWidget(len(group.fields), 2)
        table.setHorizontalHeaderLabels([self.tr("Parameter"), self.tr("Value")])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setShowGrid(True)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setStyleSheet(self._settings_table_style())
        table.setMinimumHeight(44 + (52 * len(group.fields)))

        for row, field in enumerate(group.fields):
            label = QTableWidgetItem(field.label)
            label.setFlags(label.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 0, label)

            if field.widget_type == "double_spinbox":
                editor = KeyboardDoubleSpinBox()
                editor.setDecimals(field.decimals)
            else:
                editor = KeyboardSpinBox()
            editor.setRange(field.min_val, field.max_val)
            editor.setSingleStep(field.step)
            if field.suffix:
                editor.setSuffix(field.suffix)
            editor.setValue(field.default)
            editor.setMinimumHeight(42)
            table.setCellWidget(row, 1, editor)
            table.setRowHeight(row, 52)
            self._setting_inputs[field.key] = editor
        return table

    @staticmethod
    def _settings_table_style() -> str:
        return f"""
        QTableWidget {{
            background: white;
            alternate-background-color: {BG_COLOR};
            color: {TEXT_COLOR};
            border: 2px solid {BORDER};
            border-radius: 8px;
            gridline-color: {BORDER};
        }}
        QTableWidget::item {{
            border-bottom: 1px solid {BORDER};
            border-right: 1px solid {BORDER};
            padding: 8px 10px;
        }}
        QHeaderView::section {{
            background: {BG_COLOR};
            color: {TEXT_COLOR};
            border: none;
            border-right: 1px solid {BORDER};
            border-bottom: 2px solid {BORDER};
            padding: 8px 10px;
            font-size: 10pt;
            font-weight: bold;
        }}
        """

    def _build_settings_tab(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet(f"background: {BG_COLOR};")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        tables = QHBoxLayout()
        tables.setSpacing(16)
        tables.addWidget(self._wrap_settings_table(REGISTER_GROUP.title, self._register_table))
        tables.addWidget(self._wrap_settings_table(TIMING_GROUP.title, self._timing_table))
        layout.addLayout(tables)
        layout.addStretch()
        return widget

    @staticmethod
    def _wrap_settings_table(title: str, table: QTableWidget) -> QWidget:
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = QLabel(title)
        heading.setStyleSheet(LABEL_STYLE)
        layout.addWidget(heading)
        layout.addWidget(table)
        return wrapper

    def _build_test_tab(self) -> QWidget:
        widget = QWidget()
        widget.setStyleSheet(f"background: {BG_COLOR};")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        layout.addWidget(self._build_state_panel())
        layout.addWidget(self._build_command_panel())
        layout.addStretch()
        return widget

    def _build_state_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: white; border: 2px solid {BORDER}; border-radius: 8px;")
        layout = QGridLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        self._raw_status = self._make_value_label()
        self._ready_status = self._make_value_label()
        self._moving_status = self._make_value_label()
        self._plate_status = self._make_value_label()
        self._health_status = self._make_value_label()

        rows = [
            ("Raw Status", self._raw_status),
            ("Ready", self._ready_status),
            ("Servos Moving", self._moving_status),
            ("Plate On Position", self._plate_status),
            ("Health", self._health_status),
        ]
        for row, (label, value_widget) in enumerate(rows):
            name = QLabel(label)
            name.setStyleSheet(LABEL_STYLE)
            layout.addWidget(name, row, 0)
            layout.addWidget(value_widget, row, 1)
        return panel

    def _build_command_panel(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._refresh_btn = QPushButton("Refresh Status")
        self._move_btn = QPushButton("Move Servos")
        self._open_btn = QPushButton("Open Plate")
        self._close_btn = QPushButton("Close Plate")
        self._next_btn = QPushButton("Next Position")

        self._refresh_btn.setStyleSheet(GHOST_BTN_STYLE)
        for button in (self._move_btn, self._open_btn, self._close_btn, self._next_btn):
            button.setStyleSheet(ACTION_BTN_STYLE)
        for button in (self._refresh_btn, self._move_btn, self._open_btn, self._close_btn, self._next_btn):
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        self._refresh_btn.clicked.connect(self._on_refresh_status)
        self._move_btn.clicked.connect(self._on_move_servos)
        self._open_btn.clicked.connect(self._on_open_plate)
        self._close_btn.clicked.connect(self._on_close_plate)
        self._next_btn.clicked.connect(self._on_next_position)

        layout.addWidget(self._refresh_btn)
        layout.addWidget(self._move_btn)
        layout.addWidget(self._open_btn)
        layout.addWidget(self._close_btn)
        layout.addWidget(self._next_btn)
        layout.addStretch()
        return panel

    def _build_status_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(f"background: {BG_COLOR}; border-top: 1px solid {BORDER};")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet(_STATUS_MUTED)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()
        layout.addWidget(self._status_label)
        return bar

    def _make_value_label(self) -> QLabel:
        label = QLabel("-")
        label.setStyleSheet(_STATUS_STYLE)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _on_save(self) -> None:
        self.save_requested.emit(self.get_values())

    def _on_refresh_status(self) -> None:
        self.refresh_status_requested.emit()

    def _on_move_servos(self) -> None:
        self.move_servos_requested.emit()

    def _on_open_plate(self) -> None:
        self.open_plate_requested.emit()

    def _on_close_plate(self) -> None:
        self.close_plate_requested.emit()

    def _on_next_position(self) -> None:
        self.next_position_requested.emit()

    def load_config(self, config) -> None:
        flat = DryerConfigMapper.to_flat_dict(config)
        for key, editor in self._setting_inputs.items():
            if key in flat:
                editor.setValue(flat[key])

    def get_values(self) -> dict:
        return {key: editor.value() for key, editor in self._setting_inputs.items()}

    def set_state(self, state: DryerState) -> None:
        self._raw_status.setText(str(state.raw_status))
        self._set_bool(self._ready_status, state.is_ready)
        self._set_bool(self._moving_status, state.servos_moving)
        self._set_bool(self._plate_status, state.plate_on_position)
        self._health_status.setText("OK" if state.is_healthy else "FAILED")
        self._health_status.setStyleSheet(_STATUS_ACTIVE if state.is_healthy else _STATUS_MUTED)
        if state.communication_errors:
            self.set_status(state.communication_errors[0])
        else:
            self.set_status("Status refreshed")

    def set_action_result(self, action: str, success: bool) -> None:
        self.set_status(f"{action}: {'OK' if success else 'FAILED'}")

    def set_busy(self, busy: bool) -> None:
        for button in (
            self._save_btn,
            self._refresh_btn,
            self._move_btn,
            self._open_btn,
            self._close_btn,
            self._next_btn,
        ):
            button.setEnabled(not busy)
        if busy:
            self.set_status("Working")

    def set_status(self, message: str) -> None:
        self._status_label.setText(message)
        self._status_label.setStyleSheet(_STATUS_MUTED)

    def set_error(self, message: str) -> None:
        self._status_label.setText(message)
        self._status_label.setStyleSheet(_STATUS_ERROR)

    def _set_bool(self, label: QLabel, value: bool) -> None:
        label.setText("YES" if value else "NO")
        label.setStyleSheet(_STATUS_ACTIVE if value else _STATUS_MUTED)

    def clean_up(self) -> None:
        pass
