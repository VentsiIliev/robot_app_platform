from PyQt6.QtCore import pyqtSignal, QEvent
from PyQt6.QtWidgets import QVBoxLayout

from src.applications.base.i_application_view import IApplicationView
from src.shared_contracts.declarations import MovementGroupDefinition
from src.applications.robot_settings.model.mapper import RobotSettingsMapper
from src.applications.robot_settings.view.collapsible_settings_view import CollapsibleSettingsView
from src.applications.robot_settings.view.movement_groups_tab import MovementGroupsTab
from src.applications.robot_settings.view.targeting_definitions_tab import TargetingDefinitionsTab

from src.applications.robot_settings.view.robot_settings_schema import (
    CALIBRATION_ADAPTIVE_GROUP, CALIBRATION_AXIS_MAPPING_GROUP, CALIBRATION_CAMERA_TCP_GROUP, CALIBRATION_MARKER_GROUP,
    GLOBAL_MOTION_GROUP, OFFSET_DIRECTION_GROUP, ROBOT_INFO_GROUP,
    SAFETY_LIMITS_GROUP, TCP_STEP_GROUP,
)



class RobotSettingsView(IApplicationView):
    """View — pure Qt widget. No services, no business logic."""
    SHOW_JOG_WIDGET = True
    JOG_LIVE_POSITION_ENABLED = True
    JOG_FRAME_SELECTOR_ENABLED = True

    save_requested = pyqtSignal(dict)
    value_changed = pyqtSignal(str, object, str)
    movement_changed = pyqtSignal(str, object)
    targeting_changed = pyqtSignal()
    remove_group_requested = pyqtSignal(str)
    set_current_requested = pyqtSignal(str)
    move_to_requested = pyqtSignal(str, object)  # group_name, point_str or None
    execute_requested  = pyqtSignal(str)   # group_name

    def __init__(self, movement_group_definitions: list[MovementGroupDefinition] | None = None, parent=None):
        self._movement_group_definitions = list(movement_group_definitions or [])
        super().__init__("RobotSettings", parent)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._movement_tab  = MovementGroupsTab()
        self._targeting_tab = TargetingDefinitionsTab()
        self._settings_view = CollapsibleSettingsView(
            component_name="RobotSettings",
            mapper=RobotSettingsMapper.to_flat_dict,
        )
        self._settings_view.add_tab("General",             [ROBOT_INFO_GROUP, GLOBAL_MOTION_GROUP, TCP_STEP_GROUP, OFFSET_DIRECTION_GROUP])
        self._settings_view.add_tab("Safety",              [SAFETY_LIMITS_GROUP])
        self._settings_view.add_raw_tab("Movement Groups", self._movement_tab)
        self._settings_view.add_raw_tab("Targeting", self._targeting_tab)
        self._settings_view.add_tab(
            "Calibration",
            [
                CALIBRATION_ADAPTIVE_GROUP,
                CALIBRATION_MARKER_GROUP,
                CALIBRATION_AXIS_MAPPING_GROUP,
                CALIBRATION_CAMERA_TCP_GROUP,
            ],
        )
        layout.addWidget(self._settings_view)

        self._settings_view.save_requested.connect(self._on_inner_save)
        self._settings_view.value_changed_signal.connect(self._on_inner_value_changed)
        self._movement_tab.values_changed.connect(self._on_inner_movement_changed)
        self._movement_tab.remove_group_requested.connect(self.remove_group_requested)
        self._movement_tab.set_current_requested.connect(self.set_current_requested)
        self._movement_tab.move_to_requested.connect(self.move_to_requested)
        self._movement_tab.execute_trajectory_requested.connect(self.execute_requested)
        self._targeting_tab.definitions_changed.connect(self.targeting_changed)

    def _on_inner_save(self, values: dict) -> None:
        self.save_requested.emit(values)

    def _on_inner_value_changed(self, key: str, value, component: str) -> None:
        self.value_changed.emit(key, value, component)

    def _on_inner_movement_changed(self, key: str, value) -> None:
        self.movement_changed.emit(key, value)

    def load_config(self, flat: dict) -> None:
        self._settings_view.set_values(flat)

    def load_movement_groups(
        self,
        groups: dict,
        definitions: list[MovementGroupDefinition] | None = None,
    ) -> None:
        self._movement_tab.load(groups, definitions=definitions or self._movement_group_definitions)

    def load_targeting_definitions(self, data: dict | None) -> None:
        self._targeting_tab.load(data)

    def get_values(self) -> dict:
        return self._settings_view.get_values()

    def get_movement_groups(self) -> dict:
        return self._movement_tab.get_values()

    def get_targeting_definitions(self) -> dict:
        return self._targeting_tab.get_values()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.on_language_changed()
        super().changeEvent(event)

    def add_movement_group(self, name: str, defn, group) -> None:
        self._movement_tab.add_group(name, defn, group)

    def remove_movement_group(self, name: str) -> None:
        self._movement_tab.remove_group(name)

    def get_group_widget(self, group_name: str):
        return self._movement_tab.get_widget(group_name)

    def _on_move_to(self, group_name: str, point_str) -> None:
        if point_str is None:
            # single-position group — use stored group position
            fn = lambda: self._model.move_to_group(group_name)
            label = f"Move To — {group_name}"
        else:
            # multi-position group — move to the selected point
            fn = lambda: self._model.move_to_point(group_name, point_str)
            label = f"Move To point in {group_name}"
        self._run_blocking(fn=fn, label=label)

    def clean_up(self) -> None:
        pass
