from typing import Tuple, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton

from src.plugin.settings.settings_view.settings_view import SettingsView
from src.plugin.camera_settings.view.camera_settings_view import CameraSettingsView
from src.plugin.camera_settings.view.camera_settings_schema import (
    CORE_GROUP,
    CONTOUR_GROUP,
    PREPROCESSING_GROUP,
    CALIBRATION_GROUP,
    BRIGHTNESS_GROUP,
    ARUCO_GROUP,
)


def camera_tab_factory(mapper: Callable, parent=None) -> Tuple[CameraSettingsView, SettingsView]:
    settings_view = SettingsView(
        component_name="CameraSettings",
        mapper=mapper,
        parent=parent,
    )
    settings_view.add_tab("Core",        [CORE_GROUP])
    settings_view.add_tab("Detection",   [CONTOUR_GROUP, PREPROCESSING_GROUP])
    settings_view.add_tab("Calibration", [CALIBRATION_GROUP])

    # Brightness tab — schema fields + "Set on Preview" toggle button
    brightness_btn = QPushButton("Set Brightness Area on Preview")
    brightness_btn.setCheckable(True)
    brightness_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    # brightness_btn.setStyleSheet(_SET_AREA_BTN_STYLE)
    settings_view.add_tab("Brightness", [BRIGHTNESS_GROUP], footer=brightness_btn)

    settings_view.add_tab("ArUco", [ARUCO_GROUP])

    view = CameraSettingsView(settings_view)

    # Wire the brightness area button → preview label (internal to the factory)
    def _on_brightness_btn_toggled(checked: bool) -> None:
        if view.preview_label:
            view.preview_label.set_active_area("brightness_area" if checked else None)
        # Deselect any area buttons in controls that might be active
        if not checked:
            view.controls.set_active_area("")

    brightness_btn.toggled.connect(_on_brightness_btn_toggled)

    # When a work area is selected via controls, deselect brightness button
    def _on_controls_area_changed(name: str) -> None:
        brightness_btn.blockSignals(True)
        brightness_btn.setChecked(False)
        brightness_btn.blockSignals(False)

    view.controls.active_area_changed.connect(_on_controls_area_changed)

    return view, settings_view
