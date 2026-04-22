from pl_gui.settings.settings_view.schema import SettingField, SettingGroup

ROBOT_INFO_GROUP = SettingGroup("Robot Information", [
    SettingField("robot_ip",     "IP Address",   "line_edit",      default="192.168.58.2"),
    SettingField("robot_tool",   "Tool Number",  "spinbox",        default=0,   min_val=0,     max_val=10,   step=1,   step_options=[1]),
    SettingField("robot_user",   "User Number",  "spinbox",        default=0,   min_val=0,     max_val=10,   step=1,   step_options=[1]),
    SettingField("camera_to_tcp_x_offset",  "Camera To TCP X Offset",  "double_spinbox", default=0.0, min_val=-1000, max_val=1000, decimals=3, suffix=" mm", step=0.001, step_options=[0.001, 0.01, 0.1, 1]),
    SettingField("camera_to_tcp_y_offset",  "Camera To TCP Y Offset",  "double_spinbox", default=0.0, min_val=-1000, max_val=1000, decimals=3, suffix=" mm", step=0.001, step_options=[0.001, 0.01, 0.1, 1]),
    SettingField("camera_z_shift_x_per_mm_px", "Camera Z Shift X / mm", "double_spinbox", default=0.0, min_val=-1000, max_val=1000, decimals=6, suffix=" px/mm", step=0.0001, step_options=[0.0001, 0.001, 0.01, 0.1]),
    SettingField("camera_z_shift_y_per_mm_px", "Camera Z Shift Y / mm", "double_spinbox", default=0.0, min_val=-1000, max_val=1000, decimals=6, suffix=" px/mm", step=0.0001, step_options=[0.0001, 0.001, 0.01, 0.1]),
    SettingField("camera_z_shift_x_per_mm", "Camera Z Shift X / mm",   "double_spinbox", default=0.0, min_val=-1000, max_val=1000, decimals=6, suffix=" mm/mm", step=0.0001, step_options=[0.0001, 0.001, 0.01, 0.1]),
    SettingField("camera_z_shift_y_per_mm", "Camera Z Shift Y / mm",   "double_spinbox", default=0.0, min_val=-1000, max_val=1000, decimals=6, suffix=" mm/mm", step=0.0001, step_options=[0.0001, 0.001, 0.01, 0.1]),
])

GLOBAL_MOTION_GROUP = SettingGroup("Global Motion Settings", [
    SettingField("global_velocity",     "Global Velocity",        "spinbox", default=100, min_val=1, max_val=1000, suffix=" mm/s",  step=1, step_options=[1, 5, 10, 50]),
    SettingField("global_acceleration", "Global Acceleration",    "spinbox", default=100, min_val=1, max_val=1000, suffix=" mm/s²", step=1, step_options=[1, 5, 10, 50]),
    SettingField("emergency_decel",     "Emergency Deceleration", "spinbox", default=500, min_val=1, max_val=1000, suffix=" mm/s²", step=1, step_options=[1, 5, 10, 50]),
    SettingField("max_jog_step",        "Max Jog Step",           "spinbox", default=50,  min_val=1, max_val=100,  suffix=" mm",   step=1, step_options=[1, 5, 10]),
])

TCP_STEP_GROUP = SettingGroup("TCP Step Settings", [
    SettingField("tcp_x_step_distance", "X Step Distance", "double_spinbox", default=50.0, min_val=0, max_val=200, decimals=1, suffix=" mm", step=0.1, step_options=[0.1, 1, 5, 10]),
    SettingField("tcp_x_step_offset",   "X Step Offset",   "double_spinbox", default=0.1,  min_val=0, max_val=10,  decimals=3,             step=0.001, step_options=[0.001, 0.01, 0.1]),
    SettingField("tcp_y_step_distance", "Y Step Distance", "double_spinbox", default=50.0, min_val=0, max_val=200, decimals=1, suffix=" mm", step=0.1, step_options=[0.1, 1, 5, 10]),
    SettingField("tcp_y_step_offset",   "Y Step Offset",   "double_spinbox", default=0.1,  min_val=0, max_val=10,  decimals=3,             step=0.001, step_options=[0.001, 0.01, 0.1]),
])

