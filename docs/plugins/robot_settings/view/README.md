# `src/plugins/robot_settings/view/` — Robot Settings View

---

## `RobotSettingsView`

**File:** `robot_settings_view.py`

```python
class RobotSettingsView(IPluginView):
    save_requested   = pyqtSignal(dict)
    value_changed    = pyqtSignal(str, object, str)   # (key, value, component_name)
    movement_changed = pyqtSignal(str, object)        # (key, value)
```

Pure Qt widget. Builds a `SettingsView` with four tabs and a raw `MovementGroupsTab`. Contains zero business logic.

### Outbound Signals

| Signal | Emitted when |
|--------|-------------|
| `save_requested(dict)` | User clicks Save anywhere in the settings form |
| `value_changed(key, value, component)` | Any form field changes value |
| `movement_changed(key, value)` | Any movement group field changes |

### Inbound Methods

| Method | Effect |
|--------|--------|
| `load_config(config: RobotSettings)` | Calls `settings_view.load(config)` — uses `RobotSettingsMapper.to_flat_dict` as the mapper |
| `load_movement_groups(groups: dict)` | Calls `movement_tab.load(groups)` |
| `get_values() → dict` | Returns flat dict of all form field values |
| `get_movement_groups() → dict` | Returns `Dict[str, MovementGroup]` from `MovementGroupsTab` |

### Tab Layout

```
RobotSettingsView
  └─ SettingsView
       ├─ "General" tab         → ROBOT_INFO_GROUP, GLOBAL_MOTION_GROUP,
       │                           TCP_STEP_GROUP, OFFSET_DIRECTION_GROUP
       ├─ "Safety" tab          → SAFETY_LIMITS_GROUP
       ├─ "Movement Groups" tab → MovementGroupsTab (raw QWidget tab)
       └─ "Calibration" tab     → CALIBRATION_ADAPTIVE_GROUP, CALIBRATION_MARKER_GROUP
```

---

## `robot_settings_schema.py`

Defines the field group constants consumed by `RobotSettingsView.setup_ui()`:

| Constant | Fields |
|----------|--------|
| `ROBOT_INFO_GROUP` | `robot_ip`, `robot_tool`, `robot_user` |
| `GLOBAL_MOTION_GROUP` | `global_velocity`, `global_acceleration`, `emergency_decel`, `max_jog_step` |
| `TCP_STEP_GROUP` | `tcp_x_offset`, `tcp_y_offset`, `tcp_x_step_distance`, `tcp_x_step_offset`, `tcp_y_step_distance`, `tcp_y_step_offset` |
| `OFFSET_DIRECTION_GROUP` | `offset_pos_x`, `offset_neg_x`, `offset_pos_y`, `offset_neg_y` |
| `SAFETY_LIMITS_GROUP` | all 12 `safety_*_min/max` fields |
| `CALIBRATION_ADAPTIVE_GROUP` | all 6 `calib_*` adaptive movement fields |
| `CALIBRATION_MARKER_GROUP` | `calib_z_target`, `calib_required_ids` |

---

## `movement_groups_tab.py`

`MovementGroupsTab` is a raw `QWidget` (not a `SettingsView` tab) that provides a table or form for editing named movement positions. It emits `values_changed(key, value)` as the user edits rows, and exposes `load(groups: dict)` and `get_values() → Dict[str, MovementGroup]`.

---

## Design Notes

- **Named forwarders for all signal bridging**: `_on_inner_save`, `_on_inner_value_changed`, `_on_inner_movement_changed` are named bound methods — no lambdas or `.emit` references are used as connection targets.
- **`SettingsView.add_raw_tab`**: The Movement Groups tab is added with `add_raw_tab()` which accepts any `QWidget` directly, bypassing schema-driven field generation.
