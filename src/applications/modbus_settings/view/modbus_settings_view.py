from copy import deepcopy

from PyQt6.QtCore import QEvent, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel, QFrame,
    QComboBox, QScrollArea, QStackedWidget, QTabBar, QSizePolicy, QDialog,
    QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
)


from pl_gui.settings.settings_view.group_widget import GenericSettingGroup
from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE, GHOST_BTN_STYLE, BG_COLOR, BORDER,
    PRIMARY, PRIMARY_DARK, PRIMARY_LIGHT, SECONDARY_BG, TEXT_COLOR,
    STATUS_OK, ERROR_COLOR, APP_PHASE_TAB_STYLE,
    SETTINGS_CARD_FRAME_STYLE, SETTINGS_FIELD_LABEL_STYLE,
    SETTINGS_FOOTER_STYLE, SETTINGS_HEADER_STYLE, SAVE_BUTTON_STYLE,
)
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.app_dialog import AppDialog, DIALOG_COMBO_STYLE, DIALOG_INPUT_STYLE
from src.applications.base.widgets.custom_virtual_keyboard import KeyboardLineEdit
from src.applications.base.widgets.keyboard_number_field import KeyboardNumberField
from src.applications.base.keyboard_settings_view import build_with_keyboard_setting_handlers
from src.applications.base.styled_message_box import ask_yes_no, show_warning
from src.applications.modbus_settings.model.mapper import ModbusSettingsMapper
from src.applications.modbus_settings.view.modbus_settings_schema import CONNECTION_GROUP, DEVICE_GROUP
from src.engine.hardware.communication.transport_registry import DEFAULT_TRANSPORT_REGISTRY

_TABLE_STYLE = f"""
QTableWidget {{
    background-color: white;
    color: {TEXT_COLOR};
    border: 1px solid {BORDER};
    gridline-color: {BORDER};
    selection-background-color: {SECONDARY_BG};
    selection-color: {TEXT_COLOR};
    alternate-background-color: {BG_COLOR};
}}
QHeaderView::section {{
    background-color: {PRIMARY};
    color: white;
    border: none;
    padding: 10px;
    font-weight: bold;
}}
"""

_CARD_HINT_STYLE = SETTINGS_FIELD_LABEL_STYLE
_TOOL_LABEL_STYLE = f"color: {TEXT_COLOR}; font-size: 10pt; font-weight: bold; background: transparent;"

_COMBO_STYLE = f"""
QComboBox {{
    background: white;
    color: {TEXT_COLOR};
    border: 2px solid {BORDER};
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 12pt;
    min-height: 56px;
}}
QComboBox:hover {{ border-color: {PRIMARY}; }}
QComboBox::drop-down {{ border: none; width: 40px; }}
QComboBox QAbstractItemView {{
    background: white;
    color: {TEXT_COLOR};
    selection-background-color: {PRIMARY_LIGHT};
    selection-color: {PRIMARY_DARK};
    font-size: 11pt;
    padding: 8px;
}}
"""

_STATUS_IDLE = _CARD_HINT_STYLE
_STATUS_OK = f"color: {STATUS_OK}; font-size: 9pt; background: transparent;"
_STATUS_FAIL = f"color: {ERROR_COLOR}; font-size: 9pt; background: transparent;"


