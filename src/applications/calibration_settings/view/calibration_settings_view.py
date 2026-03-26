from PyQt6.QtWidgets import QVBoxLayout

from src.applications.base.collapsible_settings_view import CollapsibleSettingsView
from src.applications.base.i_application_view import IApplicationView
from src.applications.calibration_settings.view.calibration_settings_schema import (
    CALIBRATION_ADAPTIVE_GROUP,
    CALIBRATION_AXIS_MAPPING_GROUP,
    CALIBRATION_CAMERA_TCP_GROUP,
    CALIBRATION_MARKER_GROUP,
    HEIGHT_MAPPING_GROUP,
    LASER_CALIBRATION_GROUP,
    LASER_DETECTION_GROUP,
    VISION_CALIBRATION_GROUP,
)


class CalibrationSettingsView(IApplicationView):
    save_requested = None

    def __init__(self, parent=None):
        super().__init__("CalibrationSettings", parent)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.settings_view = CollapsibleSettingsView(component_name="CalibrationSettings")
        self.settings_view.add_tab("Camera", [VISION_CALIBRATION_GROUP])
        self.settings_view.add_tab(
            "Robot",
            [
                CALIBRATION_ADAPTIVE_GROUP,
                CALIBRATION_MARKER_GROUP,
                CALIBRATION_AXIS_MAPPING_GROUP,
                CALIBRATION_CAMERA_TCP_GROUP,
            ],
        )
        self.settings_view.add_tab("Laser", [LASER_DETECTION_GROUP, LASER_CALIBRATION_GROUP])
        self.settings_view.add_tab("Height Mapping", [HEIGHT_MAPPING_GROUP])
        layout.addWidget(self.settings_view)

        self.save_requested = self.settings_view.save_requested
