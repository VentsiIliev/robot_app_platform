from PyQt6.QtCore import pyqtSignal, QEvent, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QLabel,
    QComboBox, QScrollArea, QTabWidget, QSizePolicy,
)


from pl_gui.settings.settings_view.group_widget import GenericSettingGroup
from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE, GHOST_BTN_STYLE, BG_COLOR, BORDER,
    PRIMARY, PRIMARY_DARK, LABEL_STYLE, TAB_WIDGET_STYLE, SAVE_BUTTON_STYLE,
)
from src.applications.base.i_application_view import IApplicationView
from src.applications.modbus_settings.model.mapper import ModbusSettingsMapper
from src.applications.modbus_settings.view.modbus_settings_schema import CONNECTION_GROUP, DEVICE_GROUP

_COMBO_STYLE = f"""
QComboBox {{
    background: white;
    color: #333333;
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
    color: #333333;
    selection-background-color: rgba(122, 90, 248, 0.12);
    selection-color: {PRIMARY_DARK};
    font-size: 11pt;
    padding: 8px;
}}
"""

_STATUS_BASE = f"""
    QLabel {{
        border: 2px solid {BORDER};
        border-radius: 8px;
        padding: 8px 16px;
        font-size: 11pt;
        font-weight: bold;
        background: white;
        min-height: 40px;
    }}
"""
_STATUS_IDLE = _STATUS_BASE + "QLabel { color: #888888; }"
_STATUS_OK   = _STATUS_BASE + "QLabel { color: #2E7D32; border-color: #2E7D32; }"
_STATUS_FAIL = _STATUS_BASE + "QLabel { color: #C62828; border-color: #C62828; }"


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
    test_connection_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("ModbusSettings", parent)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Groups — owned here, not by SettingsView
        self._connection_group = GenericSettingGroup(CONNECTION_GROUP)
        self._device_group     = GenericSettingGroup(DEVICE_GROUP)

        # Tab widget — built manually so we control QScrollArea policies
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(TAB_WIDGET_STYLE)
        self._tabs.addTab(_make_scroll(self._build_connection_tab()), "Connection")
        self._tabs.addTab(_make_scroll(self._build_device_tab()),     "Device")

        # Save button
        self._save_btn = QPushButton("Save")
        self._save_btn.setStyleSheet(SAVE_BUTTON_STYLE)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._on_inner_save_btn)

        # Centre content
        content = QWidget()
        content.setStyleSheet(f"background: {BG_COLOR};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)
        content_layout.addWidget(self._tabs)
        content_layout.addWidget(self._save_btn)

        layout.addWidget(content)
        layout.addWidget(self._build_action_bar())

    # ── Tab content builders ──────────────────────────────────────────────

    def _build_connection_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {BG_COLOR};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(16)
        lay.addWidget(self._build_port_row())
        lay.addWidget(self._connection_group)
        lay.addStretch()
        return w

    def _build_device_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {BG_COLOR};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(16)
        lay.addWidget(self._device_group)
        lay.addStretch()
        return w

    def _build_port_row(self) -> QWidget:
        row_widget = QWidget()
        row_widget.setStyleSheet("background: transparent;")
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        lbl = QLabel("Port")
        lbl.setStyleSheet(LABEL_STYLE)
        lbl.setFixedWidth(80)

        self._port_combo = QComboBox()
        self._port_combo.setStyleSheet(_COMBO_STYLE)
        self._port_combo.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self._port_combo.addItem("COM5")
        self._port_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        row.addWidget(lbl)
        row.addWidget(self._port_combo, stretch=1)
        return row_widget

    # ── Action bar ────────────────────────────────────────────────────────

    def _build_action_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(f"background: {BG_COLOR}; border-top: 1px solid {BORDER};")
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(12)

        self._btn_detect = QPushButton("Detect Ports")
        self._btn_detect.setStyleSheet(GHOST_BTN_STYLE)
        self._btn_detect.setCursor(Qt.CursorShape.PointingHandCursor)

        self._btn_test = QPushButton("Test Connection")
        self._btn_test.setStyleSheet(ACTION_BTN_STYLE)
        self._btn_test.setCursor(Qt.CursorShape.PointingHandCursor)

        self._status_label = QLabel("—")
        self._status_label.setStyleSheet(_STATUS_IDLE)
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        row.addWidget(self._btn_detect)
        row.addWidget(self._btn_test)
        row.addStretch()
        row.addWidget(self._status_label)

        self._btn_detect.clicked.connect(self._on_inner_detect)
        self._btn_test.clicked.connect(self._on_inner_test)
        return bar

    # ── Named forwarders ─────────────────────────────────────────────────

    def _on_inner_save_btn(self) -> None:
        self.save_requested.emit(self.get_values())

    def _on_inner_detect(self) -> None:
        self.detect_ports_requested.emit()

    def _on_inner_test(self) -> None:
        self.test_connection_requested.emit()

    # ── Inbound setters ───────────────────────────────────────────────────

    def load_config(self, config) -> None:
        flat = ModbusSettingsMapper.to_flat_dict(config)
        self._port_combo.blockSignals(True)
        self._port_combo.clear()
        self._port_combo.addItem(str(config.port))
        self._port_combo.setCurrentIndex(0)
        self._port_combo.blockSignals(False)
        self._connection_group.set_values(flat)
        self._device_group.set_values(flat)

    def get_values(self) -> dict:
        values = {}
        values.update(self._connection_group.get_values())
        values.update(self._device_group.get_values())
        values["port"] = self._port_combo.currentText()
        return values

    def set_detected_ports(self, ports: list) -> None:
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
        self._btn_detect.setEnabled(True)
        self._btn_test.setEnabled(True)

    def set_connection_result(self, success: bool, port: str = "") -> None:
        if success:
            self._status_label.setStyleSheet(_STATUS_OK)
            self._status_label.setText(f"✓ Connected — {port}")
        else:
            self._status_label.setStyleSheet(_STATUS_FAIL)
            self._status_label.setText(f"✗ Connection failed — {port}")
        self._btn_detect.setEnabled(True)
        self._btn_test.setEnabled(True)

    def set_busy(self, busy: bool) -> None:
        self._btn_detect.setEnabled(not busy)
        self._btn_test.setEnabled(not busy)
        if busy:
            self._status_label.setStyleSheet(_STATUS_IDLE)
            self._status_label.setText("Working…")

    # ── AppWidget hooks ───────────────────────────────────────────────────

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.on_language_changed()
        super().changeEvent(event)

    def clean_up(self) -> None:
        pass
