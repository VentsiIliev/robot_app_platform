from pl_gui.settings.settings_view.schema import SettingField, SettingGroup


REGISTER_GROUP = SettingGroup("Registers", [
    SettingField("status_register", "Status Register", "spinbox", default=100,
                 min_val=0, max_val=65535, step=1, step_options=[1, 10, 100]),
    SettingField("command_register", "Command Register", "spinbox", default=101,
                 min_val=0, max_val=65535, step=1, step_options=[1, 10, 100]),
    SettingField("delay_move_up_register", "Move Up Register", "spinbox", default=102,
                 min_val=0, max_val=65535, step=1, step_options=[1, 10, 100]),
    SettingField("delay_move_down_register", "Move Down Register", "spinbox", default=103,
                 min_val=0, max_val=65535, step=1, step_options=[1, 10, 100]),
    SettingField("delay_move_in_register", "Move In Register", "spinbox", default=104,
                 min_val=0, max_val=65535, step=1, step_options=[1, 10, 100]),
    SettingField("delay_move_out_register", "Move Out Register", "spinbox", default=105,
                 min_val=0, max_val=65535, step=1, step_options=[1, 10, 100]),
    SettingField("speed_of_plates_register", "Plate Speed Register", "spinbox", default=106,
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
