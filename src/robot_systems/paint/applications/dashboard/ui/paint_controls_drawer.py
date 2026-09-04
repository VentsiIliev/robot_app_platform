from __future__ import annotations

from PyQt6.QtCore import QCoreApplication, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pl_gui.shell.ui.icon_loader import load_icon
from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    BG_COLOR,
    BORDER,
    GHOST_BTN_STYLE,
    GROUP_STYLE,
    LABEL_STYLE,
    PRIMARY,
    PRIMARY_DARK,
)
from src.applications.base.widgets.custom_virtual_keyboard import KeyboardDoubleSpinBox, KeyboardSpinBox

class PaintControlsDrawer(QWidget):
    """Data-driven manual controls hosted by the dashboard drawer."""

    cable_relief_requested = pyqtSignal()
    device_toggle_requested = pyqtSignal(str, bool)
    application_shortcut_requested = pyqtSignal(str)
    unmatched_paint_settings_requested = pyqtSignal(object)
    acceleration_scale_requested = pyqtSignal(float)
    drying_mode_requested = pyqtSignal(str)

    def __init__(
        self,
        toggle_configs: list,
        *,
        show_manual_controls: bool = True,
        show_unmatched_paint_controls: bool = True,
        show_acceleration_scale_control: bool = True,
        show_shortcuts: bool = True,
        compact_layout: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._configs = list(toggle_configs)
        self._states = {item.device_id: False for item in self._configs}
        self._buttons: dict[str, QPushButton] = {}
        self._drying_mode = "auto"
        self._shortcuts = []
        self._compact_layout = bool(compact_layout)
        self._shortcut_buttons: dict[str, QPushButton] = {}
        self._title = QLabel()
        self._title.setStyleSheet(LABEL_STYLE)
        self._title.setVisible(show_manual_controls)

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(8)
        root.addWidget(self._title)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content_widget)
        self._content_layout = layout
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._unmatched_box = QGroupBox()
        self._unmatched_box.setStyleSheet(GROUP_STYLE)
        self._unmatched_box.setVisible(show_unmatched_paint_controls)
        self._unmatched_box.setMinimumHeight(430)
        unmatched_layout = QVBoxLayout(self._unmatched_box)
        self._unmatched_layout = unmatched_layout
        unmatched_layout.setContentsMargins(14, 20, 14, 14)
        unmatched_layout.setSpacing(10)
        self._unmatched_step_buttons: list[QPushButton] = []
        self._acceleration_scale_step_buttons: list[QPushButton] = []
        self._unmatched_pass_count = KeyboardSpinBox()
        self._unmatched_pass_count.setRange(1, 2)
        self._unmatched_pass_count.setSingleStep(1)
        self._unmatched_pass_count.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._unmatched_pass_count.valueChanged.connect(self._on_pass_count_changed)
        self._unmatched_pass_count_label = QLabel()
        unmatched_layout.addWidget(self._unmatched_pass_count_label)
        self._pass_count_row = self._build_touch_spin_row(
            "pass_count", self._unmatched_pass_count
        )
        unmatched_layout.addWidget(self._pass_count_row)
        self._unmatched_tabs = QTabWidget()
        self._unmatched_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                background-color: {BG_COLOR};
                border: 1px solid {BORDER};
                border-radius: 8px;
                top: -1px;
            }}
            QTabBar::tab {{
                color: {PRIMARY};
                background-color: {BG_COLOR};
                border: 1px solid {BORDER};
                border-bottom: none;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                min-width: 90px;
                min-height: 36px;
                padding: 0 14px;
                font-size: 11pt;
                font-weight: bold;
                margin-right: 4px;
            }}
            QTabBar::tab:selected {{
                color: white;
                background-color: {PRIMARY};
                border-color: {PRIMARY};
            }}
            QTabBar::tab:hover:!selected {{
                color: white;
                background-color: {PRIMARY_DARK};
                border-color: {PRIMARY_DARK};
            }}
        """)
        pass_1_widget = QWidget()
        pass_1_layout = QVBoxLayout(pass_1_widget)
        self._pass_1_layout = pass_1_layout
        self._unmatched_velocity = self._make_spin_box(0.1, 100.0, 1.0, "%")
        self._unmatched_acceleration = self._make_spin_box(0.1, 100.0, 1.0, "%")
        self._unmatched_offset = self._make_spin_box(-100.0, 100.0, 0.0, " mm")
        self._unmatched_offset.setSingleStep(0.1)
        self._unmatched_velocity_label = QLabel()
        self._unmatched_acceleration_label = QLabel()
        self._unmatched_offset_label = QLabel()
        for label in (
            self._unmatched_velocity_label,
            self._unmatched_acceleration_label,
            self._unmatched_offset_label,
        ):
            label.setMinimumHeight(24)
        pass_1_layout.addWidget(self._unmatched_velocity_label)
        self._velocity_row = self._build_touch_spin_row("velocity", self._unmatched_velocity)
        pass_1_layout.addWidget(self._velocity_row)
        pass_1_layout.addWidget(self._unmatched_acceleration_label)
        self._acceleration_row = self._build_touch_spin_row("acceleration", self._unmatched_acceleration)
        pass_1_layout.addWidget(self._acceleration_row)
        pass_1_layout.addWidget(self._unmatched_offset_label)
        self._offset_row = self._build_touch_spin_row("offset", self._unmatched_offset)
        pass_1_layout.addWidget(self._offset_row)
        self._unmatched_tabs.addTab(pass_1_widget, "")
        pass_2_widget = QWidget()
        pass_2_layout = QVBoxLayout(pass_2_widget)
        self._pass_2_layout = pass_2_layout
        self._pass_2_use_first = QCheckBox()
        self._pass_2_use_first.stateChanged.connect(self._sync_pass_2_enabled)
        pass_2_layout.addWidget(self._pass_2_use_first)
        self._pass_2_velocity = self._make_spin_box(0.1, 100.0, 1.0, "%")
        self._pass_2_acceleration = self._make_spin_box(0.1, 100.0, 1.0, "%")
        self._pass_2_offset = self._make_spin_box(-100.0, 100.0, 0.0, " mm")
        self._pass_2_offset.setSingleStep(0.1)
        self._pass_2_labels = [QLabel(), QLabel(), QLabel()]
        self._pass_2_rows = [
            self._build_touch_spin_row("pass_2_velocity", self._pass_2_velocity),
            self._build_touch_spin_row("pass_2_acceleration", self._pass_2_acceleration),
            self._build_touch_spin_row("pass_2_offset", self._pass_2_offset),
        ]
        for label, row in zip(self._pass_2_labels, self._pass_2_rows):
            pass_2_layout.addWidget(label)
            pass_2_layout.addWidget(row)
        self._unmatched_tabs.addTab(pass_2_widget, "")
        unmatched_layout.addWidget(self._unmatched_tabs)
        self._unmatched_note = QLabel()
        self._unmatched_note.setWordWrap(True)
        unmatched_layout.addWidget(self._unmatched_note)
        self._unmatched_apply = QPushButton()
        self._unmatched_apply.setStyleSheet(ACTION_BTN_STYLE)
        self._unmatched_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self._unmatched_apply.clicked.connect(self._on_unmatched_paint_settings)
        unmatched_layout.addWidget(self._unmatched_apply)
        layout.addWidget(self._unmatched_box)

        self._acceleration_scale_box = QGroupBox()
        self._acceleration_scale_box.setStyleSheet(GROUP_STYLE)
        self._acceleration_scale_box.setVisible(show_acceleration_scale_control)
        acceleration_scale_layout = QVBoxLayout(self._acceleration_scale_box)
        acceleration_scale_header = QHBoxLayout()
        self._acceleration_scale_label = QLabel()
        acceleration_scale_header.addWidget(self._acceleration_scale_label)
        acceleration_scale_header.addStretch(1)
        acceleration_scale_layout.addLayout(acceleration_scale_header)
        self._acceleration_scale = KeyboardSpinBox()
        self._acceleration_scale.setRange(0, 100)
        self._acceleration_scale.setSingleStep(1)
        self._acceleration_scale.setValue(100)
        self._acceleration_scale.setSuffix("%")
        self._acceleration_scale.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._acceleration_scale.setMinimumHeight(48)
        acceleration_scale_layout.addWidget(
            self._build_touch_spin_row("acceleration_scale", self._acceleration_scale)
        )
        self._acceleration_scale_apply = QPushButton()
        self._acceleration_scale_apply.setStyleSheet(ACTION_BTN_STYLE)
        self._acceleration_scale_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self._acceleration_scale_apply.clicked.connect(self._on_acceleration_scale_apply)
        acceleration_scale_layout.addWidget(self._acceleration_scale_apply)
        layout.addWidget(self._acceleration_scale_box)

        self._relief_box = QGroupBox()
        self._relief_box.setStyleSheet(GROUP_STYLE)
        relief_layout = QVBoxLayout(self._relief_box)
        self._relief_button = QPushButton()
        self._relief_button.setStyleSheet(ACTION_BTN_STYLE)
        self._relief_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._relief_button.clicked.connect(self._on_cable_relief)
        relief_layout.addWidget(self._relief_button)
        self._relief_box.setVisible(show_manual_controls)
        layout.addWidget(self._relief_box)

        self._devices_box = QGroupBox()
        self._devices_box.setStyleSheet(GROUP_STYLE)
        devices_layout = QVBoxLayout(self._devices_box)
        for item in self._configs:
            button = QPushButton()
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setProperty("device_id", item.device_id)
            button.clicked.connect(self._on_device_toggle)
            devices_layout.addWidget(button)
            self._buttons[item.device_id] = button
        self._drying_mode_button = QPushButton()
        self._drying_mode_button.setStyleSheet(GHOST_BTN_STYLE)
        self._drying_mode_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._drying_mode_button.clicked.connect(self._on_drying_mode)
        devices_layout.addWidget(self._drying_mode_button)
        self._devices_box.setVisible(show_manual_controls)
        layout.addWidget(self._devices_box)

        self._shortcuts_box = QGroupBox()
        self._shortcuts_box.setStyleSheet(GROUP_STYLE)
        self._shortcuts_layout = QVBoxLayout(self._shortcuts_box)
        self._shortcuts_layout.setSpacing(8)
        self._shortcuts_box.setVisible(show_shortcuts)
        layout.addWidget(self._shortcuts_box)
        layout.addStretch(1)
        if self._compact_layout:
            self._apply_compact_layout()
        self._scroll.setWidget(content_widget)
        root.addWidget(self._scroll, 1)
        self.retranslateUi()

    def _apply_compact_layout(self) -> None:
        self._unmatched_box.setMinimumHeight(300)
        summary = QWidget()
        summary.setStyleSheet("background: transparent;")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(0, 0, 0, 0)
        summary_layout.setSpacing(10)

        pass_count_box = QGroupBox()
        self._pass_count_box = pass_count_box
        pass_count_box.setStyleSheet(GROUP_STYLE)
        pass_count_layout = QVBoxLayout(pass_count_box)
        pass_count_layout.setContentsMargins(12, 20, 12, 10)
        self._unmatched_layout.removeWidget(self._unmatched_pass_count_label)
        self._unmatched_layout.removeWidget(self._pass_count_row)
        self._unmatched_pass_count_label.hide()
        pass_count_layout.addWidget(self._pass_count_row)
        self._content_layout.removeWidget(self._acceleration_scale_box)
        self._acceleration_scale_label.hide()
        summary_layout.addWidget(pass_count_box, 1)
        summary_layout.addWidget(self._acceleration_scale_box, 1)
        self._content_layout.insertWidget(0, summary)

        self._compact_pass_one_fields()
        self._compact_pass_two_fields()

    def _compact_pass_one_fields(self) -> None:
        for widget in (
            self._unmatched_velocity_label, self._velocity_row,
            self._unmatched_acceleration_label, self._acceleration_row,
            self._unmatched_offset_label, self._offset_row,
        ):
            self._pass_1_layout.removeWidget(widget)
        pair = QHBoxLayout()
        pair.addWidget(self._field_column(self._unmatched_velocity_label, self._velocity_row), 1)
        pair.addWidget(self._field_column(self._unmatched_acceleration_label, self._acceleration_row), 1)
        pair.addWidget(self._field_column(self._unmatched_offset_label, self._offset_row), 1)
        self._pass_1_layout.addLayout(pair)

    def _compact_pass_two_fields(self) -> None:
        for label, row in zip(self._pass_2_labels, self._pass_2_rows):
            self._pass_2_layout.removeWidget(label)
            self._pass_2_layout.removeWidget(row)
        pair = QHBoxLayout()
        pair.addWidget(self._field_column(self._pass_2_labels[0], self._pass_2_rows[0]), 1)
        pair.addWidget(self._field_column(self._pass_2_labels[1], self._pass_2_rows[1]), 1)
        pair.addWidget(self._field_column(self._pass_2_labels[2], self._pass_2_rows[2]), 1)
        self._pass_2_layout.addLayout(pair)

    @staticmethod
    def _field_column(label: QLabel, field: QWidget) -> QWidget:
        column = QWidget()
        column.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(label)
        layout.addWidget(field)
        return column

    @staticmethod
    def _make_spin_box(minimum: float, maximum: float, value: float, suffix: str) -> KeyboardDoubleSpinBox:
        field = KeyboardDoubleSpinBox()
        field.setRange(minimum, maximum)
        field.setDecimals(1)
        field.setSingleStep(1.0)
        field.setValue(value)
        field.setSuffix(suffix)
        field.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        field.setMinimumHeight(48)
        return field

    def _build_touch_spin_row(
        self,
        field_id: str,
        field: KeyboardDoubleSpinBox | KeyboardSpinBox,
    ) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row.setFixedHeight(52)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self._make_step_button(field_id, -1.0, "−"))
        layout.addWidget(field, 1)
        layout.addWidget(self._make_step_button(field_id, 1.0, "+"))
        return row

    def _make_step_button(self, field_id: str, direction: float, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("field_id", field_id)
        button.setProperty("step_direction", direction)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedSize(48, 48)
        button.setStyleSheet(GHOST_BTN_STYLE)
        button.setAutoRepeat(True)
        button.setAutoRepeatDelay(400)
        button.setAutoRepeatInterval(50)
        button.clicked.connect(self._on_touch_step)
        if field_id == "acceleration_scale":
            self._acceleration_scale_step_buttons.append(button)
        else:
            self._unmatched_step_buttons.append(button)
        return button

    def _on_touch_step(self) -> None:
        button = self.sender()
        fields = {
            "pass_count": self._unmatched_pass_count,
            "velocity": self._unmatched_velocity,
            "acceleration": self._unmatched_acceleration,
            "acceleration_scale": self._acceleration_scale,
            "offset": self._unmatched_offset,
            "pass_2_velocity": self._pass_2_velocity,
            "pass_2_acceleration": self._pass_2_acceleration,
            "pass_2_offset": self._pass_2_offset,
        }
        field = fields.get(str(button.property("field_id")))
        if field is None:
            return
        direction = float(button.property("step_direction") or 0.0)
        value = field.value() + direction * field.singleStep()
        field.setValue(int(value) if isinstance(field, KeyboardSpinBox) else value)

    def _on_unmatched_paint_settings(self) -> None:
        self.unmatched_paint_settings_requested.emit(
            self._settings_payload()
        )

    def _settings_payload(self) -> dict:
        return {
            "pass_count": self._unmatched_pass_count.value(),
            "pass_1": {"velocity_percent": self._unmatched_velocity.value(), "acceleration_percent": self._unmatched_acceleration.value(), "offset_mm": self._unmatched_offset.value()},
            "pass_2": {"use_pass_1_settings": self._pass_2_use_first.isChecked(), "velocity_percent": self._pass_2_velocity.value(), "acceleration_percent": self._pass_2_acceleration.value(), "offset_mm": self._pass_2_offset.value()},
        }

    def _on_pass_count_changed(self, count: int) -> None:
        self._unmatched_tabs.setTabVisible(1, int(count) == 2)

    def _on_acceleration_scale_apply(self) -> None:
        self.acceleration_scale_requested.emit(float(self._acceleration_scale.value()))

    def _sync_pass_2_enabled(self) -> None:
        enabled = not self._pass_2_use_first.isChecked()
        for field in (self._pass_2_velocity, self._pass_2_acceleration, self._pass_2_offset):
            field.setEnabled(enabled)
        for button in self._unmatched_step_buttons:
            if str(button.property("field_id")).startswith("pass_2_"):
                button.setEnabled(enabled)

    def set_unmatched_paint_settings(self, settings: dict) -> None:
        if not settings:
            self._unmatched_box.setEnabled(False)
            return
        self._unmatched_velocity.setValue(float(settings.get("velocity_percent", 10.0)))
        self._unmatched_acceleration.setValue(float(settings.get("acceleration_percent", 10.0)))
        self._unmatched_offset.setValue(float(settings.get("offset_mm", 0.0)))
        self._unmatched_pass_count.setValue(int(settings.get("pass_count", 1)))
        pass_2 = dict(settings.get("pass_2") or {})
        self._pass_2_use_first.setChecked(bool(pass_2.get("use_pass_1_settings", True)))
        self._pass_2_velocity.setValue(float(pass_2.get("velocity_percent", settings.get("velocity_percent", 10.0))))
        self._pass_2_acceleration.setValue(float(pass_2.get("acceleration_percent", settings.get("acceleration_percent", 10.0))))
        self._pass_2_offset.setValue(float(pass_2.get("offset_mm", settings.get("offset_mm", 0.0))))
        self._on_pass_count_changed(self._unmatched_pass_count.value())
        self._sync_pass_2_enabled()
        self._unmatched_box.setEnabled(True)

    def set_unmatched_paint_settings_editable(self, editable: bool) -> None:
        self._unmatched_velocity.setEnabled(editable)
        self._unmatched_acceleration.setEnabled(editable)
        self._unmatched_offset.setEnabled(editable)
        self._unmatched_apply.setEnabled(editable)
        self._unmatched_pass_count.setEnabled(editable)
        self._pass_2_use_first.setEnabled(editable)
        if not editable:
            for field in (self._pass_2_velocity, self._pass_2_acceleration, self._pass_2_offset):
                field.setEnabled(False)
        for button in self._unmatched_step_buttons:
            button.setEnabled(editable)
        if editable:
            self._sync_pass_2_enabled()

    def _on_device_toggle(self, checked: bool) -> None:
        button = self.sender()
        device_id = str(button.property("device_id"))
        self.device_toggle_requested.emit(device_id, checked)

    def _on_cable_relief(self) -> None:
        self.cable_relief_requested.emit()

    def _on_drying_mode(self) -> None:
        next_mode = {"auto": "manual", "manual": "demo", "demo": "auto"}
        self.drying_mode_requested.emit(next_mode[self._drying_mode])

    def set_drying_mode(self, mode: str) -> None:
        normalized = str(mode).lower()
        self._drying_mode = normalized if normalized in {"auto", "manual", "demo"} else "auto"
        self._render_drying_mode()

    def set_drying_mode_busy(self, busy: bool) -> None:
        self._drying_mode_button.setEnabled(not busy)

    def set_device_state(self, device_id: str, enabled: bool) -> None:
        button = self._buttons.get(device_id)
        if button is None:
            return
        self._states[device_id] = bool(enabled)
        button.blockSignals(True)
        button.setChecked(bool(enabled))
        button.blockSignals(False)
        self._render_device_button(device_id)

    def set_device_busy(self, device_id: str, busy: bool) -> None:
        button = self._buttons.get(device_id)
        if button is not None:
            button.setEnabled(not busy)

    def set_cable_relief_busy(self, busy: bool) -> None:
        self._relief_button.setEnabled(not busy)

    def set_application_shortcuts(self, shortcuts: list) -> None:
        self._shortcuts = list(shortcuts)
        while self._shortcuts_layout.count():
            item = self._shortcuts_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._shortcut_buttons.clear()

        grouped: dict[tuple[int, str, str], list] = {}
        for shortcut in self._shortcuts:
            key = (
                int(getattr(shortcut, "folder_id", 0)),
                str(getattr(shortcut, "folder_name", "") or self.tr("Other")),
                str(getattr(shortcut, "folder_translation_key", "")),
            )
            grouped.setdefault(key, []).append(shortcut)

        self._folder_boxes = []
        for (_folder_id, folder_name, translation_key), shortcuts in grouped.items():
            folder_box = QGroupBox()
            folder_box.setProperty("folder_name", folder_name)
            folder_box.setProperty("translation_key", translation_key)
            folder_box.setStyleSheet(GROUP_STYLE)
            folder_grid = QGridLayout(folder_box)
            folder_grid.setSpacing(8)
            for index, shortcut in enumerate(shortcuts):
                button = QPushButton()
                button.setProperty("app_name", shortcut.app_name)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.setMinimumHeight(56)
                button.setSizePolicy(
                    QSizePolicy.Policy.Ignored,
                    QSizePolicy.Policy.Fixed,
                )
                button.setIcon(load_icon(shortcut.icon))
                button.setIconSize(QSize(28, 28))
                button.setStyleSheet(GHOST_BTN_STYLE)
                button.clicked.connect(self._on_application_shortcut)
                folder_grid.addWidget(button, index, 0)
                self._shortcut_buttons[shortcut.app_name] = button
            folder_grid.setColumnStretch(0, 1)
            self._shortcuts_layout.addWidget(folder_box)
            self._folder_boxes.append(folder_box)
        self._render_shortcuts()

    def _on_application_shortcut(self) -> None:
        button = self.sender()
        self.application_shortcut_requested.emit(str(button.property("app_name")))

    def retranslateUi(self) -> None:
        self._title.setText(self.tr("Manual Controls"))
        self._unmatched_box.setTitle(self.tr("Painting"))
        self._unmatched_pass_count_label.setText(self.tr("Number of Passes"))
        if hasattr(self, "_pass_count_box"):
            self._pass_count_box.setTitle(self.tr("Number of Passes"))
        self._acceleration_scale_label.setText(self.tr("Process Acceleration Scale"))
        self._acceleration_scale_box.setTitle(self.tr("Process Scaling"))
        self._acceleration_scale_apply.setText(self.tr("Apply"))
        self._unmatched_tabs.setTabText(0, self.tr("Pass 1"))
        self._unmatched_tabs.setTabText(1, self.tr("Pass 2"))
        self._pass_2_use_first.setText(self.tr("Use Pass 1 settings"))
        self._unmatched_velocity_label.setText(self.tr("Velocity"))
        self._unmatched_acceleration_label.setText(self.tr("Acceleration"))
        self._unmatched_offset_label.setText(self.tr("Press Offset"))
        for label, text in zip(self._pass_2_labels, ("Velocity", "Acceleration", "Press Offset")):
            label.setText(self.tr(text))
        self._unmatched_note.setText(self.tr("Used only when workpiece matching is off."))
        self._unmatched_apply.setText(self.tr("Apply"))
        self._relief_button.setText(self.tr("Relieve Cable (Unwind J6)"))
        self._shortcuts_box.setTitle(self.tr("Application Shortcuts"))
        for item in self._configs:
            self._render_device_button(item.device_id)
        self._render_drying_mode()
        self._render_shortcuts()

    def _render_drying_mode(self) -> None:
        text = {
            "auto": self.tr("Auto Dry"),
            "manual": self.tr("Tray Dry"),
            "demo": self.tr("Demo Alternate"),
        }[self._drying_mode]
        self._drying_mode_button.setText(text)

    def set_acceleration_scale(self, value: float) -> None:
        self._acceleration_scale.setValue(max(0, min(100, int(round(value)))))

    def set_acceleration_scale_editable(self, editable: bool) -> None:
        self._acceleration_scale.setEnabled(editable)
        self._acceleration_scale_apply.setEnabled(editable)
        for button in self._acceleration_scale_step_buttons:
            button.setEnabled(editable)

    def _render_shortcuts(self) -> None:
        for folder_box in getattr(self, "_folder_boxes", []):
            translation_key = str(folder_box.property("translation_key") or "")
            folder_name = str(folder_box.property("folder_name") or "")
            translated = (
                QCoreApplication.translate("Shell", translation_key)
                if translation_key
                else ""
            )
            folder_box.setTitle(
                translated if translated and translated != translation_key else folder_name
            )
        for shortcut in self._shortcuts:
            button = self._shortcut_buttons.get(shortcut.app_name)
            if button is not None:
                translated = QCoreApplication.translate("Applications", shortcut.label)
                button.setText(translated or shortcut.label)

    def _render_device_button(self, device_id: str) -> None:
        button = self._buttons.get(device_id)
        config = next((item for item in self._configs if item.device_id == device_id), None)
        if button is None or config is None:
            return
        enabled = self._states[device_id]
        state_text = self.tr("ON") if enabled else self.tr("OFF")
        button.setText(f"{self.tr(config.label)}: {state_text}")
        button.setStyleSheet(ACTION_BTN_STYLE if enabled else GHOST_BTN_STYLE)
