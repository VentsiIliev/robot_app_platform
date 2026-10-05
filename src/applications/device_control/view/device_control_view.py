from __future__ import annotations
from functools import partial
from typing import List

from PyQt6.QtCore import QEvent, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, QLabel, QLayout,
    QScrollArea, QTabWidget, QWidget, QFrame,
)
from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    APP_PAGE_TITLE_STYLE,
    BG_COLOR,
    BORDER,
    GHOST_BTN_STYLE,
    GROUP_STYLE,
    LABEL_STYLE,
    PRIMARY,
    PRIMARY_LIGHT,
    SECONDARY_BG,
    STATUS_OK,
    ERROR_COLOR,
    TERTIARY_TEXT,
    TEXT_COLOR,
    TOUCH_SCROLL_AREA_STYLE,
)
from src.applications.base.app_styles import indicator_dot_style

from src.applications.base.i_application_view import IApplicationView
from pl_gui.utils.utils_widgets.SwitchButton import QToggle
from src.applications.device_control.service.i_device_control_service import (
    IDeviceControlDevice,
    MotorEntry,
)

_MUTED     = "#9E9E9E"

_DOT_ON  = indicator_dot_style(color=PRIMARY)
_DOT_OFF = indicator_dot_style(color=TERTIARY_TEXT)
_DOT_NA  = indicator_dot_style(color=_MUTED)

_STATE_STYLE = f"""
QLabel {{
    background: white;
    color: {TEXT_COLOR};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 11pt;
    min-height: 36px;
}}
"""

_STATE_ERROR_STYLE = f"""
QLabel {{
    background: {PRIMARY_LIGHT};
    color: {TEXT_COLOR};
    border: 1px solid {PRIMARY};
    border-radius: 8px;
    padding: 12px 16px;
    font-size: 11pt;
    font-weight: bold;
    min-height: 36px;
}}
"""

_STATIC_DEVICES = [
    ("laser",       "Laser"),
    ("vacuum_pump", "Vacuum Pump"),
    ("generator",   "Generator"),
]


