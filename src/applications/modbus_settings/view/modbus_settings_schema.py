from pl_gui.settings.settings_view.schema import SettingField, SettingGroup

CONNECTION_GROUP = SettingGroup("Connection", [
    SettingField("baudrate", "Baudrate",  "combo", default="115200",
                 choices=["9600", "19200", "38400", "57600", "115200", "230400", "460800"]),
    SettingField("parity",   "Parity",    "combo", default="N",
                 choices=["N", "E", "O", "M", "S"]),
    SettingField("bytesize", "Byte Size", "combo", default="8",
                 choices=["5", "6", "7", "8"]),
    SettingField("stopbits", "Stop Bits", "combo", default="1",
                 choices=["1", "2"]),
    SettingField("timeout",  "Timeout",   "double_spinbox", default=0.01,
                 min_val=0.001, max_val=10.0, decimals=3, suffix=" s",
                 step=0.001, step_options=[0.001, 0.01, 0.1, 1.0]),
])

DEVICE_GROUP = SettingGroup("Device", [
    SettingField("slave_address", "Slave Address", "spinbox", default=10,
                 min_val=1, max_val=247, step=1, step_options=[1, 5, 10]),
    SettingField("max_retries",   "Max Retries",   "spinbox", default=30,
                 min_val=1, max_val=100, step=1, step_options=[1, 5, 10]),
])