OFFSET_DIRECTION_GROUP = SettingGroup("Offset Direction Map", [
    SettingField("offset_pos_x", "+X Direction", "combo", default="True",  choices=["True", "False"]),
    SettingField("offset_neg_x", "-X Direction", "combo", default="True",  choices=["True", "False"]),
    SettingField("offset_pos_y", "+Y Direction", "combo", default="True",  choices=["True", "False"]),
    SettingField("offset_neg_y", "-Y Direction", "combo", default="True",  choices=["True", "False"]),
])

CALIBRATION_ADAPTIVE_GROUP = SettingGroup("Adaptive Movement", [
    SettingField("calib_min_step_mm",        "Min Step",            "double_spinbox", default=0.1,   min_val=0.0, max_val=10.0,   decimals=2, suffix=" mm", step=0.01, step_options=[0.01, 0.1, 1.0]),
    SettingField("calib_max_step_mm",        "Max Step",            "double_spinbox", default=25.0,  min_val=0.0, max_val=100.0,  decimals=1, suffix=" mm", step=0.1,  step_options=[0.1, 1.0, 5.0]),
    SettingField("calib_target_error_mm",    "Target Error",        "double_spinbox", default=0.25,  min_val=0.0, max_val=10.0,   decimals=2, suffix=" mm", step=0.01, step_options=[0.01, 0.1, 1.0]),
    SettingField("calib_max_error_ref",      "Max Error Reference", "double_spinbox", default=100.0, min_val=0.0, max_val=1000.0, decimals=1, suffix=" mm", step=1.0,  step_options=[1, 5, 10, 50]),
    SettingField("calib_k",                  "Responsiveness (k)",  "double_spinbox", default=2.0,   min_val=0.1, max_val=10.0,   decimals=1,              step=0.1,  step_options=[0.1, 0.5, 1.0]),
    SettingField("calib_derivative_scaling", "Derivative Scaling",  "double_spinbox", default=0.5,   min_val=0.0, max_val=2.0,    decimals=2,              step=0.01, step_options=[0.01, 0.1, 0.5]),
    SettingField("calib_initial_align_y_scale", "Initial Y Scale",  "double_spinbox", default=1.0,   min_val=0.5, max_val=2.0,    decimals=3,              step=0.01, step_options=[0.01, 0.05, 0.1]),
])

CALIBRATION_MARKER_GROUP = SettingGroup("Marker Detection", [
    SettingField("calib_run_height_measurement", "Measure Height",  "combo",   default="True", choices=["True", "False"]),
    SettingField("calib_z_target",              "Z Target Height",  "spinbox",      default=300,  min_val=0,   max_val=1000,  suffix=" mm",   step=1,   step_options=[1, 10, 50]),
    SettingField("calib_required_ids",          "Required IDs",     "int_list",     default="0,1,2,3,4,5,6,8", min_val=0, max_val=255),
    SettingField("calib_candidate_ids",         "Candidate IDs",    "int_list",     default="", min_val=0, max_val=999),
    SettingField("calib_min_target_separation_px", "Min Separation", "double_spinbox", default=120.0, min_val=0.0, max_val=2000.0, decimals=1, suffix=" px", step=1.0, step_options=[1, 10, 50, 100, 150]),
    SettingField("calib_travel_velocity",       "Travel Velocity",     "spinbox",      default=30,   min_val=1,   max_val=1000,  suffix=" mm/s",  step=1,   step_options=[1, 5, 10, 50]),
    SettingField("calib_travel_acceleration",   "Travel Acceleration", "spinbox",      default=10,   min_val=1,   max_val=1000,  suffix=" mm/s²", step=1,   step_options=[1, 5, 10, 50]),
    SettingField("calib_iterative_velocity",    "Iter Align Velocity", "spinbox",      default=30,   min_val=1,   max_val=1000,  suffix=" mm/s",  step=1,   step_options=[1, 5, 10, 50]),
    SettingField("calib_iterative_acceleration", "Iter Align Accel",  "spinbox",      default=10,   min_val=1,   max_val=1000,  suffix=" mm/s²", step=1,   step_options=[1, 5, 10, 50]),
    SettingField("calib_fast_iteration_wait",   "Stability Wait",   "double_spinbox", default=1.0, min_val=0.0, max_val=10.0, suffix=" s",    step=0.1, decimals=1, step_options=[0.1, 0.5, 1.0]),
])

