from __future__ import annotations

from PyQt6.QtCore import QCoreApplication, QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QTabWidget, QVBoxLayout,
)

from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE, APP_PAGE_TITLE_STYLE, APP_PHASE_TAB_STYLE, BG_COLOR,
    BORDER, GHOST_BTN_STYLE, PRIMARY, SECONDARY_BG, TERTIARY_TEXT,
    TEXT_COLOR, TOUCH_SCROLL_AREA_STYLE,
)
from pl_gui.utils.utils_widgets.SwitchButton import QToggle
from src.applications.base.app_dialog import AppDialog, DIALOG_COMBO_STYLE, DIALOG_INPUT_STYLE
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.styled_message_box import ask_yes_no
from src.applications.base.widgets.custom_virtual_keyboard import KeyboardLineEdit
from src.applications.base.widgets.keyboard_number_field import KeyboardNumberField


class _PasswordDialog(AppDialog):
    def __init__(self, ssid: str, parent=None) -> None:
        super().__init__(QCoreApplication.translate("_PasswordDialog", "Wi-Fi password") or "Wi-Fi password", min_width=420, parent=parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        layout.addWidget(QLabel(ssid))
        self._password = KeyboardLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText(self.tr("Password"))
        self._password.setStyleSheet(DIALOG_INPUT_STYLE)
        layout.addWidget(self._password)
        layout.addWidget(self._build_button_row(ok_label=self.tr("Connect")))

    def password(self) -> str:
        return self._password.text()


class _IPv4Dialog(AppDialog):
    def __init__(self, current: dict, parent=None) -> None:
        super().__init__(QCoreApplication.translate("_IPv4Dialog", "IPv4 settings") or "IPv4 settings", min_width=460, parent=parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)
        form = QFormLayout()
        form.setSpacing(12)
        self._mode = QComboBox()
        self._mode.setStyleSheet(DIALOG_COMBO_STYLE)
        self._mode.addItem(self.tr("Automatic (DHCP)"), "auto")
        self._mode.addItem(self.tr("Manual"), "manual")
        self._ip = KeyboardLineEdit()
        self._gateway = KeyboardLineEdit()
        self._dns = KeyboardLineEdit()
        for field in (self._ip, self._gateway, self._dns):
            field.setStyleSheet(DIALOG_INPUT_STYLE)
        self._prefix = KeyboardNumberField()
        self._prefix.setRange(0, 32)
        self._ip.setPlaceholderText("192.168.1.100")
        self._gateway.setPlaceholderText("192.168.1.1")
        self._dns.setPlaceholderText("1.1.1.1, 8.8.8.8")
        form.addRow(self.tr("IPv4 mode"), self._mode)
        form.addRow(self.tr("IP address"), self._ip)
        form.addRow(self.tr("Prefix"), self._prefix)
        form.addRow(self.tr("Gateway"), self._gateway)
        form.addRow(self.tr("DNS servers"), self._dns)
        root.addLayout(form)
        note = QLabel(self.tr("Separate multiple DNS servers with commas."))
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {TERTIARY_TEXT};")
        root.addWidget(note)
        root.addWidget(self._build_button_row(ok_label=self.tr("Apply")))
        self._mode.currentIndexChanged.connect(self._update_fields)
        self._mode.setCurrentIndex(1 if current.get("mode") == "manual" else 0)
        self._ip.setText(current.get("ip", ""))
        self._prefix.setValue(int(current.get("prefix") or 24))
        self._gateway.setText(current.get("gateway", ""))
        self._dns.setText(current.get("dns", ""))
        self._update_fields()

    def _update_fields(self) -> None:
        manual = self._mode.currentData() == "manual"
        for widget in (self._ip, self._prefix, self._gateway):
            widget.setEnabled(manual)

    def settings(self) -> dict:
        return {
            "mode": self._mode.currentData(),
            "ip": self._ip.text().strip(),
            "prefix": str(self._prefix.value()),
            "gateway": self._gateway.text().strip(),
            "dns": self._dns.text().strip(),
        }


class NetworkSettingsView(IApplicationView):
    SHOW_JOG_WIDGET = False

    refresh_wifi_requested = pyqtSignal()
    refresh_wired_requested = pyqtSignal()
    connect_wifi_requested = pyqtSignal(str, str, bool)
    disconnect_wifi_requested = pyqtSignal()
    forget_wifi_requested = pyqtSignal(str)
    connect_wired_requested = pyqtSignal(str)
    disconnect_wired_requested = pyqtSignal(str)
    wifi_ipv4_requested = pyqtSignal()
    wired_ipv4_requested = pyqtSignal(dict)
    remote_support_requested = pyqtSignal(bool)
    remote_support_refresh_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__("NetworkSettings", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        root = QVBoxLayout(self)
        root.setContentsMargins(30, 16, 30, 20)
        root.setSpacing(14)
        self._title = QLabel()
        self._title.setStyleSheet(APP_PAGE_TITLE_STYLE)
        root.addWidget(self._title)
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(
            APP_PHASE_TAB_STYLE + "QTabWidget::pane { border: none; background: transparent; }"
        )
        root.addWidget(self._tabs, 1)
        self._wifi_list = self._build_page(
            "wifi", ("refresh", "connect", "disconnect", "forget", "ipv4")
        )
        self._wired_list = self._build_page(
            "wired", ("refresh", "connect", "disconnect", "ipv4")
        )
        self._build_remote_support_page()
        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._buttons["wifi"]["refresh"].clicked.connect(self.refresh_wifi_requested.emit)
        self._buttons["wifi"]["connect"].clicked.connect(self._on_connect_wifi)
        self._buttons["wifi"]["disconnect"].clicked.connect(self.disconnect_wifi_requested.emit)
        self._buttons["wifi"]["forget"].clicked.connect(self._on_forget_wifi)
        self._buttons["wifi"]["ipv4"].clicked.connect(self._on_wifi_ipv4)
        self._buttons["wired"]["refresh"].clicked.connect(self.refresh_wired_requested.emit)
        self._buttons["wired"]["connect"].clicked.connect(self._on_connect_wired)
        self._buttons["wired"]["disconnect"].clicked.connect(self._on_disconnect_wired)
        self._buttons["wired"]["ipv4"].clicked.connect(self._on_wired_ipv4)
        self._wifi_list.itemSelectionChanged.connect(self._sync_actions)
        self._wired_list.itemSelectionChanged.connect(self._sync_actions)
        self._status = QLabel()
        self._status.setStyleSheet(
            f"background: white; color: {TERTIARY_TEXT}; border: 1px solid {BORDER};"
            " border-radius: 12px; padding: 12px 16px;"
        )
        root.addWidget(self._status)
        self._wifi_data: list[dict] = []
        self._wired_data: list[dict] = []
        self._busy = {"wifi": False, "wired": False, "remote": False}
        self._remote_enabled: bool | None = None
        self._remote_active: bool | None = None
        self._remote_error: str | None = None
        self._sync_actions()
        self.retranslateUi()

    def _build_page(self, kind: str, actions: tuple[str, ...]) -> QListWidget:
        if not hasattr(self, "_buttons"):
            self._buttons: dict[str, dict[str, QPushButton]] = {}
            self._headings: dict[str, QLabel] = {}
            self._hints: dict[str, QLabel] = {}
        page = QFrame()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(12)
        heading = QLabel()
        heading.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 18pt; font-weight: bold; background: transparent;"
        )
        hint = QLabel()
        hint.setStyleSheet(f"color: {TERTIARY_TEXT}; background: transparent;")
        self._headings[kind] = heading
        self._hints[kind] = hint
        layout.addWidget(heading)
        layout.addWidget(hint)
        card = QFrame()
        card.setObjectName("networkCard")
        card.setStyleSheet(
            f"QFrame#networkCard {{ background: white; border: 1px solid {BORDER};"
            " border-radius: 16px; }"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(12)
        list_widget = QListWidget()
        list_widget.setMinimumHeight(310)
        list_widget.setStyleSheet(f"""
            QListWidget {{ background: white; color: {TEXT_COLOR}; border: 1px solid {BORDER};
                border-radius: 10px; font-size: 11pt; padding: 6px; }}
            QListWidget::item {{ min-height: 52px; padding: 8px 12px; border-radius: 8px; }}
            QListWidget::item:selected {{ background: {SECONDARY_BG}; color: {PRIMARY}; }}
        """ + TOUCH_SCROLL_AREA_STYLE)
        card_layout.addWidget(list_widget)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self._buttons[kind] = {}
        for action in actions:
            button = QPushButton()
            button.setStyleSheet(ACTION_BTN_STYLE if action == "connect" else GHOST_BTN_STYLE)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self._buttons[kind][action] = button
            buttons.addWidget(button)
        buttons.addStretch(1)
        card_layout.addLayout(buttons)
        layout.addWidget(card)
        layout.addStretch(1)
        self._tabs.addTab(page, "")
        return list_widget

    def _build_remote_support_page(self) -> None:
        page = QFrame()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(12)
        self._remote_heading = QLabel()
        self._remote_heading.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 18pt; font-weight: bold; background: transparent;"
        )
        self._remote_hint = QLabel()
        self._remote_hint.setStyleSheet(f"color: {TERTIARY_TEXT}; background: transparent;")
        layout.addWidget(self._remote_heading)
        layout.addWidget(self._remote_hint)
        card = QFrame()
        card.setObjectName("remoteSupportCard")
        card.setStyleSheet(
            f"QFrame#remoteSupportCard {{ background: white; border: 1px solid {BORDER};"
            " border-radius: 16px; }"
        )
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(20)
        labels = QVBoxLayout()
        labels.setSpacing(8)
        self._remote_state = QLabel()
        self._remote_state.setStyleSheet(
            f"color: {TEXT_COLOR}; font-size: 13pt; font-weight: bold; background: transparent;"
        )
        self._remote_service = QLabel()
        self._remote_service.setWordWrap(True)
        self._remote_service.setStyleSheet(f"color: {TERTIARY_TEXT}; background: transparent;")
        labels.addWidget(self._remote_state)
        labels.addWidget(self._remote_service)
        card_layout.addLayout(labels, 1)
        self._remote_switch = QToggle()
        self._remote_switch.setFixedHeight(36)
        self._remote_switch.setMinimumWidth(76)
        self._remote_switch.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remote_switch.setEnabled(False)
        self._remote_switch.clicked.connect(self._on_remote_switch_clicked)
        card_layout.addWidget(self._remote_switch)
        layout.addWidget(card)
        layout.addStretch(1)
        self._tabs.addTab(page, "")

    def _on_remote_switch_clicked(self, enabled: bool) -> None:
        self._remote_switch.sync_visual_state(bool(self._remote_enabled))
        self.remote_support_requested.emit(enabled)

    def _on_tab_changed(self, index: int) -> None:
        if index == 2:
            self.remote_support_refresh_requested.emit()

    def is_remote_support_visible(self) -> bool:
        return self.isVisible() and self._tabs.currentIndex() == 2

    def set_remote_support_status(self, status: dict) -> None:
        self._remote_error = None
        self._remote_enabled = bool(status["enabled"])
        self._remote_active = bool(status["active"])
        self._remote_switch.sync_visual_state(self._remote_enabled)
        self._update_remote_labels()
        self._sync_actions()

    def set_remote_support_error(self, message: str) -> None:
        self._remote_error = message
        self._remote_enabled = None
        self._remote_active = None
        self._remote_switch.sync_visual_state(False)
        self._update_remote_labels()
        self._sync_actions()

    def _update_remote_labels(self) -> None:
        if self._remote_error:
            self._remote_state.setText(self.tr("Remote Support unavailable"))
            self._remote_service.setText(self._remote_error)
        elif self._remote_enabled is None:
            self._remote_state.setText(self.tr("Remote Support: checking…"))
            self._remote_service.setText(self.tr("Checking remote support status…"))
        elif self._remote_enabled != self._remote_active:
            self._remote_state.setText(self.tr("Remote Support: action needed"))
            self._remote_service.setText(
                self.tr("Remote access is still active.") if self._remote_active
                else self.tr("Remote access is not running.")
            )
        elif self._remote_enabled:
            self._remote_state.setText(self.tr("Remote Support: ON"))
            self._remote_service.setText(self.tr("PL PROJECT support can connect to this robot."))
        else:
            self._remote_state.setText(self.tr("Remote Support: OFF"))
            self._remote_service.setText(self.tr("PL PROJECT support cannot connect to this robot."))

    def set_wifi_networks(self, networks: list[dict]) -> None:
        self._wifi_data = list(networks)
        self._wifi_list.clear()
        for network in networks:
            ssid = network.get("ssid", "")
            state = self.tr("Connected") if network.get("connected") else self.tr("Available")
            security = self.tr("Secured") if network.get("secure") else self.tr("Open")
            item = QListWidgetItem(f"{ssid}    ·    {network.get('signal', '')}%    ·    {security}    ·    {state}")
            item.setData(Qt.ItemDataRole.UserRole, network)
            self._wifi_list.addItem(item)
        if not networks:
            self._add_empty(self._wifi_list, self.tr("No Wi-Fi networks found."))
        self._sync_actions()

    def set_wired_devices(self, devices: list[dict]) -> None:
        self._wired_data = list(devices)
        self._wired_list.clear()
        for device in devices:
            name = device.get("device", "")
            state = device.get("state", "")
            connection = device.get("connection", "")
            item = QListWidgetItem(f"{name}    ·    {state}    ·    {connection}")
            item.setData(Qt.ItemDataRole.UserRole, device)
            self._wired_list.addItem(item)
        if not devices:
            self._add_empty(self._wired_list, self.tr("No wired interfaces found."))
        self._sync_actions()

    @staticmethod
    def _add_empty(widget: QListWidget, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        widget.addItem(item)

    def _selected(self, kind: str) -> dict | None:
        widget = self._wifi_list if kind == "wifi" else self._wired_list
        item = widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _sync_actions(self) -> None:
        if not hasattr(self, "_busy"):
            return
        self._remote_switch.setEnabled(self._remote_enabled is not None and not self._busy["remote"])
        wifi = self._selected("wifi")
        wired = self._selected("wired")
        for kind, selected in (("wifi", wifi), ("wired", wired)):
            for action, button in self._buttons[kind].items():
                enabled = not self._busy[kind]
                if action not in ("refresh", "disconnect"):
                    enabled = enabled and selected is not None
                if kind == "wifi" and action == "connect" and selected:
                    enabled = enabled and not selected.get("connected", False)
                if kind == "wifi" and action == "disconnect":
                    enabled = enabled and any(network.get("connected") for network in self._wifi_data)
                if kind == "wifi" and action == "ipv4" and selected:
                    enabled = enabled and selected.get("connected", False)
                if kind == "wired" and action == "ipv4" and selected:
                    enabled = enabled and bool(selected.get("connection")) and selected.get("connection") != "--"
                if kind == "wired" and action in ("connect", "disconnect"):
                    connected = bool(selected and str(selected.get("state", "")).lower() == "connected")
                    enabled = enabled and selected is not None
                    enabled = enabled and (not connected if action == "connect" else connected)
                button.setEnabled(enabled)

    def set_busy(self, kind: str, busy: bool) -> None:
        self._busy[kind] = busy
        self._sync_actions()

    def set_status(self, message: str) -> None:
        self._status.setText(message)

    def set_error(self, message: str) -> None:
        self._status.setText(message)

    def edit_ipv4(self, current: dict) -> dict | None:
        dialog = _IPv4Dialog(current, self)
        return dialog.settings() if dialog.exec() else None

    def _on_connect_wifi(self) -> None:
        network = self._selected("wifi")
        if network is None:
            return
        password = ""
        if network.get("secure"):
            dialog = _PasswordDialog(network["ssid"], self)
            if not dialog.exec():
                return
            password = dialog.password()
        self.connect_wifi_requested.emit(network["ssid"], password, bool(network.get("secure")))

    def _on_forget_wifi(self) -> None:
        network = self._selected("wifi")
        if network and ask_yes_no(
            self, self.tr("Forget Wi-Fi network"),
            self.tr("Remove the saved connection for {ssid}?").format(ssid=network["ssid"]),
        ):
            self.forget_wifi_requested.emit(network["ssid"])

    def _on_wifi_ipv4(self) -> None:
        if self._selected("wifi"):
            self.wifi_ipv4_requested.emit()

    def _on_connect_wired(self) -> None:
        device = self._selected("wired")
        if device:
            self.connect_wired_requested.emit(device["device"])

    def _on_disconnect_wired(self) -> None:
        device = self._selected("wired")
        if device:
            self.disconnect_wired_requested.emit(device["device"])

    def _on_wired_ipv4(self) -> None:
        device = self._selected("wired")
        if device:
            self.wired_ipv4_requested.emit(device)

    def retranslateUi(self) -> None:
        self._title.setText(self.tr("Network Settings"))
        self._tabs.setTabText(0, self.tr("Wi-Fi"))
        self._tabs.setTabText(1, self.tr("Wired"))
        self._tabs.setTabText(2, self.tr("Remote Support"))
        self._remote_heading.setText(self.tr("Remote Support"))
        self._remote_hint.setText(self.tr("Allow PL PROJECT support engineers to connect to this robot."))
        self._update_remote_labels()
        for kind, source, hint in (
            ("wifi", "Wi-Fi networks", "Scan and manage nearby wireless networks."),
            ("wired", "Wired interfaces", "Connect and configure Ethernet interfaces."),
        ):
            self._headings[kind].setText(self.tr(source))
            self._hints[kind].setText(self.tr(hint))
        for kind in ("wifi", "wired"):
            for action, button in self._buttons[kind].items():
                source = {
                    "refresh": "Refresh", "connect": "Connect",
                    "disconnect": "Disconnect", "forget": "Forget",
                    "ipv4": "IPv4 settings",
                }[action]
                button.setText(self.tr(source))
        if not self._status.text():
            self._status.setText(self.tr("Ready"))
        if self._wifi_data:
            self.set_wifi_networks(self._wifi_data)
        if self._wired_data:
            self.set_wired_devices(self._wired_data)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def clean_up(self) -> None:
        pass
