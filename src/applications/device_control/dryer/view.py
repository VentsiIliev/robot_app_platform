from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pl_gui.settings.settings_view.styles import (
    BG_COLOR,
    BORDER,
    LABEL_STYLE,
    SAVE_BUTTON_STYLE,
    TERTIARY_TEXT,
    TEXT_COLOR,
)
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.keyboard_settings_view import build_with_keyboard_setting_handlers
from src.applications.base.widgets.custom_virtual_keyboard import (
    KeyboardDoubleSpinBox,
    KeyboardSpinBox,
)
from src.applications.device_control.dryer.mapper import DryerConfigMapper
from src.applications.device_control.dryer.schema import REGISTER_GROUP, TIMING_GROUP

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

class DryerControlPanel(IApplicationView):
    save_requested = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__("DryerControlPanel", parent)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._setting_inputs: dict[str, KeyboardSpinBox | KeyboardDoubleSpinBox] = {}
        build_with_keyboard_setting_handlers(self._build_setting_tables)

        self._save_btn = QPushButton("Save")
        self._save_btn.setStyleSheet(SAVE_BUTTON_STYLE)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._on_save)

        content = QWidget()
        content.setStyleSheet(f"background: {BG_COLOR};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)
        content_layout.addWidget(self._build_settings_tab())
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

    def _on_save(self) -> None:
        self.save_requested.emit(self.get_values())

    def load_config(self, config) -> None:
        flat = DryerConfigMapper.to_flat_dict(config)
        for key, editor in self._setting_inputs.items():
            if key in flat:
                editor.setValue(flat[key])

    def get_values(self) -> dict:
        return {key: editor.value() for key, editor in self._setting_inputs.items()}

    def set_status(self, message: str) -> None:
        self._status_label.setText(message)
        self._status_label.setStyleSheet(_STATUS_MUTED)

    def clean_up(self) -> None:
        pass
