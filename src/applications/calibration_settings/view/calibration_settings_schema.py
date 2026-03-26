from pl_gui.settings.settings_view.schema import SettingField, SettingGroup
from src.applications.height_measuring.view.height_measuring_schema import (
    CALIBRATION_GROUP as LASER_CALIBRATION_GROUP,
)
from src.applications.height_measuring.view.height_measuring_schema import (
    DETECTION_GROUP as LASER_DETECTION_GROUP,
)
from src.applications.height_measuring.view.height_measuring_schema import (
    MEASURING_GROUP as HEIGHT_MAPPING_GROUP,
)
from src.applications.robot_settings.view.robot_settings_schema import (
    CALIBRATION_ADAPTIVE_GROUP,
    CALIBRATION_AXIS_MAPPING_GROUP,
    CALIBRATION_CAMERA_TCP_GROUP,
    CALIBRATION_MARKER_GROUP,
)

VISION_CALIBRATION_GROUP = SettingGroup("Camera Calibration", [
    SettingField("calib_vision_chessboard_width", "Chessboard Width", "spinbox",
                 default=32, min_val=3, max_val=50, step=1),
    SettingField("calib_vision_chessboard_height", "Chessboard Height", "spinbox",
                 default=20, min_val=3, max_val=50, step=1),
    SettingField("calib_vision_square_size_mm", "Square Size", "double_spinbox",
                 default=25.0, min_val=1.0, max_val=200.0, step=0.5, decimals=1,
                 suffix=" mm", step_options=[0.5, 1.0, 5.0]),
    SettingField("calib_vision_skip_frames", "Skip Frames", "spinbox",
                 default=30, min_val=1, max_val=200, step=1, step_options=[1, 5, 10]),
])

__all__ = [
    "VISION_CALIBRATION_GROUP",
    "CALIBRATION_ADAPTIVE_GROUP",
    "CALIBRATION_MARKER_GROUP",
    "CALIBRATION_AXIS_MAPPING_GROUP",
    "CALIBRATION_CAMERA_TCP_GROUP",
    "LASER_DETECTION_GROUP",
    "LASER_CALIBRATION_GROUP",
    "HEIGHT_MAPPING_GROUP",
]