def _make_scroll(widget: QWidget) -> QScrollArea:
    """Vertical scroll only — horizontal never overflows."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
    scroll.setWidget(widget)
    return scroll





class ModbusSettingsView(IApplicationView):
    """View — pure Qt widget. No services, no model, no business logic."""

    save_requested            = pyqtSignal(dict)
    detect_ports_requested    = pyqtSignal()
    grant_permission_requested = pyqtSignal()
    set_low_latency_requested  = pyqtSignal()
    test_connection_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("ModbusSettings", parent)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setStyleSheet(f"background: {BG_COLOR};")

        # Groups — owned here, not by SettingsView
        build_with_keyboard_setting_handlers(self._build_setting_groups)
        self._translated_labels: list[tuple[QLabel, str]] = []

        self._phase_bar = QTabBar()
        self._phase_bar.setExpanding(False)
        self._phase_bar.setDrawBase(False)
        self._phase_bar.setStyleSheet(APP_PHASE_TAB_STYLE)
        self._tabs = QStackedWidget()
        self._tabs.addWidget(_make_scroll(self._build_connection_tab()))
        self._phase_bar.addTab("Connection")
        self._tabs.addWidget(_make_scroll(self._build_device_tab()))
        self._phase_bar.addTab("Slaves")
        self._phase_bar.currentChanged.connect(self._tabs.setCurrentIndex)

        self._title_label = QLabel()
        self._title_label.setStyleSheet(SETTINGS_HEADER_STYLE)

        content = QWidget()
        content.setStyleSheet(f"background: {BG_COLOR};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 16, 10, 0)
        content_layout.setSpacing(12)
        content_layout.addWidget(self._title_label)
        content_layout.addWidget(self._phase_bar, alignment=Qt.AlignmentFlag.AlignLeft)
        content_layout.addWidget(self._tabs, stretch=1)

        layout.addWidget(content, stretch=1)
        layout.addWidget(self._build_save_bar())
        self.retranslateUi()

    def _build_card(self, title: str) -> tuple[QFrame, QVBoxLayout, QHBoxLayout]:
        card = QFrame()
        card.setObjectName("settingsCard")
        card.setStyleSheet(SETTINGS_CARD_FRAME_STYLE)
        outer = QVBoxLayout(card)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QWidget()
        header.setObjectName("settingsCardHeader")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(16, 10, 16, 10)
        label = QLabel(title)
        label.setObjectName("settingsCardTitle")
        self._translated_labels.append((label, title))
        header_row.addWidget(label)
        outer.addWidget(header)
        body = QWidget()
        body.setObjectName("settingsCardContent")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(16, 14, 16, 16)
        body_layout.setSpacing(14)
        outer.addWidget(body)
        return card, body_layout, header_row

    @staticmethod
    def _size_table(table: QTableWidget) -> None:
        header_height = table.horizontalHeader().height() or 40
        rows_height = sum(table.rowHeight(row) for row in range(table.rowCount()))
        table.setFixedHeight(min(280, max(88, header_height + rows_height + 4)))

    def _build_setting_groups(self) -> None:
        self._connection_group = GenericSettingGroup(CONNECTION_GROUP)
        self._device_group     = GenericSettingGroup(DEVICE_GROUP)

    # ── Tab content builders ──────────────────────────────────────────────

    def _build_connection_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {BG_COLOR};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        lay.addWidget(self._build_port_row())
        lay.addWidget(self._build_profile_row())
        lay.addWidget(self._build_action_bar())
        lay.addStretch()
        return w

    def _build_device_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {BG_COLOR};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)
        lay.addWidget(self._build_slave_row())
        lay.addStretch()
        return w

    def _build_slave_row(self) -> QWidget:
        row_widget, row, _header = self._build_card("MODBUS SLAVES")

        self._slave_table = QTableWidget(0, 5)
        self._slave_table.setHorizontalHeaderLabels(["Name", "Slave ID", "Profile", "Transport", "Retries"])
        self._slave_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._slave_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._slave_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._slave_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._slave_table.setStyleSheet(_TABLE_STYLE)
        self._slave_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._slave_table.itemSelectionChanged.connect(self._on_slave_table_selection)

        self._slave_combo = QComboBox()
        self._slave_combo.currentTextChanged.connect(self._on_slave_changed)
        self._slave_profile_combo = QComboBox()
        self._slave_transport_combo = QComboBox()
        self._slave_combo.setVisible(False)
        self._slave_profile_combo.setVisible(False)
        self._slave_transport_combo.setVisible(False)
        self._add_slave_btn = QPushButton("Add Slave")
        self._add_slave_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._add_slave_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_slave_btn.clicked.connect(self._on_add_slave)

        self._remove_slave_btn = QPushButton("Remove Slave")
        self._remove_slave_btn.setStyleSheet(GHOST_BTN_STYLE)
        self._remove_slave_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_slave_btn.clicked.connect(self._on_remove_slave)

        self._edit_slave_btn = QPushButton("Edit Slave")
        self._edit_slave_btn.setStyleSheet(GHOST_BTN_STYLE)
        self._edit_slave_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._edit_slave_btn.clicked.connect(self._on_edit_slave)
        self._slave_actions = QHBoxLayout()
        self._slave_actions.addWidget(self._add_slave_btn)
        self._slave_actions.addWidget(self._edit_slave_btn)
        self._slave_actions.addWidget(self._remove_slave_btn)
        self._slave_actions.addStretch()

        row.addWidget(self._slave_table)
        row.addLayout(self._slave_actions)
        return row_widget

    def _build_profile_row(self) -> QWidget:
        row_widget, row, _header = self._build_card("CONNECTION PROFILES")

        self._profile_table = QTableWidget(0, 4)
        self._profile_table.setHorizontalHeaderLabels(["Name", "Port", "Baudrate", "Format"])
        self._profile_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._profile_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._profile_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._profile_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._profile_table.setStyleSheet(_TABLE_STYLE)
        self._profile_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._profile_table.itemSelectionChanged.connect(self._on_profile_table_selection)

        self._profile_combo = QComboBox()
        self._profile_combo.setVisible(False)
        self._profile_combo.currentTextChanged.connect(self._on_profile_changed)

        self._add_profile_btn = QPushButton("Add Profile")
        self._add_profile_btn.setStyleSheet(ACTION_BTN_STYLE)
        self._add_profile_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_profile_btn.clicked.connect(self._on_add_profile)

        self._remove_profile_btn = QPushButton("Remove Profile")
        self._remove_profile_btn.setStyleSheet(GHOST_BTN_STYLE)
        self._remove_profile_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_profile_btn.clicked.connect(self._on_remove_profile)
        self._edit_profile_btn = QPushButton("Edit Profile")
        self._edit_profile_btn.setStyleSheet(GHOST_BTN_STYLE)
        self._edit_profile_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._edit_profile_btn.clicked.connect(self._on_edit_profile)

        actions = QHBoxLayout()
        actions.addWidget(self._add_profile_btn)
        actions.addWidget(self._edit_profile_btn)
        actions.addWidget(self._remove_profile_btn)
        actions.addStretch()
        row.addWidget(self._profile_table)
        row.addLayout(actions)
        return row_widget

    def _build_port_row(self) -> QWidget:
        row_widget, body, _header = self._build_card("PORT")
        lbl = QLabel("SERIAL PORT")
        lbl.setStyleSheet(_CARD_HINT_STYLE)
        self._translated_labels.append((lbl, "SERIAL PORT"))
        body.addWidget(lbl)
        row = QHBoxLayout()
        row.setSpacing(12)

        self._port_combo = QComboBox()
        self._port_combo.setStyleSheet(_COMBO_STYLE)
        self._port_combo.addItem("COM5")
        self._port_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._port_combo.currentTextChanged.connect(self._refresh_dirty)

        row.addWidget(self._port_combo, stretch=1)
        self._btn_detect = QPushButton("Detect Ports")
        self._btn_detect.setStyleSheet(GHOST_BTN_STYLE)
        self._btn_detect.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_detect.clicked.connect(self._on_inner_detect)
        row.addWidget(self._btn_detect)
        body.addLayout(row)
        return row_widget

    # ── Action bar ────────────────────────────────────────────────────────

    def _build_action_bar(self) -> QWidget:
        bar, body, header = self._build_card("CONNECTION TOOLS")
        self._status_pristine = True
        self._status_label = QLabel("Not tested")
        self._status_label.setStyleSheet(_STATUS_IDLE)
        header.addStretch()
        header.addWidget(self._status_label)

        self._btn_permission = QPushButton("Give Permission")
        self._btn_permission.setStyleSheet(GHOST_BTN_STYLE)
        self._btn_permission.setCursor(Qt.CursorShape.PointingHandCursor)

        self._btn_low_latency = QPushButton(self.tr("Set Low Latency"))
        self._btn_low_latency.setStyleSheet(GHOST_BTN_STYLE)
        self._btn_low_latency.setCursor(Qt.CursorShape.PointingHandCursor)

        self._btn_test = QPushButton("Test Connection")
        self._btn_test.setStyleSheet(ACTION_BTN_STYLE)
        self._btn_test.setCursor(Qt.CursorShape.PointingHandCursor)

        self._add_tool_row(body, "Give permission", "Allow this user to open the serial port", self._btn_permission)
        self._add_tool_row(body, "Set low latency", "Reduce USB serial adapter latency", self._btn_low_latency)
        self._add_tool_row(body, "Test connection", "Send a test request using the selected port", self._btn_test)
        self._btn_permission.clicked.connect(self._on_inner_permission)
        self._btn_low_latency.clicked.connect(self._on_inner_low_latency)
        self._btn_test.clicked.connect(self._on_inner_test)
        return bar

    def _add_tool_row(self, layout: QVBoxLayout, title: str, hint: str, button: QPushButton) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)
        labels = QVBoxLayout()
        labels.setSpacing(1)
        name = QLabel(title)
        name.setStyleSheet(_TOOL_LABEL_STYLE)
        description = QLabel(hint)
        description.setStyleSheet(_CARD_HINT_STYLE)
        self._translated_labels.extend(((name, title), (description, hint)))
        labels.addWidget(name)
        labels.addWidget(description)
        row.addLayout(labels)
        row.addStretch()
        button.setFixedWidth(200)
        row.addWidget(button)
        layout.addLayout(row)

    def _build_save_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("settingsFooter")
        bar.setStyleSheet(SETTINGS_FOOTER_STYLE)
        row = QHBoxLayout(bar)
        row.setContentsMargins(20, 10, 20, 10)
        row.setSpacing(12)
        self._status_dot = QFrame()
        self._status_dot.setFixedSize(10, 10)
        row.addWidget(self._status_dot)
        self._save_status_label = QLabel()
        row.addWidget(self._save_status_label)
        row.addStretch()
        self._discard_btn = QPushButton("Discard")
        self._discard_btn.setStyleSheet(GHOST_BTN_STYLE)
        self._discard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._discard_btn.clicked.connect(self._on_discard)
        row.addWidget(self._discard_btn)
        self._save_btn = QPushButton("Save")
        self._save_btn.setStyleSheet(SAVE_BUTTON_STYLE)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._on_inner_save_btn)
        row.addWidget(self._save_btn)
        self._set_dirty(False)
        return bar

    # ── Named forwarders ─────────────────────────────────────────────────

    def _on_inner_save_btn(self) -> None:
        self.save_requested.emit(self.get_values())

    def _on_discard(self) -> None:
        if not hasattr(self, "_saved_profiles"):
            return
        self._profiles = deepcopy(self._saved_profiles)
        self._slaves = deepcopy(self._saved_slaves)
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        self._profile_combo.addItems(list(self._profiles))
        self._profile_combo.setCurrentText("default")
        self._profile_combo.blockSignals(False)
        self._active_profile = "default"
        self._load_profile("default")
        self._reload_profile_table()
        self._slave_combo.blockSignals(True)
        self._slave_combo.clear()
        self._slave_combo.addItems(list(self._slaves))
        self._slave_combo.setCurrentText("default")
        self._slave_combo.blockSignals(False)
        self._slave_profile_combo.blockSignals(True)
        self._slave_profile_combo.clear()
        self._slave_profile_combo.addItems(list(self._profiles))
        self._slave_profile_combo.blockSignals(False)
        self._active_slave = "default"
        self._load_slave("default")
        self._reload_slave_table()
        self._set_dirty(False)

    def _set_dirty(self, dirty: bool) -> None:
        self._save_btn.setEnabled(dirty)
        self._discard_btn.setEnabled(dirty)
        color = PRIMARY if dirty else STATUS_OK
        self._save_status_label.setStyleSheet(
            f"color: {color}; background: transparent; font-size: 10pt;"
        )
        self._status_dot.setStyleSheet(f"background: {color}; border-radius: 5px;")
        self._save_status_label.setText(
            self.tr("Unsaved changes") if dirty else self.tr("All changes saved")
        )

    def _refresh_dirty(self, *_args) -> None:
        if not hasattr(self, "_saved_profiles"):
            return
        dirty = (
            self.get_profile_values() != self._saved_profiles
            or self.get_slave_values() != self._saved_slaves
        )
        self._set_dirty(dirty)

    def _on_inner_detect(self) -> None:
        self.detect_ports_requested.emit()

    def _on_inner_permission(self) -> None:
        self.grant_permission_requested.emit()

    def _on_inner_low_latency(self) -> None:
        self.set_low_latency_requested.emit()

    def _on_inner_test(self) -> None:
        self.test_connection_requested.emit()

    # ── Inbound setters ───────────────────────────────────────────────────

    def load_config(self, config) -> None:
        self._profiles = {
            name: ModbusSettingsMapper.device_to_flat_dict(config.get_profile(name))
            for name in config.profile_names()
        }
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        self._profile_combo.addItems(list(self._profiles))
        self._profile_combo.setCurrentText("default")
        self._profile_combo.blockSignals(False)
        self._active_profile = "default"
        self._load_profile("default")
        self._reload_profile_table()

        self._slaves = {
            name: {
                "slave_address": config.get_slave(name).slave_address,
                "profile_name": config.get_slave(name).profile_name,
                "transport_type": config.get_slave(name).transport_type,
                "max_retries": config.get_slave(name).max_retries,
            }
            for name in config.slave_names()
        }
        self._slave_combo.blockSignals(True)
        self._slave_combo.clear()
        self._slave_combo.addItems(list(self._slaves))
        self._slave_combo.setCurrentText("default")
        self._slave_combo.blockSignals(False)
        self._slave_profile_combo.blockSignals(True)
        self._slave_profile_combo.clear()
        self._slave_profile_combo.addItems(list(self._profiles))
        self._slave_profile_combo.blockSignals(False)
        self._slave_transport_combo.blockSignals(True)
        self._slave_transport_combo.clear()
        for descriptor in DEFAULT_TRANSPORT_REGISTRY.descriptors():
            self._slave_transport_combo.addItem(descriptor.label, descriptor.key)
        self._slave_transport_combo.blockSignals(False)
        self._active_slave = "default"
        self._load_slave("default")
        self._reload_slave_table()
        self._saved_profiles = deepcopy(self.get_profile_values())
        self._saved_slaves = deepcopy(self.get_slave_values())
        self._set_dirty(False)

    def _reload_profile_table(self) -> None:
        self._profile_table.blockSignals(True)
        self._profile_table.setRowCount(0)
        for name, values in self._profiles.items():
            row = self._profile_table.rowCount()
            self._profile_table.insertRow(row)
            self._profile_table.setItem(row, 0, QTableWidgetItem(name))
            self._profile_table.setItem(row, 1, QTableWidgetItem(str(values.get("port", ""))))
            self._profile_table.setItem(row, 2, QTableWidgetItem(str(values.get("baudrate", ""))))
            self._profile_table.setItem(
                row, 3,
                QTableWidgetItem(
                    f'{values.get("bytesize", "")}{values.get("parity", "")}{values.get("stopbits", "")}'
                ),
            )
        self._profile_table.blockSignals(False)
        self._size_table(self._profile_table)
        if self._profiles:
            self._profile_table.selectRow(max(0, list(self._profiles).index(self._profile_combo.currentText())))

    def _reload_slave_table(self) -> None:
        self._slave_table.blockSignals(True)
        self._slave_table.setRowCount(0)
        for name, values in self._slaves.items():
            row = self._slave_table.rowCount()
            self._slave_table.insertRow(row)
            self._slave_table.setItem(row, 0, QTableWidgetItem(name))
            self._slave_table.setItem(row, 1, QTableWidgetItem(str(values.get("slave_address", ""))))
            self._slave_table.setItem(row, 2, QTableWidgetItem(str(values.get("profile_name", ""))))
            self._slave_table.setItem(row, 3, QTableWidgetItem(str(values.get("transport_type", ""))))
            self._slave_table.setItem(row, 4, QTableWidgetItem(str(values.get("max_retries", ""))))
        self._slave_table.blockSignals(False)
        self._size_table(self._slave_table)
        if self._slaves:
            self._slave_table.selectRow(max(0, list(self._slaves).index(self._slave_combo.currentText())))

    def _on_profile_table_selection(self) -> None:
        row = self._profile_table.currentRow()
        if row >= 0:
            self._profile_combo.setCurrentText(self._profile_table.item(row, 0).text())

    def _on_slave_table_selection(self) -> None:
        row = self._slave_table.currentRow()
        if row >= 0:
            self._slave_combo.setCurrentText(self._slave_table.item(row, 0).text())

    def _load_profile(self, name: str) -> None:
        flat = self._profiles[name]
        self._port_combo.blockSignals(True)
        self._port_combo.clear()
        self._port_combo.addItem(str(flat["port"]))
        self._port_combo.setCurrentIndex(0)
        self._port_combo.blockSignals(False)
        self._connection_group.set_values(flat)

    def _capture_current_profile(self) -> None:
        name = self._profile_combo.currentText()
        if name:
            self._profiles[name] = self._get_connection_values()

    def _get_connection_values(self) -> dict:
        values = dict(self._connection_group.get_values())
        values["port"] = self._port_combo.currentText()
        return values

    def _on_profile_changed(self, name: str) -> None:
        if not hasattr(self, "_profiles") or name not in self._profiles:
            return
        previous = getattr(self, "_active_profile", None)
        if previous and previous in self._profiles:
            self._profiles[previous] = self._get_connection_values()
        self._active_profile = name
        self._load_profile(name)
        self._reload_profile_table()

    def _load_slave(self, name: str) -> None:
        values = self._slaves[name]
        self._device_group.set_values(values)
        self._slave_profile_combo.blockSignals(True)
        self._slave_profile_combo.setCurrentText(values["profile_name"])
        self._slave_profile_combo.blockSignals(False)
        self._slave_transport_combo.blockSignals(True)
        index = self._slave_transport_combo.findData(values.get("transport_type", "modbus_register"))
        self._slave_transport_combo.setCurrentIndex(max(0, index))
        self._slave_transport_combo.blockSignals(False)

    def _capture_current_slave(self, name: str | None = None) -> None:
        name = name or self._slave_combo.currentText()
        if name:
            values = dict(self._device_group.get_values())
            values["profile_name"] = self._slave_profile_combo.currentText()
            values["transport_type"] = self._slave_transport_combo.currentData()
            self._slaves[name] = values

    def _on_slave_changed(self, name: str) -> None:
        if not hasattr(self, "_slaves") or name not in self._slaves:
            return
        previous = getattr(self, "_active_slave", None)
        if previous and previous in self._slaves:
            self._capture_current_slave(previous)
        self._active_slave = name
        self._load_slave(name)

    def _on_slave_profile_changed(self, profile_name: str) -> None:
        name = self._slave_combo.currentText()
        if name in self._slaves and profile_name:
            self._slaves[name]["profile_name"] = profile_name

    def _on_add_slave(self) -> None:
        dlg = _ModbusSlaveDialog(
            profile_names=list(self._profiles),
            transport_descriptors=DEFAULT_TRANSPORT_REGISTRY.descriptors(),
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name, values = dlg.get_values()
        if not name or name in self._slaves:
            show_warning(self, "Add Slave", f"Slave '{name}' already exists.")
            return
        self._slaves[name] = values
        self._slave_combo.addItem(name)
        self._slave_combo.setCurrentText(name)
        self._reload_slave_table()
        self._refresh_dirty()

    def _on_edit_slave(self) -> None:
        name = self._slave_combo.currentText()
        if not name or name not in self._slaves:
            return
        dlg = _ModbusSlaveDialog(
            self._slaves[name], name=name, profile_names=list(self._profiles),
            transport_descriptors=DEFAULT_TRANSPORT_REGISTRY.descriptors(), parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        updated_name, values = dlg.get_values()
        if updated_name != name and updated_name in self._slaves:
            show_warning(self, "Edit Slave", f"Slave '{updated_name}' already exists.")
            return
        self._slaves.pop(name)
        self._slaves[updated_name] = values
        self._slave_combo.blockSignals(True)
        try:
            self._slave_combo.clear()
            self._slave_combo.addItems(list(self._slaves))
            self._slave_combo.setCurrentText(updated_name)
        finally:
            self._slave_combo.blockSignals(False)
        self._active_slave = updated_name
        self._load_slave(updated_name)
        self._reload_slave_table()
        self._refresh_dirty()

    def _on_remove_slave(self) -> None:
        name = self._slave_combo.currentText()
        if name == "default" or name not in self._slaves:
            return
        if not ask_yes_no(self, "Remove Slave", f"Remove slave '{name}'?"):
            return
        self._slaves.pop(name)
        self._slave_combo.removeItem(self._slave_combo.currentIndex())
        self._slave_combo.setCurrentText("default")
        self._reload_slave_table()
        self._refresh_dirty()

    def _on_add_profile(self) -> None:
        dlg = _ModbusProfileDialog(self._profiles.get("default"), parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name, values = dlg.get_values()
        if not name or name in self._profiles:
            show_warning(self, "Add Profile", f"Profile '{name}' already exists.")
            return
        self._profiles[name] = values
        self._profile_combo.addItem(name)
        self._profile_combo.setCurrentText(name)
        self._slave_profile_combo.clear()
        self._slave_profile_combo.addItems(list(self._profiles))
        self._slave_transport_combo.clear()
        for descriptor in DEFAULT_TRANSPORT_REGISTRY.descriptors():
            self._slave_transport_combo.addItem(descriptor.label, descriptor.key)
        self._reload_profile_table()
        self._refresh_dirty()

    def _on_edit_profile(self) -> None:
        name = self._profile_combo.currentText()
        if not name or name not in self._profiles:
            return
        dlg = _ModbusProfileDialog(self._profiles[name], name=name, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        updated_name, values = dlg.get_values()
        if updated_name != name and updated_name in self._profiles:
            show_warning(self, "Edit Profile", f"Profile '{updated_name}' already exists.")
            return
        self._profiles.pop(name)
        self._profiles[updated_name] = values
        for slave in self._slaves.values():
            if slave.get("profile_name") == name:
                slave["profile_name"] = updated_name
        self._profile_combo.blockSignals(True)
        try:
            self._profile_combo.clear()
            self._profile_combo.addItems(list(self._profiles))
            self._profile_combo.setCurrentText(updated_name)
        finally:
            self._profile_combo.blockSignals(False)
        self._active_profile = updated_name
        self._load_profile(updated_name)
        self._slave_profile_combo.clear()
        self._slave_profile_combo.addItems(list(self._profiles))
        self._slave_transport_combo.clear()
        for descriptor in DEFAULT_TRANSPORT_REGISTRY.descriptors():
            self._slave_transport_combo.addItem(descriptor.label, descriptor.key)
        self._reload_profile_table()
        self._reload_slave_table()
        self._refresh_dirty()

    def _on_remove_profile(self) -> None:
        name = self._profile_combo.currentText()
        if name == "default" or name not in self._profiles:
            return
        if any(slave.get("profile_name") == name for slave in self._slaves.values()):
            show_warning(self, "Remove Profile", "This profile is assigned to a slave.")
            return
        if not ask_yes_no(self, "Remove Profile", f"Remove profile '{name}'?"):
            return
        self._profiles.pop(name)
        self._profile_combo.removeItem(self._profile_combo.currentIndex())
        self._profile_combo.setCurrentText("default")
        self._slave_profile_combo.clear()
        self._slave_profile_combo.addItems(list(self._profiles))
        self._reload_profile_table()
        self._refresh_dirty()

    def get_values(self) -> dict:
        values = {}
        values.update(self._connection_group.get_values())
        values.update(self._device_group.get_values())
        values["port"] = self._port_combo.currentText()
        return values

    def get_profile_values(self) -> dict[str, dict]:
        self._capture_current_profile()
        return {name: dict(values) for name, values in self._profiles.items()}

    def get_slave_values(self) -> dict[str, dict]:
        self._capture_current_slave()
        return {name: dict(values) for name, values in self._slaves.items()}

    def set_detected_ports(self, ports: list) -> None:
        self._status_pristine = False
        self._port_combo.blockSignals(True)
        self._port_combo.clear()
        if ports:
            for p in ports:
                self._port_combo.addItem(p)
            self._port_combo.setCurrentIndex(0)
            self._status_label.setStyleSheet(_STATUS_OK)
            self._status_label.setText(f"Found {len(ports)} port(s)")
        else:
            self._port_combo.addItem("—")
            self._status_label.setStyleSheet(_STATUS_FAIL)
            self._status_label.setText("No serial ports detected")
        self._port_combo.blockSignals(False)
        self._refresh_dirty()
        self._btn_detect.setEnabled(True)
        self._btn_permission.setEnabled(True)
        self._btn_low_latency.setEnabled(True)
        self._btn_test.setEnabled(True)

    def set_connection_result(self, success: bool, port: str = "") -> None:
        self._status_pristine = False
        if success:
            self._status_label.setStyleSheet(_STATUS_OK)
            self._status_label.setText(f"✓ Connected — {port}")
        else:
            self._status_label.setStyleSheet(_STATUS_FAIL)
            self._status_label.setText(f"✗ Connection failed — {port}")
        self._btn_detect.setEnabled(True)
        self._btn_permission.setEnabled(True)
        self._btn_low_latency.setEnabled(True)
        self._btn_test.setEnabled(True)

    def set_save_result(self, success: bool, message: str) -> None:
        if success:
            self._saved_profiles = deepcopy(self.get_profile_values())
            self._saved_slaves = deepcopy(self.get_slave_values())
            self._set_dirty(False)
        else:
            self._save_status_label.setStyleSheet(_STATUS_FAIL)
            self._save_status_label.setText(message)

    def set_permission_result(self, success: bool, ports: list) -> None:
        self._status_pristine = False
        if success:
            self._status_label.setStyleSheet(_STATUS_OK)
            self._status_label.setText(f"Permission updated — {len(ports)} port(s)")
        else:
            self._status_label.setStyleSheet(_STATUS_FAIL)
            self._status_label.setText("Permission update failed")
        self._btn_detect.setEnabled(True)
        self._btn_permission.setEnabled(True)
        self._btn_low_latency.setEnabled(True)
        self._btn_test.setEnabled(True)

    def set_low_latency_result(
        self,
        success: bool,
        ports: list,
        error: str = "",
    ) -> None:
        self._status_pristine = False
        if success:
            self._status_label.setStyleSheet(_STATUS_OK)
            self._status_label.setText(
                self.tr("Low latency enabled — {count} port(s)").format(count=len(ports))
            )
        else:
            self._status_label.setStyleSheet(_STATUS_FAIL)
            self._status_label.setText(error or self.tr("Low latency update failed"))
        self.set_busy(False)

    def set_busy(self, busy: bool) -> None:
        self._btn_detect.setEnabled(not busy)
        self._btn_permission.setEnabled(not busy)
        self._btn_low_latency.setEnabled(not busy)
        self._btn_test.setEnabled(not busy)
        if busy:
            self._status_pristine = False
            self._status_label.setStyleSheet(_STATUS_IDLE)
            self._status_label.setText("Working…")

    # ── AppWidget hooks ───────────────────────────────────────────────────

    def clean_up(self) -> None:
        pass

    def retranslateUi(self) -> None:
        self._title_label.setText((self.tr("SETTINGS") or "SETTINGS").capitalize())
        self._phase_bar.setTabText(0, self.tr("Connection"))
        self._phase_bar.setTabText(1, self.tr("Slaves"))
        for label, source in self._translated_labels:
            label.setText(self.tr(source))
        for button, source in (
            (self._btn_detect, "Detect Ports"),
            (self._btn_permission, "Give Permission"),
            (self._btn_test, "Test Connection"),
            (self._add_profile_btn, "Add Profile"),
            (self._edit_profile_btn, "Edit Profile"),
            (self._remove_profile_btn, "Remove Profile"),
            (self._add_slave_btn, "Add Slave"),
            (self._edit_slave_btn, "Edit Slave"),
            (self._remove_slave_btn, "Remove Slave"),
            (self._discard_btn, "Discard"),
            (self._save_btn, "Save"),
        ):
            button.setText(self.tr(source))
        self._btn_low_latency.setText(self.tr("Set Low Latency"))
        if self._status_pristine:
            self._status_label.setText(self.tr("Not tested"))
        if hasattr(self, "_saved_profiles"):
            self._refresh_dirty()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)


class _ModbusProfileDialog(AppDialog):
    def __init__(self, values: dict | None = None, name: str = "", parent=None):
        super().__init__("Modbus Connection Profile", min_width=560, parent=parent)
        values = values or {}
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)
        form_host = QWidget(self)
        form = QFormLayout(form_host)
        form.setSpacing(12)
        self._name = KeyboardLineEdit(name)
        self._name.setEnabled(name != "default")
        self._port = KeyboardLineEdit(str(values.get("port", "COM5")))
        self._baudrate = QComboBox()
        self._baudrate.addItems(["9600", "19200", "38400", "57600", "115200", "230400", "460800"])
        self._baudrate.setCurrentText(str(values.get("baudrate", 115200)))
        self._parity = QComboBox()
        self._parity.addItems(["N", "E", "O", "M", "S"])
        self._parity.setCurrentText(str(values.get("parity", "N")))
        self._bytesize = QComboBox()
        self._bytesize.addItems(["5", "6", "7", "8"])
        self._bytesize.setCurrentText(str(values.get("bytesize", 8)))
        self._stopbits = QComboBox()
        self._stopbits.addItems(["1", "2"])
        self._stopbits.setCurrentText(str(values.get("stopbits", 1)))
        self._timeout = KeyboardNumberField(decimal=True)
        self._timeout.setRange(0.001, 10.0)
        self._timeout.setDecimals(3)
        self._timeout.setSingleStep(0.001)
        self._timeout.setValue(float(values.get("timeout", 0.01)))
        self._timeout.setSuffix("s")
        for widget in (self._name, self._port):
            widget.setStyleSheet(DIALOG_INPUT_STYLE)
        for widget in (self._baudrate, self._parity, self._bytesize, self._stopbits):
            widget.setStyleSheet(DIALOG_COMBO_STYLE)
        form.addRow("Name", self._name)
        form.addRow("Port", self._port)
        form.addRow("Baudrate", self._baudrate)
        form.addRow("Parity", self._parity)
        form.addRow("Byte Size", self._bytesize)
        form.addRow("Stop Bits", self._stopbits)
        form.addRow("Timeout", self._timeout)
        root.addWidget(form_host)
        root.addWidget(self._build_button_row(ok_label="Save"))

    def get_values(self) -> tuple[str, dict]:
        return self._name.text().strip(), {
            "port": self._port.text().strip(),
            "baudrate": int(self._baudrate.currentText()),
            "bytesize": int(self._bytesize.currentText()),
            "stopbits": int(self._stopbits.currentText()),
            "parity": self._parity.currentText(),
            "timeout": float(self._timeout.value()),
            "slave_address": 10,
            "max_retries": 30,
        }


class _ModbusSlaveDialog(AppDialog):
    def __init__(
        self,
        values: dict | None = None,
        name: str = "",
        profile_names: list[str] | None = None,
        transport_descriptors=(),
        parent=None,
    ):
        super().__init__("Modbus Slave", min_width=560, parent=parent)
        values = values or {}
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)
        form_host = QWidget(self)
        form = QFormLayout(form_host)
        form.setSpacing(12)
        self._name = KeyboardLineEdit(name)
        self._name.setEnabled(name != "default")
        self._address = KeyboardNumberField()
        self._address.setRange(1, 247)
        self._address.setValue(int(values.get("slave_address", 10)))
        self._profile = QComboBox()
        self._profile.addItems(profile_names or ["default"])
        self._profile.setCurrentText(str(values.get("profile_name", "default")))
        self._transport = QComboBox()
        for descriptor in transport_descriptors:
            self._transport.addItem(descriptor.label, descriptor.key)
        if self._transport.count() == 0:
            self._transport.addItem("Standard Modbus Registers", "modbus_register")
        transport_index = self._transport.findData(
            str(values.get("transport_type", "modbus_register"))
        )
        self._transport.setCurrentIndex(max(0, transport_index))
        self._retries = KeyboardNumberField()
        self._retries.setRange(1, 100)
        self._retries.setValue(int(values.get("max_retries", 30)))
        self._name.setStyleSheet(DIALOG_INPUT_STYLE)
        self._profile.setStyleSheet(DIALOG_COMBO_STYLE)
        self._transport.setStyleSheet(DIALOG_COMBO_STYLE)
        form.addRow("Name", self._name)
        form.addRow("Slave Address", self._address)
        form.addRow("Connection Profile", self._profile)
        form.addRow("Transport Type", self._transport)
        form.addRow("Max Retries", self._retries)
        root.addWidget(form_host)
        root.addWidget(self._build_button_row(ok_label="Save"))

    def get_values(self) -> tuple[str, dict]:
        return self._name.text().strip(), {
            "slave_address": int(self._address.value()),
            "profile_name": self._profile.currentText(),
            "transport_type": self._transport.currentData(),
            "max_retries": int(self._retries.value()),
        }
