from typing import List

from PyQt6.QtWidgets import (
    QWidget, QTabWidget, QVBoxLayout, QScrollArea, QPushButton
)
from PyQt6.QtCore import pyqtSignal, Qt

from src.settings.settings_view.schema import SettingGroup
from src.settings.settings_view.group_widget import GenericSettingGroup
from src.settings.settings_view.styles import TAB_WIDGET_STYLE, SAVE_BUTTON_STYLE, BG_COLOR


class SettingsView(QWidget):
    """
    Schema-driven settings UI — touch-friendly.

    Usage:
        view = SettingsView("RobotSettings")
        view.add_tab("General", [ROBOT_INFO_GROUP, GLOBAL_MOTION_GROUP])
        view.add_tab("Safety",  [SAFETY_LIMITS_GROUP])
        view.set_values(flat_dict)
        view.value_changed_signal.connect(handler)
        view.save_requested.connect(on_save)
    """

    value_changed_signal = pyqtSignal(str, object, str)  # key, value, component_name
    save_requested = pyqtSignal(dict)                     # emits current values on Save

    def __init__(self, component_name: str = "SettingsView", mapper=None, parent: QWidget = None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        self._component_name = component_name
        self._mapper = mapper
        self._groups: List[GenericSettingGroup] = []

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(TAB_WIDGET_STYLE)

        self._save_btn = QPushButton("Save")
        self._save_btn.setStyleSheet(SAVE_BUTTON_STYLE)
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(lambda: self.save_requested.emit(self.get_values()))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(self._tabs)
        layout.addWidget(self._save_btn)

    def add_tab(self, title: str, groups: List[SettingGroup]) -> None:
        """Build a tab from a list of SettingGroup schemas and add it."""
        content = QWidget()
        content.setStyleSheet(f"background: {BG_COLOR};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(16)

        for schema in groups:
            widget = GenericSettingGroup(schema)
            widget.value_changed.connect(
                lambda k, v: self.value_changed_signal.emit(k, v, self._component_name)
            )
            self._groups.append(widget)
            content_layout.addWidget(widget)

        content_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setWidget(content)

        self._tabs.addTab(scroll, title)

    def add_raw_tab(self, title: str, widget: QWidget) -> None:
        """Add a tab containing an arbitrary widget (not schema-driven)."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setWidget(widget)
        self._tabs.addTab(scroll, title)

    def load(self, model) -> None:
        """Convert model → flat dict via mapper, then push into widgets."""
        if self._mapper is None:
            raise RuntimeError("No mapper configured on this SettingsView.")
        self.set_values(self._mapper(model))

    def set_values(self, flat: dict) -> None:
        for group in self._groups:
            group.set_values(flat)

    def get_values(self) -> dict:
        result = {}
        for group in self._groups:
            result.update(group.get_values())
        return result
