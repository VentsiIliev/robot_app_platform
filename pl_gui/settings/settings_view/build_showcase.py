from src.settings.settings_view import SettingField, SettingGroup
from src.settings.settings_view import SettingsView


# ── Demo groups ───────────────────────────────────────────────────────────────

SPINBOX_GROUP = SettingGroup("spinbox  —  integer stepper", [
    SettingField(
        "spin_no_pills", "No step pills  (step_options=[1])",
        "spinbox", default=42, min_val=0, max_val=100, step=1,
        step_options=[1],
    ),
    SettingField(
        "spin_with_pills", "Step pills  (step_options=[1,5,10,50])",
        "spinbox", default=100, min_val=0, max_val=1000, suffix=" mm/s", step=1,
        step_options=[1, 5, 10, 50],
    ),
])

DOUBLE_SPINBOX_GROUP = SettingGroup("double_spinbox  —  float stepper", [
    SettingField(
        "double_2dec", "2 decimals",
        "double_spinbox", default=1.5, min_val=0.0, max_val=10.0,
        decimals=2, step=0.1, step_options=[0.1, 0.5, 1.0],
    ),
    SettingField(
        "double_3dec", "3 decimals + suffix",
        "double_spinbox", default=0.025, min_val=-100.0, max_val=100.0,
        decimals=3, suffix=" mm", step=0.001, step_options=[0.001, 0.01, 0.1, 1.0],
    ),
])

TEXT_GROUP = SettingGroup("line_edit  —  free text input", [
    SettingField(
        "line_ip", "IP address",
        "line_edit", default="192.168.1.100",
    ),
    SettingField(
        "line_name", "Name",
        "line_edit", default="My Robot",
    ),
])

COMBO_GROUP = SettingGroup("combo  —  dropdown selector", [
    SettingField(
        "combo_mode", "Operating mode",
        "combo", default="Auto",
        choices=["Manual", "Auto", "Semi-Auto"],
    ),
    SettingField(
        "combo_bool", "Boolean as combo  (True / False)",
        "combo", default="True",
        choices=["True", "False"],
    ),
])

INT_LIST_GROUP = SettingGroup("int_list  —  add / edit / remove integer items", [
    SettingField(
        "int_list_ids", "Marker IDs  (0 – 255)",
        "int_list", default="0,1,2,3,4,5,6,8",
        min_val=0, max_val=255,
    ),
])

MIXED_GROUP = SettingGroup("Mixed  —  int_list spans full width; other fields stay 2-column", [
    SettingField(
        "mixed_spin", "Spinbox left",
        "spinbox", default=10, min_val=0, max_val=100, step=1, step_options=[1],
    ),
    SettingField(
        "mixed_combo", "Combo right",
        "combo", default="B", choices=["A", "B", "C"],
    ),
    SettingField(
        "mixed_list", "Int list  (full row)",
        "int_list", default="10,20,30", min_val=0, max_val=999,
    ),
    SettingField(
        "mixed_text", "Line edit below",
        "line_edit", default="back to normal",
    ),
])


# ── Factory ───────────────────────────────────────────────────────────────────

def build_showcase() -> SettingsView:
    view = SettingsView(component_name="Showcase")
    view.add_tab("Numeric",      [SPINBOX_GROUP, DOUBLE_SPINBOX_GROUP])
    view.add_tab("Text & Combo", [TEXT_GROUP, COMBO_GROUP])
    view.add_tab("Int List",     [INT_LIST_GROUP])
    view.add_tab("Mixed",        [MIXED_GROUP])
    return view
