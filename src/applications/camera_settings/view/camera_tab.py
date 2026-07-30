from typing import Callable, Tuple

from pl_gui.settings.settings_view.settings_view import SettingsView
from src.applications.base.collapsible_settings_view import CollapsibleGroup
from src.applications.base.keyboard_settings_view import (
    KeyboardSettingsView,
    build_with_keyboard_setting_handlers,
)
from src.applications.camera_settings.view.camera_settings_view import CameraSettingsView
from src.applications.camera_settings.view.camera_settings_schema import (
    ARUCO_GROUP,
    BRIGHTNESS_GROUP,
    CONTOUR_GROUP,
    CORE_GROUP,
    PREPROCESSING_GROUP,
)


def _keyboard_collapsible_group(schema) -> CollapsibleGroup:
    group_holder: list[CollapsibleGroup] = []
    build_with_keyboard_setting_handlers(
        lambda: group_holder.append(CollapsibleGroup(schema))
    )
    return group_holder[0]


def camera_tab_factory(
    mapper: Callable,
    parent=None,
) -> Tuple[CameraSettingsView, SettingsView]:
    settings_view = KeyboardSettingsView(
        component_name="CameraSettings",
        mapper=mapper,
        parent=parent,
    )
    settings_view.add_tab("Core", [CORE_GROUP])
    settings_view.add_tab("Detection", [CONTOUR_GROUP, PREPROCESSING_GROUP])
    settings_view.add_tab("ArUco", [ARUCO_GROUP])

    brightness_group_widget = _keyboard_collapsible_group(BRIGHTNESS_GROUP)
    brightness_group_widget.value_changed.connect(settings_view._on_group_value_changed)
    settings_view._groups.append(brightness_group_widget)
    settings_view.add_raw_tab("Brightness", brightness_group_widget)
    view = CameraSettingsView(settings_view)
    return view, settings_view
