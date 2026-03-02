from src.plugin.settings.settings_view.schema import SettingField, SettingGroup

_ARUCO_DICTS = [
    "DICT_4X4_50",  "DICT_4X4_100",  "DICT_4X4_250",  "DICT_4X4_1000",
    "DICT_5X5_50",  "DICT_5X5_100",  "DICT_5X5_250",  "DICT_5X5_1000",
    "DICT_6X6_50",  "DICT_6X6_100",  "DICT_6X6_250",  "DICT_6X6_1000",
    "DICT_7X7_50",  "DICT_7X7_100",  "DICT_7X7_250",  "DICT_7X7_1000",
]

CORE_GROUP = SettingGroup("Core", [
    SettingField("index",                   "Camera Index",            "spinbox",
                 default=0,     min_val=0,    max_val=10,   step=1),
    SettingField("width",                   "Width",                   "spinbox",
                 default=1280,  min_val=320,  max_val=4096, step=1,   step_options=[1, 10, 100]),
    SettingField("height",                  "Height",                  "spinbox",
                 default=720,   min_val=240,  max_val=2160, step=1,   step_options=[1, 10, 100]),
    SettingField("skip_frames",             "Skip Frames",             "spinbox",
                 default=30,    min_val=0,    max_val=200,  step=1,   step_options=[1, 5, 10]),
    SettingField("capture_position_offset", "Capture Position Offset", "spinbox",
                 default=-4,    min_val=-500, max_val=500,  step=1,   step_options=[1, 5, 10]),
])

CONTOUR_GROUP = SettingGroup("Contour Detection", [
    SettingField("contour_detection",     "Enable Detection",      "toggle",
                 default=True),
    SettingField("draw_contours",         "Draw Contours",         "toggle",
                 default=True),
    SettingField("threshold",             "Threshold",             "spinbox",
                 default=150,   min_val=0,    max_val=255,        step=1,   step_options=[1, 5, 10]),
    SettingField("threshold_pickup_area", "Pickup Area Threshold", "spinbox",
                 default=200,   min_val=0,    max_val=255,        step=1,   step_options=[1, 5, 10]),
    SettingField("epsilon",               "Epsilon",               "double_spinbox",
                 default=0.05,  min_val=0.0,  max_val=10.0,       step=0.001, decimals=3,
                 step_options=[0.001, 0.01, 0.1]),
    SettingField("min_contour_area",      "Min Contour Area",      "double_spinbox",
                 default=1000.0, min_val=0.0, max_val=1_000_000.0, step=100, decimals=1,
                 step_options=[100, 1000, 10000]),
    SettingField("max_contour_area",      "Max Contour Area",      "double_spinbox",
                 default=10_000_000.0, min_val=0.0, max_val=100_000_000.0, step=10000, decimals=1,
                 step_options=[10000, 100000, 1000000]),
])

PREPROCESSING_GROUP = SettingGroup("Preprocessing", [
    SettingField("gaussian_blur",      "Gaussian Blur",    "toggle",  default=True),
    SettingField("blur_kernel_size",   "Blur Kernel Size", "spinbox",
                 default=3, min_val=1, max_val=99, step=2, step_options=[2]),
    SettingField("threshold_type",     "Threshold Type",   "combo",
                 default="binary_inv",
                 choices=["binary", "binary_inv", "trunc", "tozero", "tozero_inv"]),
    SettingField("dilate_enabled",     "Dilate",           "toggle",  default=True),
    SettingField("dilate_kernel_size", "Dilate Kernel",    "spinbox",
                 default=3, min_val=1, max_val=99, step=2, step_options=[2]),
    SettingField("dilate_iterations",  "Dilate Iterations","spinbox",
                 default=2, min_val=1, max_val=50, step=1, step_options=[1, 5]),
    SettingField("erode_enabled",      "Erode",            "toggle",  default=True),
    SettingField("erode_kernel_size",  "Erode Kernel",     "spinbox",
                 default=3, min_val=1, max_val=99, step=2, step_options=[2]),
    SettingField("erode_iterations",   "Erode Iterations", "spinbox",
                 default=4, min_val=1, max_val=50, step=1, step_options=[1, 5]),
])

CALIBRATION_GROUP = SettingGroup("Calibration", [
    SettingField("chessboard_width",        "Chessboard Width",  "spinbox",
                 default=32,   min_val=3,   max_val=50,   step=1),
    SettingField("chessboard_height",       "Chessboard Height", "spinbox",
                 default=20,   min_val=3,   max_val=50,   step=1),
    SettingField("square_size_mm",          "Square Size",       "double_spinbox",
                 default=25.0, min_val=1.0, max_val=200.0, step=0.5, decimals=1,
                 suffix=" mm", step_options=[0.5, 1.0, 5.0]),
    SettingField("calibration_skip_frames", "Skip Frames",       "spinbox",
                 default=30,   min_val=1,   max_val=200,  step=1, step_options=[1, 5, 10]),
])

BRIGHTNESS_GROUP = SettingGroup("Brightness Control", [
    SettingField("brightness_auto",   "Auto Adjust",      "toggle",  default=True),
    SettingField("brightness_kp",     "Kp",               "double_spinbox",
                 default=0.0,  min_val=0.0, max_val=10.0, step=0.001, decimals=3,
                 step_options=[0.001, 0.01, 0.1]),
    SettingField("brightness_ki",     "Ki",               "double_spinbox",
                 default=0.2,  min_val=0.0, max_val=10.0, step=0.001, decimals=3,
                 step_options=[0.001, 0.01, 0.1]),
    SettingField("brightness_kd",     "Kd",               "double_spinbox",
                 default=0.05, min_val=0.0, max_val=10.0, step=0.001, decimals=3,
                 step_options=[0.001, 0.01, 0.1]),
    SettingField("target_brightness", "Target Brightness","double_spinbox",
                 default=200.0, min_val=0.0, max_val=255.0, step=1.0, decimals=1,
                 step_options=[1, 5, 10]),
])

ARUCO_GROUP = SettingGroup("ArUco Detection", [
    SettingField("aruco_enabled",    "Enable Detection", "toggle",  default=False),
    SettingField("aruco_dictionary", "Dictionary",       "combo",
                 default="DICT_4X4_1000", choices=_ARUCO_DICTS),
    SettingField("aruco_flip_image", "Flip Image",       "toggle",  default=False),
])
