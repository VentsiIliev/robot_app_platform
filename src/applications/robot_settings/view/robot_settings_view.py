from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from src.applications.base.i_application_view import IApplicationView
from src.shared_contracts.declarations import MovementGroupDefinition
from src.applications.base.keyboard_settings_view import KeyboardSettingsView
from src.applications.robot_settings.model.mapper import RobotSettingsMapper
from src.applications.robot_settings.view.movement_groups_tab import MovementGroupsTab
from src.applications.robot_settings.view.targeting_definitions_tab import TargetingDefinitionsTab
from pl_gui.settings.settings_view.styles import TOUCH_SCROLL_AREA_STYLE

from src.applications.robot_settings.view.robot_settings_schema import (
    CALIBRATION_ADAPTIVE_GROUP, CALIBRATION_AXIS_MAPPING_GROUP, CALIBRATION_CAMERA_TCP_GROUP, CALIBRATION_MARKER_GROUP,
    GLOBAL_MOTION_GROUP, OFFSET_DIRECTION_GROUP, ROBOT_INFO_GROUP,
    SAFETY_LIMITS_GROUP, TCP_STEP_GROUP,
)


_SHOW_LEGACY_CALIBRATION_TAB = False


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
        self._cached_flat_config: dict = {}
        self._cached_movement_groups: dict = {}
        self._cached_targeting_definitions: dict | None = None
        self._movement_tab = None
        self._targeting_tab = None
        self._settings_view = None
        super().__init__("RobotSettings", parent)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._settings_view = KeyboardSettingsView(
            component_name="RobotSettings",
            mapper=RobotSettingsMapper.to_flat_dict,
        )
        self._settings_view.add_tab("General",             [ROBOT_INFO_GROUP, GLOBAL_MOTION_GROUP, TCP_STEP_GROUP, OFFSET_DIRECTION_GROUP])
        self._settings_view.add_tab("Safety", [SAFETY_LIMITS_GROUP])
        self._add_lazy_raw_tab("Movement Groups")
        self._add_lazy_raw_tab("Targeting")
        if _SHOW_LEGACY_CALIBRATION_TAB:
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
        self._settings_view._tabs.currentChanged.connect(self._on_tab_changed)

    def _add_lazy_raw_tab(self, title: str) -> None:
        self._settings_view._tabs.addTab(self._make_placeholder(title), title)

    @staticmethod
    def _make_placeholder(title: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(24, 24, 24, 24)
        label = QLabel(f"{title} will load when opened.")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addStretch()
        return widget

    def _on_tab_changed(self, index: int) -> None:
        if index == 2 and self._movement_tab is None:
            self._build_movement_groups_tab()
        elif index == 3 and self._targeting_tab is None:
            self._build_targeting_tab()

    def _build_movement_groups_tab(self) -> None:
        self._movement_tab = MovementGroupsTab()
        self._movement_tab.values_changed.connect(self._on_inner_movement_changed)
        self._movement_tab.remove_group_requested.connect(self.remove_group_requested)
        self._movement_tab.set_current_requested.connect(self.set_current_requested)
        self._movement_tab.move_to_requested.connect(self.move_to_requested)
        self._movement_tab.execute_trajectory_requested.connect(self.execute_requested)
        self._movement_tab.load(
            self._cached_movement_groups,
            definitions=self._movement_group_definitions,
        )
        self._replace_tab_with_widget(index=2, title="Movement Groups", widget=self._movement_tab)

    def _build_targeting_tab(self) -> None:
        self._targeting_tab = TargetingDefinitionsTab()
        self._targeting_tab.definitions_changed.connect(self.targeting_changed)
        self._targeting_tab.load(self._cached_targeting_definitions)
        self._replace_tab_with_widget(index=3, title="Targeting", widget=self._targeting_tab)

    def _replace_tab_with_widget(self, index: int, title: str, widget: QWidget) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(TOUCH_SCROLL_AREA_STYLE)
        scroll.setWidget(widget)
        self._settings_view._tabs.removeTab(index)
        self._settings_view._tabs.insertTab(index, scroll, title)
        self._settings_view._tabs.setCurrentIndex(index)

    def _on_inner_save(self, values: dict) -> None:
        self.save_requested.emit(values)

    def _on_inner_value_changed(self, key: str, value, component: str) -> None:
        self.value_changed.emit(key, value, component)

    def _on_inner_movement_changed(self, key: str, value) -> None:
        self.movement_changed.emit(key, value)

    def load_config(self, flat: dict) -> None:
        self._cached_flat_config = dict(flat)
        self._settings_view.set_values(flat)

    def update_robot_config(self, config) -> None:
        flat = RobotSettingsMapper.to_flat_dict(config)
        self._cached_flat_config.update(flat)
        self._settings_view.set_values(flat)

    def load_movement_groups(
        self,
        groups: dict,
        definitions: list[MovementGroupDefinition] | None = None,
    ) -> None:
        self._cached_movement_groups = dict(groups)
        self._movement_group_definitions = list(definitions or self._movement_group_definitions)
        if self._movement_tab is not None:
            self._movement_tab.load(
                self._cached_movement_groups,
                definitions=self._movement_group_definitions,
            )

    def load_targeting_definitions(self, data: dict | None) -> None:
        self._cached_targeting_definitions = dict(data) if data is not None else None
        if self._targeting_tab is not None:
            self._targeting_tab.load(self._cached_targeting_definitions)

    def get_values(self) -> dict:
        values = dict(self._cached_flat_config)
        values.update(self._settings_view.get_values())
        return values

    def get_movement_groups(self) -> dict:
        if self._movement_tab is None:
            return dict(self._cached_movement_groups)
        return self._movement_tab.get_values()

    def get_targeting_definitions(self) -> dict:
        if self._targeting_tab is None:
            return dict(self._cached_targeting_definitions or {})
        return self._targeting_tab.get_values()

    def add_movement_group(self, name: str, defn, group) -> None:
        self._cached_movement_groups[name] = group
        if self._movement_tab is not None:
            self._movement_tab.add_group(name, defn, group)

    def remove_movement_group(self, name: str) -> None:
        self._cached_movement_groups.pop(name, None)
        if self._movement_tab is not None:
            self._movement_tab.remove_group(name)

    def get_group_widget(self, group_name: str):
        if self._movement_tab is None:
            return None
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
