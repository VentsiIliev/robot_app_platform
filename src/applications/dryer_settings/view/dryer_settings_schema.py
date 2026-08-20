from pl_gui.settings.settings_view.schema import SettingField, SettingGroup


REGISTER_GROUP = SettingGroup("Registers", [
    SettingField("plate_register", "Plate Register", "spinbox", default=2,
                 min_val=0, max_val=65535, step=1, step_options=[1, 10, 100]),
    SettingField("open_plate_value", "Open Plate Value", "spinbox", default=2,
                 min_val=0, max_val=65535, step=1, step_options=[1, 10, 100]),
    SettingField("close_plate_value", "Close Plate Value", "spinbox", default=0,
                 min_val=0, max_val=65535, step=1, step_options=[1, 10, 100]),
])

TIMING_GROUP = SettingGroup("Timing Defaults", [
    SettingField("default_delay_move_up", "Move Up Delay", "spinbox", default=120,
                 min_val=0, max_val=65535, step=1, step_options=[1, 10, 100]),
    SettingField("default_delay_move_down", "Move Down Delay", "spinbox", default=140,
                 min_val=0, max_val=65535, step=1, step_options=[1, 10, 100]),
    SettingField("default_delay_move_in", "Move In Delay", "spinbox", default=80,
                 min_val=0, max_val=65535, step=1, step_options=[1, 10, 100]),
    SettingField("default_delay_move_out", "Move Out Delay", "spinbox", default=90,
                 min_val=0, max_val=65535, step=1, step_options=[1, 10, 100]),
    SettingField("default_speed_of_plates", "Plate Speed", "spinbox", default=50,
                 min_val=0, max_val=65535, step=1, step_options=[1, 10, 100]),
])
