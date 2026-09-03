from pl_gui.settings.settings_view.schema import SettingField, SettingGroup


def _int_field(name: str, label: str, default: int) -> SettingField:
    return SettingField(name, label, "spinbox", default=default, min_val=0,
                        max_val=65535, step=1, step_options=[1, 10, 100])


REGISTER_GROUP = SettingGroup("Servo and Plate Values", [
    _int_field("pwm_open_vrytka", "Gate Open PWM", 600),
    _int_field("pwm_close_vrytka", "Gate Close PWM", 150),
    _int_field("pwm_open_izbutvatel", "Ejector Open PWM", 600),
    _int_field("pwm_close_izbutvatel", "Ejector Close PWM", 180),
    _int_field("rev_minute", "Revolutions per Minute", 50),
    SettingField("acceleration", "Acceleration", "double_spinbox", default=0.1,
                 min_val=0.0, max_val=6553.5, step=0.1, decimals=1),
    _int_field("target_position_backword", "Target Position Backward", 500),
    _int_field("target_position_forword", "Target Position Forward", 500),
])

TIMING_GROUP = SettingGroup("Timing Values", [
    _int_field("time_delay_move_servo_up", "Servo Up Delay", 80),
    _int_field("time_delay_move_servo_down", "Servo Down Delay", 50),
    _int_field("time_delay_move_servo_in", "Servo In Delay", 30),
    _int_field("time_delay_move_servo_out", "Servo Out Delay", 50),
    _int_field("time_delay_move_plate_in", "Plate In Delay", 300),
    _int_field("time_delay_move_plate_out", "Plate Out Delay", 350),
    _int_field("time_delay_start_servo_move", "Servo Start Delay", 50),
])
