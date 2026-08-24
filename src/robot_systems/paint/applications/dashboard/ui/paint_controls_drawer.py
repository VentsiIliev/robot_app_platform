from __future__ import annotations

from PyQt6.QtCore import QCoreApplication, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pl_gui.shell.ui.icon_loader import load_icon
from pl_gui.settings.settings_view.styles import (
    ACTION_BTN_STYLE,
    GHOST_BTN_STYLE,
    GROUP_STYLE,
    LABEL_STYLE,
)

class PaintControlsDrawer(QWidget):
    """Data-driven manual controls hosted by the dashboard drawer."""

    cable_relief_requested = pyqtSignal()
    device_toggle_requested = pyqtSignal(str, bool)
    application_shortcut_requested = pyqtSignal(str)

    def __init__(
        self,
        toggle_configs: list,
        *,
        show_manual_controls: bool = True,
        show_shortcuts: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._configs = list(toggle_configs)
        self._states = {item.device_id: False for item in self._configs}
        self._buttons: dict[str, QPushButton] = {}
        self._shortcuts = []
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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

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
        self._devices_box.setVisible(show_manual_controls)
        layout.addWidget(self._devices_box)

        self._shortcuts_box = QGroupBox()
        self._shortcuts_box.setStyleSheet(GROUP_STYLE)
        self._shortcuts_layout = QVBoxLayout(self._shortcuts_box)
        self._shortcuts_layout.setSpacing(8)
        self._shortcuts_box.setVisible(show_shortcuts)
        layout.addWidget(self._shortcuts_box)
        layout.addStretch(1)
        self._scroll.setWidget(content_widget)
        root.addWidget(self._scroll, 1)
        self.retranslateUi()

    def _on_device_toggle(self, checked: bool) -> None:
        button = self.sender()
        device_id = str(button.property("device_id"))
        self.device_toggle_requested.emit(device_id, checked)

    def _on_cable_relief(self) -> None:
        self.cable_relief_requested.emit()

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
        self._relief_button.setText(self.tr("Relieve Cable (Unwind J6)"))
        self._shortcuts_box.setTitle(self.tr("Application Shortcuts"))
        for item in self._configs:
            self._render_device_button(item.device_id)
        self._render_shortcuts()

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
