import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PyQt6.QtGui import QPixmap, QColor
from PyQt6.QtWidgets import QApplication, QMainWindow

from camera_settings import CameraSettingsPlugin, ICameraSettingsService
from camera_settings.camera_settings_data import CameraSettingsData
from camera_settings.mapper import CameraSettingsMapper

# ── Sample data matching the exact JSON structure ──────────────────────────────

_SAMPLE_JSON = {
    "Index": 0, "Width": 1280, "Height": 720,
    "Skip frames": 30, "Capture position offset": -4,
    "Threshold": 150, "Threshold pickup area": 200,
    "Epsilon": 0.05, "Min contour area": 1000, "Max contour area": 10000000,
    "Contour detection": True, "Draw contours": True,
    "Preprocessing": {
        "Gaussian blur": True, "Blur kernel size": 3,
        "Threshold type": "binary_inv",
        "Dilate enabled": True, "Dilate kernel size": 3, "Dilate iterations": 2,
        "Erode enabled": True, "Erode kernel size": 3, "Erode iterations": 4,
    },
    "Calibration": {
        "Chessboard width": 32, "Chessboard height": 20,
        "Square size (mm)": 25, "Skip frames": 30,
    },
    "Brightness Control": {
        "Enable auto adjust": True, "Kp": 0.0, "Ki": 0.2, "Kd": 0.05,
        "Target brightness": 200,
        "Brightness area point 1": [851, 636], "Brightness area point 2": [1024, 650],
        "Brightness area point 3": [1026, 697], "Brightness area point 4": [862, 694],
    },
    "Aruco": {"Enable detection": False, "Dictionary": "DICT_4X4_1000", "Flip image": False},
}


class FakeCameraSettingsService(ICameraSettingsService):
    def load_settings(self) -> CameraSettingsData:
        return CameraSettingsMapper.from_flat_dict(_SAMPLE_JSON, CameraSettingsData())

    def save_settings(self, settings: CameraSettingsData) -> None:
        print(f"[service] Settings saved: {settings}")

    # Camera actions
    def set_raw_mode(self, enabled: bool) -> None:
        print(f"[service] Raw mode: {'ON' if enabled else 'OFF'}")

    def capture_image(self) -> None:
        print(f"[service] Capturing image...")

    def calibrate_camera(self) -> None:
        print(f"[service] Starting camera calibration...")

    def calibrate_robot(self) -> None:
        print(f"[service] Starting robot calibration...")


# ── Runner ─────────────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)

    plugin = CameraSettingsPlugin(service=FakeCameraSettingsService())
    plugin.load()

    # White test frame so overlay drawing is visible
    test_frame = QPixmap(1280, 720)
    test_frame.fill(QColor("white"))
    plugin.preview_label.set_frame(test_frame)

    win = QMainWindow()
    win.setWindowTitle("Camera Settings")
    win.resize(1280, 1024)
    win.setCentralWidget(plugin.widget)
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
