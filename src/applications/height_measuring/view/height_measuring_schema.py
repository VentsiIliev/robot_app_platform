from pl_gui.settings.settings_view.schema import SettingField, SettingGroup

DETECTION_GROUP = SettingGroup("Laser Detection", [
    SettingField("min_intensity",          "Min Intensity",       "double_spinbox", default=10.0, min_val=0.0,  max_val=255.0, decimals=1, step=0.5,   step_options=[0.5, 1.0, 5.0]),
    SettingField("blur_kernel_size",       "Blur Kernel Size",    "spinbox",        default=21,   min_val=1,    max_val=101,   step=2,     step_options=[2, 4, 10]),
    SettingField("gaussian_blur_sigma",    "Blur Sigma",          "double_spinbox", default=0.0,  min_val=0.0,  max_val=10.0,  decimals=2, step=0.1,   step_options=[0.1, 0.5, 1.0]),
    SettingField("default_axis",           "Detection Axis",      "combo",          default="y",  choices=["x", "y"]),
    SettingField("detection_delay_ms",     "Detection Delay",     "spinbox",        default=200,  min_val=0,    max_val=5000,  suffix=" ms", step=50,   step_options=[50, 100, 200]),
    SettingField("image_capture_delay_ms", "Capture Delay",       "spinbox",        default=10,   min_val=0,    max_val=1000,  suffix=" ms", step=5,    step_options=[5, 10, 50]),
    SettingField("detection_samples",      "Detection Samples",   "spinbox",        default=5,    min_val=1,    max_val=20,    step=1,     step_options=[1, 2, 5]),
    SettingField("max_detection_retries",  "Max Retries",         "spinbox",        default=5,    min_val=1,    max_val=20,    step=1,     step_options=[1, 2, 5]),
])

CALIBRATION_GROUP = SettingGroup("Laser Calibration", [
    SettingField("step_size_mm",             "Step Size",         "double_spinbox", default=1.0,  min_val=0.1,  max_val=50.0,  decimals=2, suffix=" mm",    step=0.1,  step_options=[0.1, 0.5, 1.0]),
    SettingField("num_iterations",           "Iterations",        "spinbox",        default=50,   min_val=5,    max_val=500,   step=5,     step_options=[5, 10, 50]),
    SettingField("calibration_velocity",     "Velocity",          "double_spinbox", default=50.0, min_val=1.0,  max_val=500.0, decimals=1, suffix=" mm/s",   step=5.0,  step_options=[5, 10, 50]),
    SettingField("calibration_acceleration", "Acceleration",      "double_spinbox", default=10.0, min_val=1.0,  max_val=500.0, decimals=1, suffix=" mm/s²",  step=5.0,  step_options=[5, 10, 50]),
    SettingField("movement_threshold",       "Move Threshold",    "double_spinbox", default=0.2,  min_val=0.0,  max_val=10.0,  decimals=2, suffix=" mm",    step=0.01, step_options=[0.01, 0.1, 1.0]),
    SettingField("movement_timeout",         "Move Timeout",      "double_spinbox", default=2.0,  min_val=0.5,  max_val=60.0,  decimals=1, suffix=" s",     step=0.5,  step_options=[0.5, 1.0, 5.0]),
    SettingField("cal_delay_ms",             "Detect Delay",      "spinbox",        default=1000, min_val=0,    max_val=10000, suffix=" ms", step=100,       step_options=[100, 500, 1000]),
    SettingField("calibration_max_attempts", "Max Attempts",      "spinbox",        default=5,    min_val=1,    max_val=20,    step=1,     step_options=[1, 2, 5]),
    SettingField("max_polynomial_degree",    "Max Poly Degree",   "spinbox",        default=6,    min_val=1,    max_val=10,    step=1,     step_options=[1, 2, 3]),
])

MEASURING_GROUP = SettingGroup("Height Measuring", [
    SettingField("measurement_velocity",     "Velocity",     "double_spinbox", default=20.0, min_val=1.0,  max_val=500.0, decimals=1, suffix=" mm/s",  step=5.0,  step_options=[5, 10, 50]),
    SettingField("measurement_acceleration", "Acceleration", "double_spinbox", default=10.0, min_val=1.0,  max_val=500.0, decimals=1, suffix=" mm/s²", step=5.0,  step_options=[5, 10, 50]),
    SettingField("measurement_threshold",    "Threshold",    "double_spinbox", default=0.25, min_val=0.0,  max_val=10.0,  decimals=2, suffix=" mm",   step=0.01, step_options=[0.01, 0.1, 1.0]),
    SettingField("measurement_timeout",      "Timeout",      "double_spinbox", default=10.0, min_val=1.0,  max_val=120.0, decimals=1, suffix=" s",    step=1.0,  step_options=[1, 5, 10]),
    SettingField("meas_delay_ms",            "Detect Delay", "spinbox",        default=500,  min_val=0,    max_val=10000, suffix=" ms", step=100,      step_options=[100, 500, 1000]),
])