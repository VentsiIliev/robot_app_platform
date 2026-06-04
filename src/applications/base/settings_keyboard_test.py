import sys

from PyQt6.QtWidgets import QApplication, QMainWindow

from pl_gui.settings.settings_view.schema import SettingField, SettingGroup
from src.applications.base.keyboard_settings_view import KeyboardSettingsView


def build_keyboard_settings_view() -> KeyboardSettingsView:
    connection = SettingGroup(
        "Connection",
        [
            SettingField("host", "Host", "line_edit", default="192.168.0.10"),
            SettingField("port", "Port", "spinbox", default=502, min_val=1, max_val=65535),
            SettingField("device_name", "Device name", "line_edit", default="Robot Controller"),
            SettingField("timeout", "Timeout", "double_spinbox", default=2.5, min_val=0.1, max_val=30.0, step=0.1, decimals=1, suffix=" s"),
        ],
    )
    motion = SettingGroup(
        "Motion",
        [
            SettingField("velocity", "Velocity", "double_spinbox", default=120.0, min_val=0.0, max_val=500.0, step=1.0, decimals=1, suffix=" mm/s"),
            SettingField("acceleration", "Acceleration", "double_spinbox", default=80.0, min_val=0.0, max_val=500.0, step=1.0, decimals=1, suffix=" mm/s2"),
            SettingField("passes", "Passes", "spinbox", default=3, min_val=1, max_val=20),
            SettingField("comment", "Comment", "line_edit", default="Tap lower fields first"),
        ],
    )
    lower_fields = SettingGroup(
        "Lower Fields",
        [
            SettingField(f"field_{index}", f"Field {index}", "line_edit", default=f"value {index}")
            for index in range(1, 13)
        ],
    )

    diagnostics = SettingGroup(
        "Diagnostics",
        [
            SettingField("operator", "Operator", "line_edit", default="test user"),
            SettingField("batch", "Batch", "line_edit", default="A-001"),
            SettingField("sample_count", "Samples", "spinbox", default=5, min_val=1, max_val=100),
            SettingField("note", "Note", "line_edit", default="Collapsed sections test"),
        ],
    )

    view = KeyboardSettingsView(component_name="KeyboardSettingsExample")
    view.add_tab("Core", [connection, motion])
    view.add_tab("Long Form", [lower_fields, diagnostics])
    return view


class SettingsKeyboardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SettingsView Virtual Keyboard Test")
        self.resize(900, 700)
        self.setCentralWidget(build_keyboard_settings_view())


def main() -> None:
    app = QApplication(sys.argv)
    window = SettingsKeyboardWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