SAFETY_LIMITS_GROUP = SettingGroup("Safety Limits", [
    SettingField("safety_x_min",  "X Min",  "spinbox", default=-500, min_val=-1000, max_val=1000, suffix=" mm", step=1, step_options=[1, 10, 50, 100]),
    SettingField("safety_x_max",  "X Max",  "spinbox", default=500,  min_val=-1000, max_val=1000, suffix=" mm", step=1, step_options=[1, 10, 50, 100]),
    SettingField("safety_y_min",  "Y Min",  "spinbox", default=-500, min_val=-1000, max_val=1000, suffix=" mm", step=1, step_options=[1, 10, 50, 100]),
    SettingField("safety_y_max",  "Y Max",  "spinbox", default=500,  min_val=-1000, max_val=1000, suffix=" mm", step=1, step_options=[1, 10, 50, 100]),
    SettingField("safety_z_min",  "Z Min",  "spinbox", default=100,  min_val=0,     max_val=1000, suffix=" mm", step=1, step_options=[1, 10, 50, 100]),
    SettingField("safety_z_max",  "Z Max",  "spinbox", default=800,  min_val=0,     max_val=1000, suffix=" mm", step=1, step_options=[1, 10, 50, 100]),
    SettingField("safety_rx_min", "RX Min", "spinbox", default=170,  min_val=-180,  max_val=180,  suffix=" °",  step=1, step_options=[1, 5, 10]),
    SettingField("safety_rx_max", "RX Max", "spinbox", default=180,  min_val=-180,  max_val=180,  suffix=" °",  step=1, step_options=[1, 5, 10]),
    SettingField("safety_ry_min", "RY Min", "spinbox", default=-10,  min_val=-180,  max_val=180,  suffix=" °",  step=1, step_options=[1, 5, 10]),
    SettingField("safety_ry_max", "RY Max", "spinbox", default=10,   min_val=-180,  max_val=180,  suffix=" °",  step=1, step_options=[1, 5, 10]),
    SettingField("safety_rz_min", "RZ Min", "spinbox", default=-180, min_val=-180,  max_val=180,  suffix=" °",  step=1, step_options=[1, 5, 10]),
    SettingField("safety_rz_max", "RZ Max", "spinbox", default=180,  min_val=-180,  max_val=180,  suffix=" °",  step=1, step_options=[1, 5, 10]),
])

CALIBRATION_AXIS_MAPPING_GROUP = SettingGroup("Axis Mapping", [
    SettingField("calib_axis_marker_id",       "Marker ID",            "spinbox",        default=4,     min_val=0,   max_val=255,  step=1,   step_options=[1]),
    SettingField("calib_axis_move_mm",         "Move Distance",        "double_spinbox", default=100.0, min_val=1.0, max_val=500.0, decimals=1, suffix=" mm", step=1.0, step_options=[1, 5, 10, 50]),
    SettingField("calib_axis_max_attempts",    "Max Detect Attempts",  "spinbox",        default=100,   min_val=1,   max_val=1000, step=10,  step_options=[10, 50, 100]),
    SettingField("calib_axis_delay_after_move","Delay After Move",     "double_spinbox", default=1.0,   min_val=0.0, max_val=10.0, decimals=2, suffix=" s", step=0.1, step_options=[0.1, 0.5, 1.0]),
])

