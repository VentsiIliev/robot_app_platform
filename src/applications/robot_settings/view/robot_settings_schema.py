from pl_gui.settings.settings_view.schema import SettingField, SettingGroup

ROBOT_INFO_GROUP = SettingGroup("Robot Information", [
    SettingField("robot_ip",     "IP Address",   "line_edit",      default="192.168.58.2"),
    SettingField("robot_tool",   "Tool Number",  "spinbox",        default=0,   min_val=0,     max_val=10,   step=1,   step_options=[1]),
    SettingField("robot_user",   "User Number",  "spinbox",        default=0,   min_val=0,     max_val=10,   step=1,   step_options=[1]),
    SettingField("tcp_x_offset", "TCP X Offset", "double_spinbox", default=0.0, min_val=-1000, max_val=1000, decimals=3, suffix=" mm", step=0.001, step_options=[0.001, 0.01, 0.1, 1]),
    SettingField("tcp_y_offset", "TCP Y Offset", "double_spinbox", default=0.0, min_val=-1000, max_val=1000, decimals=3, suffix=" mm", step=0.001, step_options=[0.001, 0.01, 0.1, 1]),
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
])

CALIBRATION_MARKER_GROUP = SettingGroup("Marker Detection", [
    SettingField("calib_z_target",     "Z Target Height", "spinbox",   default=300,             min_val=0, max_val=1000, suffix=" mm", step=1, step_options=[1, 10, 50]),
    SettingField("calib_required_ids", "Required IDs",    "int_list",  default="0,1,2,3,4,5,6,8", min_val=0, max_val=255),
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