class DeviceControlView(IApplicationView):

    laser_on_requested        = pyqtSignal()
    laser_off_requested       = pyqtSignal()
    vacuum_pump_on_requested  = pyqtSignal()
    vacuum_pump_off_requested = pyqtSignal()
    motor_on_requested        = pyqtSignal(int)   # carries motor address
    motor_off_requested       = pyqtSignal(int)   # carries motor address
    generator_on_requested    = pyqtSignal()
    generator_off_requested   = pyqtSignal()
    device_action_requested   = pyqtSignal(str, str)
    device_enabled_requested = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__("Device Control", parent)

    def setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 16, 40, 20)
        root.setSpacing(16)
        self._page_title = QLabel()
        self._page_title.setStyleSheet(APP_PAGE_TITLE_STYLE)
        root.addWidget(self._page_title)

        content = QHBoxLayout()
        content.setSpacing(16)
        root.addLayout(content, 1)
        self._sidebar = QFrame()
        self._sidebar.setObjectName("devicesSidebar")
        self._sidebar.setStyleSheet(
            f"QFrame#devicesSidebar {{ background: white; border: 1px solid {BORDER};"
            " border-radius: 18px; }"
        )
        self._sidebar.setFixedWidth(230)
        self._sidebar_layout = QVBoxLayout(self._sidebar)
        self._sidebar_layout.setContentsMargins(8, 8, 8, 8)
        self._sidebar_layout.setSpacing(4)
        self._sidebar_layout.addStretch(1)
        content.addWidget(self._sidebar, 0, Qt.AlignmentFlag.AlignTop)
        self._sidebar.hide()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._inner = QWidget()
        self._inner.setStyleSheet(f"background-color: {BG_COLOR};")
        self._device_layout = QVBoxLayout(self._inner)
        self._device_layout.setSpacing(10)
        self._device_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self._inner)
        self._legacy_scroll = scroll
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet("QTabWidget::pane { border: none; background: transparent; }")
        self._tabs.tabBar().hide()
        self._tabs.setVisible(False)
        self._tabs.currentChanged.connect(self._sync_sidebar_selection)
        content.addWidget(self._tabs, 1)
        content.addWidget(scroll, 1)
        self._nav_buttons: dict[str, QPushButton] = {}
        self._nav_order: list[str] = []
        self._device_labels: dict[str, str] = {}
        self._device_headings: dict[str, QLabel] = {}
        self._device_hints: dict[str, QLabel] = {}
        self._static_text_widgets: list[tuple[QLabel | QGroupBox, str]] = []

        self._device_tabs: dict[str, QWidget] = {}
        self._device_tab_layouts: dict[str, QVBoxLayout] = {}
        self._device_state_labels: dict[str, QLabel] = {}
        self._device_state_boxes: dict[str, QGroupBox] = {}
        self._device_buttons: dict[str, list[QPushButton]] = {}
        self._device_action_labels: dict[str, QLabel] = {}
        self._device_enabled_toggles: dict[str, QToggle] = {}
        self._enabled_badges: dict[str, QLabel] = {}
        self._health_badges: dict[str, QLabel] = {}
        self._vacuum_status_dot: QLabel | None = None
        self._vacuum_status_label: QLabel | None = None

        self._on_btns:    dict[str, QPushButton] = {}
        self._off_btns:   dict[str, QPushButton] = {}
        self._dots:       dict[str, QLabel]      = {}
        self._motor_boxes: dict[str, QGroupBox]  = {}

        _forwarders = {
            "laser":       (self._on_laser_on,       self._on_laser_off),
            "vacuum_pump": (self._on_vacuum_pump_on,  self._on_vacuum_pump_off),
            "generator":   (self._on_generator_on,    self._on_generator_off),
        }
        for key, label in _STATIC_DEVICES:
            self._add_device_row(key, label, _forwarders[key][0], _forwarders[key][1])

        # motor rows added later via setup_motors()
        self._device_layout.addStretch()
        self.retranslateUi()

    def _clear_navigation(self) -> None:
        while self._sidebar_layout.count():
            item = self._sidebar_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._nav_buttons.clear()
        self._nav_order.clear()
        self._sidebar_layout.addStretch(1)

    def _add_navigation_item(self, key: str, label: str) -> None:
        self._device_labels[key] = label
        display_label = self._display_name(key, label)
        if key == "physical_control_buttons":
            display_label = self.tr("Physical control\n     buttons")
        button = QPushButton(f"●  {display_label}")
        button.setCheckable(True)
        button.setProperty("device_key", key)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(54)
        button.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {PRIMARY}; border: none;
                border-radius: 12px; text-align: left; padding: 8px 16px;
                font-size: 11pt; font-weight: bold; }}
            QPushButton:hover {{ background: {PRIMARY_LIGHT}; }}
            QPushButton:checked {{ background: {PRIMARY}; color: white; }}
        """)
        button.clicked.connect(self._on_navigation_clicked)
        self._sidebar_layout.insertWidget(self._sidebar_layout.count() - 1, button)
        self._nav_buttons[key] = button
        self._nav_order.append(key)
        self._sidebar.setFixedHeight(16 + 58 * len(self._nav_order))

    def _on_navigation_clicked(self) -> None:
        button = self.sender()
        if isinstance(button, QPushButton):
            key = str(button.property("device_key"))
            if key in self._nav_order:
                index = self._nav_order.index(key)
                self._tabs.setCurrentIndex(index)
                self._sync_sidebar_selection(index)

    def _sync_sidebar_selection(self, index: int) -> None:
        for position, key in enumerate(self._nav_order):
            self._nav_buttons[key].setChecked(position == index)

    @staticmethod
    def _card_style() -> str:
        return (
            f"QFrame#deviceCard {{ background: white; border: 1px solid {BORDER};"
            " border-radius: 18px; }"
        )

    def _device_hint(self, key: str) -> str:
        hints = {
            "vacuum_pump": self.tr("Turn the pump on or off and check its state."),
            "tray_fan": self.tr("Turn the fan on or off and check its state."),
            "vacuum_sensor": self.tr("Live reading from the vacuum sensor."),
            "physical_control_buttons": self.tr("Switch the Start and Pause button outputs."),
            "paint_head": self.tr("Configure how the paint head steps between settings."),
        }
        return hints.get(key, self.tr("Manage availability and device commands."))

    def _display_name(self, key: str, fallback: str) -> str:
        names = {
            "vacuum_pump": self.tr("Vacuum pump"),
            "tray_fan": self.tr("Tray fan"),
            "vacuum_sensor": self.tr("Vacuum sensor"),
            "physical_control_buttons": self.tr("Physical control buttons"),
            "paint_head": self.tr("Paint head"),
            "cameras": self.tr("Cameras"),
        }
        return names.get(key, fallback)

    @staticmethod
    def _group_actions(device_key: str, actions: dict) -> dict[str, list[tuple[str, str]]]:
        groups: dict[str, list[tuple[str, str]]] = {}
        for action, label in actions.items():
            if action in {"on", "off"}:
                name = {"vacuum_pump": "Pump", "tray_fan": "Fan"}.get(
                    device_key, device_key.replace("_", " ").title()
                )
            elif action.endswith(("_on", "_off")):
                name = action.rsplit("_", 1)[0].replace("_", " ").title()
            else:
                name = label
            groups.setdefault(name, []).append((action, label))
        return groups

    def setup_devices(self, devices: List[IDeviceControlDevice]) -> None:
        self._clear_navigation()
        while self._tabs.count():
            widget = self._tabs.widget(0)
            self._tabs.removeTab(0)
            widget.deleteLater()
        self._device_tabs.clear()
        self._device_tab_layouts.clear()
        self._device_state_labels.clear()
        self._device_state_boxes.clear()
        self._device_buttons.clear()
        self._device_action_labels.clear()
        self._device_enabled_toggles.clear()
        self._enabled_badges.clear()
        self._health_badges.clear()
        self._device_labels.clear()
        self._device_headings.clear()
        self._device_hints.clear()
        self._static_text_widgets.clear()
        self._vacuum_status_dot = None
        self._vacuum_status_label = None

        for device in devices:
            page = QWidget()
            page.setStyleSheet(f"background-color: {BG_COLOR};")
            layout = QVBoxLayout(page)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(12)
            layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

            header = QHBoxLayout()
            title_column = QVBoxLayout()
            title_column.setSpacing(2)
            heading = QLabel(self._display_name(device.key, device.label))
            heading.setStyleSheet(
                f"color: {TEXT_COLOR}; font-size: 18pt; font-weight: bold; "
                "background: transparent;"
            )
            hint = QLabel(self._device_hint(device.key))
            hint.setStyleSheet(
                f"color: {TERTIARY_TEXT}; font-size: 10pt; background: transparent;"
            )
            title_column.addWidget(heading)
            title_column.addWidget(hint)
            self._device_headings[device.key] = heading
            self._device_hints[device.key] = hint
            header.addLayout(title_column, 1)
            lifecycle_label = QLabel(self.tr("Enabled"))
            self._static_text_widgets.append((lifecycle_label, "Enabled"))
            lifecycle_label.setStyleSheet(LABEL_STYLE)
            enabled_toggle = QToggle()
            enabled_toggle.setFixedHeight(40)
            enabled_toggle.setProperty("device_key", device.key)
            enabled_toggle.sync_visual_state(device.is_enabled())
            enabled_toggle.stateChanged.connect(self._on_device_enabled_changed)
            if device.key != "vacuum_sensor":
                header.addWidget(lifecycle_label)
                header.addWidget(enabled_toggle)
            layout.addLayout(header)

            badge_row = QHBoxLayout()
            badge_row.setSpacing(8)
            enabled_badge = QLabel()
            health_badge = QLabel()
            for badge in (enabled_badge, health_badge):
                badge.setStyleSheet(
                    f"background: {SECONDARY_BG}; color: {TERTIARY_TEXT};"
                    " border-radius: 14px; padding: 6px 12px;"
                )
                badge_row.addWidget(badge)
            badge_row.addStretch(1)
            self._enabled_badges[device.key] = enabled_badge
            self._health_badges[device.key] = health_badge
            if device.key != "vacuum_sensor":
                layout.addLayout(badge_row)

            if device.key == "vacuum_sensor":
                reading_card = QFrame()
                reading_card.setObjectName("deviceCard")
                reading_card.setStyleSheet(self._card_style())
                reading_layout = QVBoxLayout(reading_card)
                reading_layout.setContentsMargins(22, 20, 22, 20)
                reading_layout.setSpacing(14)
                reading_title = QLabel(self.tr("Reading"))
                self._static_text_widgets.append((reading_title, "Reading"))
                reading_title.setStyleSheet(LABEL_STYLE)
                reading_layout.addWidget(reading_title)
                status_row = QHBoxLayout()
                status_row.setSpacing(12)
                self._vacuum_status_dot = QLabel("●")
                self._vacuum_status_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self._vacuum_status_dot.setFixedSize(40, 40)
                self._vacuum_status_dot.setStyleSheet(
                    indicator_dot_style(color=_MUTED, font_pt=30)
                )
                self._vacuum_status_label = QLabel(self.tr("Waiting for sensor reading"))
                self._vacuum_status_label.setStyleSheet(
                    f"color: {TERTIARY_TEXT}; font-size: 13pt; font-weight: bold;"
                )
                status_row.addWidget(self._vacuum_status_dot)
                status_row.addWidget(self._vacuum_status_label)
                status_row.addStretch()
                reading_layout.addLayout(status_row)
                layout.addWidget(reading_card)

            state_box = QGroupBox(self.tr("Device State"))
            self._static_text_widgets.append((state_box, "Device State"))
            state_box.setStyleSheet(GROUP_STYLE)
            state_box.hide()
            state_layout = QVBoxLayout(state_box)
            state_layout.setContentsMargins(16, 16, 16, 16)
            state = QLabel(self.tr("State: not read"))
            state.setWordWrap(True)
            state.setStyleSheet(_STATE_STYLE)
            state_layout.addWidget(state)
            layout.addWidget(state_box)
            self._device_state_boxes[device.key] = state_box

            action_status = QLabel(self.tr("Ready"))
            action_status.setStyleSheet(
                f"color: {TERTIARY_TEXT}; background: {SECONDARY_BG};"
                " border-radius: 12px; padding: 10px 14px; font-size: 10pt;"
            )
            buttons = []
            actions = device.actions()
            if actions:
                actions_box = QFrame()
                actions_box.setObjectName("deviceCard")
                actions_box.setStyleSheet(self._card_style())
                actions_layout = QVBoxLayout(actions_box)
                actions_layout.setContentsMargins(22, 20, 22, 20)
                actions_layout.setSpacing(12)
                section_title = QLabel(self.tr("Controls"))
                self._static_text_widgets.append((section_title, "Controls"))
                section_title.setStyleSheet(LABEL_STYLE)
                actions_layout.addWidget(section_title)
                for group_name, group_actions in self._group_actions(device.key, actions).items():
                    action_row = QHBoxLayout()
                    action_row.setSpacing(10)
                    row_label = QLabel(group_name)
                    row_label.setStyleSheet(LABEL_STYLE)
                    action_row.addWidget(row_label, 1)
                    for action, label in group_actions:
                        button = QPushButton(label)
                        button.setProperty("device_key", device.key)
                        button.setProperty("action", action)
                        button.setStyleSheet(self._action_button_style(action))
                        button.setMinimumWidth(130)
                        button.setCursor(Qt.CursorShape.PointingHandCursor)
                        button.clicked.connect(self._on_device_action_clicked)
                        action_row.addWidget(button)
                        buttons.append(button)
                    actions_layout.addLayout(action_row)
                actions_layout.addWidget(action_status)
                layout.addWidget(actions_box)
            layout.addStretch()
            page_scroll = QScrollArea()
            page_scroll.setWidgetResizable(True)
            page_scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            page_scroll.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
            page_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            page_scroll.setStyleSheet(TOUCH_SCROLL_AREA_STYLE)
            page_scroll.setWidget(page)
            self._tabs.addTab(page_scroll, device.label)
            self._add_navigation_item(device.key, device.label)
            self._device_tabs[device.key] = page
            self._device_tab_layouts[device.key] = layout
            self._device_state_labels[device.key] = state
            self._device_buttons[device.key] = buttons
            if actions:
                self._device_action_labels[device.key] = action_status
            self._device_enabled_toggles[device.key] = enabled_toggle
            self._set_device_buttons_enabled(device.key, device.is_enabled())
            self._set_device_idle_status(device.key)
            self.set_device_state(
                device.key,
                {"enabled": device.is_enabled(), "healthy": None},
            )

        has_devices = bool(devices)
        self._tabs.setVisible(has_devices)
        self._sidebar.setVisible(has_devices)
        self._legacy_scroll.setVisible(not has_devices)
        if has_devices:
            self._tabs.setCurrentIndex(0)
            self._sync_sidebar_selection(0)

    def set_device_panel(self, device_key: str, panel: QWidget) -> None:
        """Add an optional device-specific panel to an existing device tab."""
        layout = self._device_tab_layouts.get(device_key)
        if layout is None:
            panel.deleteLater()
            return
        layout.insertWidget(max(0, layout.count() - 1), panel)

    def add_custom_tab(self, key: str, label: str, panel: QWidget) -> None:
        """Add a lifecycle-managed extension panel without device toggles."""
        existing = self._device_tabs.get(key)
        if existing is not None:
            index = self._tabs.indexOf(existing)
            if index >= 0:
                self._tabs.removeTab(index)
                nav = self._nav_buttons.pop(key, None)
                if nav is not None:
                    self._sidebar_layout.removeWidget(nav)
                    nav.deleteLater()
                    self._nav_order.remove(key)
            existing.deleteLater()
        panel.setParent(self._tabs)
        self._tabs.addTab(panel, label)
        self._add_navigation_item(key, label)
        self._device_tabs[key] = panel
        self._tabs.setVisible(True)
        self._sidebar.setVisible(True)
        self._legacy_scroll.setVisible(False)
        self._sync_sidebar_selection(self._tabs.currentIndex())

    def set_device_state(self, device_key: str, state: dict[str, object]) -> None:
        label = self._device_state_labels.get(device_key)
        if label is None:
            return
        if state.get("enabled") is False:
            text = self.tr("Disabled")
            label.setStyleSheet(_STATE_STYLE)
        elif state.get("healthy") is False:
            text = f"Communication error: {state.get('error', 'read failed')}"
            label.setStyleSheet(_STATE_ERROR_STYLE)
        else:
            values = ", ".join(
                f"{self._state_label(key)}: "
                f"{'N/A' if key == 'healthy' and value is None else value}"
                for key, value in state.items()
                if key != "error" or value
            )
            text = f"State: {values or 'OK'}"
            label.setStyleSheet(_STATE_STYLE)
        label.setText(text)
        state_box = self._device_state_boxes.get(device_key)
        if state_box is not None:
            state_box.setVisible(state.get("healthy") is False and bool(state.get("error")))
        self._update_state_badges(device_key, state)
        if device_key == "vacuum_sensor":
            self._set_vacuum_sensor_status(state)

    def _update_state_badges(self, device_key: str, state: dict[str, object]) -> None:
        enabled_badge = self._enabled_badges.get(device_key)
        health_badge = self._health_badges.get(device_key)
        if enabled_badge is None or health_badge is None:
            return
        enabled = state.get("enabled")
        enabled_badge.setText(self.tr("Enabled") if enabled is not False else self.tr("Disabled"))
        enabled_badge.setStyleSheet(
            f"background: {SECONDARY_BG}; color: {STATUS_OK if enabled is not False else TERTIARY_TEXT};"
            " border-radius: 14px; padding: 6px 12px;"
        )
        healthy = state.get("healthy")
        health_badge.setText(
            self.tr("Healthy") if healthy is True else
            self.tr("Communication error") if healthy is False else
            self.tr("Health: not reported")
        )
        health_badge.setStyleSheet(
            f"background: {SECONDARY_BG}; color: {ERROR_COLOR if healthy is False else TERTIARY_TEXT};"
            " border-radius: 14px; padding: 6px 12px;"
        )

    @staticmethod
    def _state_label(key: str) -> str:
        if key == "healthy":
            return "Health"
        return key.replace("_", " ").title()

    def _set_vacuum_sensor_status(self, state: dict[str, object]) -> None:
        if self._vacuum_status_dot is None or self._vacuum_status_label is None:
            return
        if state.get("healthy") is False:
            color = _MUTED
            text = self.tr("Sensor unavailable")
        elif bool(state.get("detected")):
            color = PRIMARY
            text = self.tr("Workpiece attached")
        else:
            color = TERTIARY_TEXT
            text = self.tr("No workpiece attached")
        self._vacuum_status_dot.setStyleSheet(
            indicator_dot_style(color=color, font_pt=30)
        )
        self._vacuum_status_label.setText(text)
        self._vacuum_status_label.setStyleSheet(
            f"color: {color}; font-size: 14pt; font-weight: bold;"
        )

    def _on_device_action_clicked(self) -> None:
        button = self.sender()
        if isinstance(button, QPushButton):
            self.device_action_requested.emit(
                str(button.property("device_key")),
                str(button.property("action")),
            )

    def _on_device_enabled_changed(self, state: int) -> None:
        toggle = self.sender()
        if isinstance(toggle, QToggle):
            self.device_enabled_requested.emit(
                str(toggle.property("device_key")),
                bool(state),
            )

    @staticmethod
    def _action_button_style(action: str) -> str:
        normalized = action.lower()
        if normalized.endswith("off") or normalized.startswith("close"):
            return GHOST_BTN_STYLE
        return ACTION_BTN_STYLE

    def set_device_busy(self, device_key: str, busy: bool) -> None:
        for button in self._device_buttons.get(device_key, []):
            button.setEnabled(not busy)
        label = self._device_action_labels.get(device_key)
        if label is not None:
            if busy:
                label.setText(self.tr("Working…"))
            else:
                self._set_device_idle_status(device_key)
            label.setStyleSheet(
                f"color: {TERTIARY_TEXT}; font-size: 10pt; font-weight: bold;"
            )

    def set_device_enabled(self, device_key: str, enabled: bool) -> None:
        toggle = self._device_enabled_toggles.get(device_key)
        if toggle is not None:
            blocked = toggle.blockSignals(True)
            try:
                toggle.sync_visual_state(enabled)
            finally:
                toggle.blockSignals(blocked)
        self._set_device_buttons_enabled(device_key, enabled)
        self._set_device_idle_status(device_key)
        enabled_badge = self._enabled_badges.get(device_key)
        if enabled_badge is not None:
            enabled_badge.setText(self.tr("Enabled") if enabled else self.tr("Disabled"))
            enabled_badge.setStyleSheet(
                f"background: {SECONDARY_BG}; color: {STATUS_OK if enabled else TERTIARY_TEXT};"
                " border-radius: 14px; padding: 6px 12px;"
            )

    def _set_device_buttons_enabled(self, device_key: str, enabled: bool) -> None:
        for button in self._device_buttons.get(device_key, []):
            button.setEnabled(enabled)

    def _set_device_idle_status(self, device_key: str) -> None:
        label = self._device_action_labels.get(device_key)
        toggle = self._device_enabled_toggles.get(device_key)
        if label is None or toggle is None:
            return
        label.setText(self.tr("Ready") if toggle.isChecked() else self.tr("Disabled"))
        label.setStyleSheet(
            f"color: {TERTIARY_TEXT}; font-size: 10pt; font-weight: bold;"
        )

    def set_device_action_result(self, device_key: str, success: bool) -> None:
        label = self._device_action_labels.get(device_key)
        if label is None:
            return
        toggle = self._device_enabled_toggles.get(device_key)
        if success and toggle is not None and not toggle.isChecked():
            label.setText(self.tr("Disabled"))
        else:
            label.setText(self.tr("Command completed") if success else self.tr("Command failed"))
        label.setStyleSheet(
            f"color: {PRIMARY if success else TERTIARY_TEXT}; "
            "font-size: 10pt; font-weight: bold;"
        )

    # ── Motor rows built dynamically from config ───────────────────────

    def setup_motors(self, motors: List[MotorEntry]) -> None:
        for key, box in list(self._motor_boxes.items()):
            self._device_layout.removeWidget(box)
            box.deleteLater()
            self._on_btns.pop(key, None)
            self._off_btns.pop(key, None)
            self._dots.pop(key, None)
        self._motor_boxes.clear()

        for motor in motors:
            key = f"motor_{motor.address}"
            self._add_device_row(
                key, motor.name,
                partial(self._emit_motor_on,  motor.address),
                partial(self._emit_motor_off, motor.address),
            )


    def _add_device_row(self, key: str, label: str, on_slot, off_slot) -> None:
        box = QGroupBox(label)
        box.setStyleSheet(GROUP_STYLE)
        row = QHBoxLayout(box)
        row.setSpacing(12)
        row.setContentsMargins(16, 8, 16, 8)

        dot = QLabel("●")
        dot.setStyleSheet(_DOT_NA)
        dot.setFixedWidth(22)

        btn_on = QPushButton("ON")
        btn_on.setStyleSheet(ACTION_BTN_STYLE)
        btn_on.setEnabled(False)
        btn_on.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_on.clicked.connect(on_slot)

        btn_off = QPushButton("OFF")
        btn_off.setStyleSheet(GHOST_BTN_STYLE)
        btn_off.setEnabled(False)
        btn_off.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_off.clicked.connect(off_slot)

        row.addWidget(dot)
        row.addWidget(btn_on)
        row.addWidget(btn_off)
        row.addStretch()

        self._on_btns[key]  = btn_on
        self._off_btns[key] = btn_off
        self._dots[key]     = dot
        if key.startswith("motor_"):
            self._motor_boxes[key] = box

        # Insert before the trailing stretch
        self._device_layout.insertWidget(self._device_layout.count() - 1, box)

    # ── Named forwarders — static devices ─────────────────────────────

    def _on_laser_on(self):        self.laser_on_requested.emit()
    def _on_laser_off(self):       self.laser_off_requested.emit()
    def _on_vacuum_pump_on(self):  self.vacuum_pump_on_requested.emit()
    def _on_vacuum_pump_off(self): self.vacuum_pump_off_requested.emit()
    def _on_generator_on(self):    self.generator_on_requested.emit()
    def _on_generator_off(self):   self.generator_off_requested.emit()

    # Named forwarders for motor signals (address-carrying)
    def _emit_motor_on(self, address: int) -> None:
        self.motor_on_requested.emit(address)

    def _emit_motor_off(self, address: int) -> None:
        self.motor_off_requested.emit(address)

    # ── Inbound setters ───────────────────────────────────────────────

    def set_device_available(self, key: str, available: bool) -> None:
        if key not in self._on_btns:
            return
        self._on_btns[key].setEnabled(available)
        self._off_btns[key].setEnabled(available)
        self._on_btns[key].setStyleSheet(ACTION_BTN_STYLE)
        self._off_btns[key].setStyleSheet(GHOST_BTN_STYLE)
        self._dots[key].setStyleSheet(_DOT_OFF if available else _DOT_NA)

    def set_motors_available(self, available: bool) -> None:
        for key in [k for k in self._on_btns if k.startswith("motor_")]:
            self.set_device_available(key, available)

    def set_device_active(self, key: str, active: bool) -> None:
        if key in self._dots:
            self._dots[key].setStyleSheet(_DOT_ON if active else _DOT_OFF)

    def clean_up(self) -> None:
        pass

    def retranslateUi(self) -> None:
        self._page_title.setText(self.tr("Devices"))
        for widget, source in self._static_text_widgets:
            if isinstance(widget, QGroupBox):
                widget.setTitle(self.tr(source))
            else:
                widget.setText(self.tr(source))
        for key, heading in self._device_headings.items():
            heading.setText(self._display_name(key, self._device_labels.get(key, key)))
            self._device_hints[key].setText(self._device_hint(key))
        for key, button in self._nav_buttons.items():
            label = self._display_name(key, self._device_labels.get(key, key))
            if key == "physical_control_buttons":
                label = self.tr("Physical control\n     buttons")
            button.setText(f"●  {label}")

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)