CALIBRATION_CAMERA_TCP_GROUP = SettingGroup("Camera TCP Offset Calibration", [
    SettingField("calib_tcp_marker_id",          "Marker ID",           "spinbox",        default=4,     min_val=0,   max_val=255,  step=1,   step_options=[1]),
    SettingField("calib_tcp_run_during_main",    "Capture In Main Cal", "combo",          default="False", choices=["False", "True"]),
    SettingField("calib_tcp_max_markers",        "Max Markers",         "spinbox",        default=2,     min_val=1,   max_val=50,   step=1,   step_options=[1, 2, 3, 5, 10]),
    SettingField("calib_tcp_rotation_step_deg",  "Rotation Step",       "double_spinbox", default=15.0,  min_val=0.1, max_val=180.0, decimals=2, suffix=" °", step=0.1, step_options=[0.1, 1.0, 5.0, 15.0]),
    SettingField("calib_tcp_iterations",         "Iterations",          "spinbox",        default=6,     min_val=1,   max_val=100,  step=1,   step_options=[1, 2, 5, 10]),
    SettingField("calib_tcp_approach_z",         "Approach Z",          "double_spinbox", default=300.0, min_val=0.0, max_val=1000.0, decimals=3, suffix=" mm", step=0.1, step_options=[0.1, 1.0, 10.0, 50.0]),
    SettingField("calib_tcp_approach_rx",        "Approach RX",         "double_spinbox", default=180.0, min_val=-180.0, max_val=180.0, decimals=3, suffix=" °", step=0.1, step_options=[0.1, 1.0, 5.0, 10.0]),
    SettingField("calib_tcp_approach_ry",        "Approach RY",         "double_spinbox", default=0.0,   min_val=-180.0, max_val=180.0, decimals=3, suffix=" °", step=0.1, step_options=[0.1, 1.0, 5.0, 10.0]),
    SettingField("calib_tcp_approach_rz",        "Reference RZ",        "double_spinbox", default=0.0,   min_val=-180.0, max_val=180.0, decimals=3, suffix=" °", step=0.1, step_options=[0.1, 1.0, 5.0, 10.0]),
    SettingField("calib_tcp_velocity",           "Velocity",            "spinbox",        default=20,    min_val=1,   max_val=1000, suffix=" mm/s",  step=1, step_options=[1, 5, 10, 50]),
    SettingField("calib_tcp_acceleration",       "Acceleration",        "spinbox",        default=10,    min_val=1,   max_val=1000, suffix=" mm/s²", step=1, step_options=[1, 5, 10, 50]),
    SettingField("calib_tcp_settle_time_s",      "Settle Time",         "double_spinbox", default=1.0,   min_val=0.0, max_val=10.0, decimals=2, suffix=" s", step=0.1, step_options=[0.1, 0.5, 1.0, 2.0]),
    SettingField("calib_tcp_detection_attempts", "Detection Attempts",  "spinbox",        default=20,    min_val=1,   max_val=1000, step=1, step_options=[1, 5, 10, 20, 50]),
    SettingField("calib_tcp_retry_delay_s",      "Retry Delay",         "double_spinbox", default=0.1,   min_val=0.0, max_val=10.0, decimals=2, suffix=" s", step=0.01, step_options=[0.01, 0.1, 0.5, 1.0]),
    SettingField("calib_tcp_recenter_max_iterations", "Recenter Max Iters", "spinbox",    default=20,    min_val=1,   max_val=200,  step=1, step_options=[1, 5, 10, 20, 50]),
    SettingField("calib_tcp_min_samples",        "Min Samples",         "spinbox",        default=3,     min_val=1,   max_val=200,  step=1, step_options=[1, 2, 3, 5, 10]),
    SettingField("calib_tcp_max_acceptance_std_mm", "Max Std",          "double_spinbox", default=10.0,  min_val=0.0, max_val=100.0, decimals=3, suffix=" mm", step=0.1, step_options=[0.1, 1.0, 5.0, 10.0]),
])
