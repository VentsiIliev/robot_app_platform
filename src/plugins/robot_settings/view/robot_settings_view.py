from PyQt6.QtCore import pyqtSignal, QEvent
from PyQt6.QtWidgets import QVBoxLayout

from src.plugins.base.i_plugin_view import IPluginView
from pl_gui.settings.settings_view.settings_view import SettingsView
from src.plugins.robot_settings.model.mapper import RobotSettingsMapper
from src.plugins.robot_settings.view.movement_groups_tab import MovementGroupsTab
from src.plugins.robot_settings.view.robot_settings_schema import (
    CALIBRATION_ADAPTIVE_GROUP, CALIBRATION_MARKER_GROUP,
    GLOBAL_MOTION_GROUP, OFFSET_DIRECTION_GROUP, ROBOT_INFO_GROUP,
    SAFETY_LIMITS_GROUP, TCP_STEP_GROUP,
)


class RobotSettingsView(IPluginView):
    """View — pure Qt widget. No services, no business logic."""

    save_requested   = pyqtSignal(dict)
    value_changed    = pyqtSignal(str, object, str)
    movement_changed = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__("RobotSettings", parent)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._movement_tab  = MovementGroupsTab()
        self._settings_view = SettingsView(
            component_name="RobotSettings",
            mapper=RobotSettingsMapper.to_flat_dict,
        )
        self._settings_view.add_tab("General",             [ROBOT_INFO_GROUP, GLOBAL_MOTION_GROUP, TCP_STEP_GROUP, OFFSET_DIRECTION_GROUP])
        self._settings_view.add_tab("Safety",              [SAFETY_LIMITS_GROUP])
        self._settings_view.add_raw_tab("Movement Groups", self._movement_tab)
        self._settings_view.add_tab("Calibration",         [CALIBRATION_ADAPTIVE_GROUP, CALIBRATION_MARKER_GROUP])
        layout.addWidget(self._settings_view)

        self._settings_view.save_requested.connect(self._on_inner_save)
        self._settings_view.value_changed_signal.connect(self._on_inner_value_changed)
        self._movement_tab.values_changed.connect(self._on_inner_movement_changed)

    def _on_inner_save(self, values: dict) -> None:
        self.save_requested.emit(values)

    def _on_inner_value_changed(self, key: str, value, component: str) -> None:
        self.value_changed.emit(key, value, component)

    def _on_inner_movement_changed(self, key: str, value) -> None:
        self.movement_changed.emit(key, value)

    def load_config(self, config) -> None:
        self._settings_view.load(config)

    def load_movement_groups(self, groups: dict) -> None:
        self._movement_tab.load(groups)

    def get_values(self) -> dict:
        return self._settings_view.get_values()

    def get_movement_groups(self) -> dict:
        return self._movement_tab.get_values()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.on_language_changed()
        super().changeEvent(event)

    def clean_up(self) -> None:
        pass
