from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from src.applications.base.collapsible_settings_view import CollapsibleGroup
from src.applications.base.app_styles import (
    APP_CARD_STYLE,
    APP_SECONDARY_BUTTON_STYLE,
    divider,
    section_hint,
    section_label,
)
from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton


class _BaseCalibrationTab(QWidget):
    def __init__(self, title: str, hint: str, parent=None):
        super().__init__(parent)
        self._settings_groups: list[CollapsibleGroup] = []
        self._save_button: QPushButton | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._card = QWidget()
        self._card.setStyleSheet(APP_CARD_STYLE)
        self._card_layout = QVBoxLayout(self._card)
        self._card_layout.setContentsMargins(16, 12, 16, 16)
        self._card_layout.setSpacing(10)
        self._card_layout.addWidget(section_label(title))
        self._card_layout.addWidget(section_hint(hint))

        layout.addWidget(self._card)
        layout.addStretch(1)

    def add_widget(self, widget: QWidget) -> None:
        self._card_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._card_layout.addLayout(layout)

    def add_divider(self) -> None:
        self._card_layout.addWidget(divider())

    def add_settings_groups(self, schemas: list) -> None:
        for schema in schemas:
            group = CollapsibleGroup(schema)
            self._settings_groups.append(group)
            self._card_layout.addWidget(group)

    def add_save_button(self) -> QPushButton:
        button = MaterialButton("Save Phase Settings")
        button.setStyleSheet(APP_SECONDARY_BUTTON_STYLE)
        self._save_button = button
        self._card_layout.addWidget(button)
        return button

    def set_settings_values(self, flat: dict) -> None:
        for group in self._settings_groups:
            group.set_values(flat)

    def get_settings_values(self) -> dict:
        values: dict = {}
        for group in self._settings_groups:
            values.update(group.get_values())
        return values


class SystemCalibrationTab(_BaseCalibrationTab):
    def __init__(self, sequence_btn: QWidget, stop_btn: QWidget, parent=None):
        super().__init__(
            "System Calibration",
            "Use the guided sequence for the normal workflow, or stop the active task from here.",
            parent=parent,
        )
        self.add_widget(sequence_btn)
        self.add_divider()
        self.add_widget(stop_btn)


class CameraCalibrationTab(_BaseCalibrationTab):
    def __init__(
        self,
        capture_btn: QWidget,
        crosshair_btn: QWidget,
        magnifier_btn: QWidget,
        calibrate_camera_btn: QWidget,
        auto_capture_widget: QWidget | None,
        settings_schemas: list,
        parent=None,
    ):
        super().__init__(
            "Camera Calibration",
            "Capture a fresh image, use overlays while framing the board, then run camera calibration.",
            parent=parent,
        )
        self.add_widget(capture_btn)
        overlay_row = QHBoxLayout()
        overlay_row.setSpacing(8)
        overlay_row.addWidget(crosshair_btn)
        overlay_row.addWidget(magnifier_btn)
        self.add_layout(overlay_row)
        self.add_divider()
        self.add_widget(calibrate_camera_btn)
        if auto_capture_widget is not None:
            self.add_divider()
            self.add_widget(auto_capture_widget)
        self.add_settings_groups(settings_schemas)
        self.add_save_button()


class RobotCalibrationTab(_BaseCalibrationTab):
    def __init__(
        self,
        calibrate_robot_btn: QWidget,
        calibrate_tcp_btn: QWidget,
        test_btn: QWidget,
        settings_schemas: list,
        parent=None,
    ):
        super().__init__(
            "Robot Calibration",
            "Run robot calibration, then use TCP offset and test validation once calibration data exists.",
            parent=parent,
        )
        self.add_widget(calibrate_robot_btn)
        self.add_widget(calibrate_tcp_btn)
        self.add_divider()
        self.add_widget(test_btn)
        self.add_settings_groups(settings_schemas)
        self.add_save_button()


class LaserCalibrationTab(_BaseCalibrationTab):
    def __init__(
        self,
        calibrate_laser_btn: QWidget,
        detect_laser_btn: QWidget,
        settings_schemas: list,
        parent=None,
    ):
        super().__init__(
            "Laser Calibration",
            "Calibrate the laser model or run a single detection pass for validation and debugging.",
            parent=parent,
        )
        self.add_widget(calibrate_laser_btn)
        self.add_widget(detect_laser_btn)
        self.add_settings_groups(settings_schemas)
        self.add_save_button()


class HeightMappingTab(_BaseCalibrationTab):
    def __init__(
        self,
        verify_saved_model_btn: QWidget,
        settings_schemas: list,
        height_mapping_content: QWidget | None = None,
        parent=None,
    ):
        super().__init__(
            "Height Mapping",
            "Define the mapping area on the preview, generate the area grid, and verify the saved model here.",
            parent=parent,
        )
        self._height_mapping_content: QWidget | None = None
        self._height_mapping_divider: QWidget | None = None
        if height_mapping_content is not None:
            self.set_height_mapping_content(height_mapping_content)
        self.add_widget(verify_saved_model_btn)
        self.add_settings_groups(settings_schemas)
        self.add_save_button()

    def set_height_mapping_content(self, widget: QWidget) -> None:
        if self._height_mapping_content is not None:
            self._card_layout.removeWidget(self._height_mapping_content)
            self._height_mapping_content.setParent(None)
        if self._height_mapping_divider is not None:
            self._card_layout.removeWidget(self._height_mapping_divider)
            self._height_mapping_divider.setParent(None)
        self._height_mapping_content = widget
        self._height_mapping_divider = divider()
        self._card_layout.insertWidget(2, widget)
        self._card_layout.insertWidget(3, self._height_mapping_divider)
