from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout

from src.applications.base.keyboard_settings_view import KeyboardSettingsView
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
from src.applications.calibration_settings.view.workobject_calibration_tab import (
    WorkObjectCalibrationTab,
)


class CalibrationSettingsView(IApplicationView):
    workobject_capture_requested = pyqtSignal(str)
    workobject_solve_requested = pyqtSignal(int, str)
    workobject_save_requested = pyqtSignal(int, str)

    save_requested = None

    def __init__(self, parent=None):
        self._workobject_tab = None
        super().__init__("CalibrationSettings", parent)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.settings_view = KeyboardSettingsView(component_name="CalibrationSettings")
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
        self._workobject_tab = WorkObjectCalibrationTab()
        self._workobject_tab.capture_requested.connect(self.workobject_capture_requested)
        self._workobject_tab.solve_requested.connect(self.workobject_solve_requested)
        self._workobject_tab.save_requested.connect(self.workobject_save_requested)
        self.settings_view._tabs.addTab(self._workobject_tab, "WorkObject")
        layout.addWidget(self.settings_view)

        self.save_requested = self.settings_view.save_requested

    def set_workobject_capture(self, point: str, pose) -> None:
        if self._workobject_tab is not None:
            self._workobject_tab.set_capture_result(point, pose)

    def set_workobject_result(self, ok: bool, message: str, payload: dict | None = None) -> None:
        if self._workobject_tab is not None:
            self._workobject_tab.set_result(ok, message, payload)
