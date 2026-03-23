# `src/applications/robot_settings/view/` — Robot Settings View

---

## `RobotSettingsView`

**File:** `robot_settings_view.py`

```python
class RobotSettingsView(IApplicationView):
    save_requested   = pyqtSignal(dict)
    value_changed    = pyqtSignal(str, object, str)   # (key, value, component_name)
    movement_changed = pyqtSignal(str, object)        # (key, value)
```

Pure Qt widget. Builds a `SettingsView` with schema-driven tabs plus two raw tabs: `MovementGroupsTab` and `TargetingDefinitionsTab`. Contains zero business logic.

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
| `load_targeting_definitions(data: dict \| None)` | Calls `targeting_tab.load(data)` |
| `get_values() → dict` | Returns flat dict of all form field values |
| `get_movement_groups() → dict` | Returns `Dict[str, MovementGroup]` from `MovementGroupsTab` |
| `get_targeting_definitions() → dict` | Returns generic point/frame definition data from `TargetingDefinitionsTab` |

### Tab Layout

```
RobotSettingsView
  └─ SettingsView
       ├─ "General" tab         → ROBOT_INFO_GROUP, GLOBAL_MOTION_GROUP,
       │                           TCP_STEP_GROUP, OFFSET_DIRECTION_GROUP
       ├─ "Safety" tab          → SAFETY_LIMITS_GROUP
       ├─ "Movement Groups" tab → MovementGroupsTab (raw QWidget tab)
       ├─ "Targeting" tab       → TargetingDefinitionsTab (raw QWidget tab)
       └─ "Calibration" tab     → CALIBRATION_ADAPTIVE_GROUP, CALIBRATION_MARKER_GROUP,
                                   CALIBRATION_AXIS_MAPPING_GROUP,
                                   CALIBRATION_CAMERA_TCP_GROUP
```

---

## `robot_settings_schema.py`

Defines the field group constants consumed by `RobotSettingsView.setup_ui()`:

| Constant | Fields |
|----------|--------|
| `ROBOT_INFO_GROUP` | `robot_ip`, `robot_tool`, `robot_user`, `camera_to_tcp_x_offset`, `camera_to_tcp_y_offset` |
| `GLOBAL_MOTION_GROUP` | `global_velocity`, `global_acceleration`, `emergency_decel`, `max_jog_step` |
| `TCP_STEP_GROUP` | `tcp_x_step_distance`, `tcp_x_step_offset`, `tcp_y_step_distance`, `tcp_y_step_offset` |
| `OFFSET_DIRECTION_GROUP` | `offset_pos_x`, `offset_neg_x`, `offset_pos_y`, `offset_neg_y` |
| `SAFETY_LIMITS_GROUP` | all 12 `safety_*_min/max` fields |
| `CALIBRATION_ADAPTIVE_GROUP` | all 6 `calib_*` adaptive movement fields |
| `CALIBRATION_MARKER_GROUP` | `calib_z_target`, `calib_required_ids`, `calib_velocity`, `calib_acceleration` |
| `CALIBRATION_AXIS_MAPPING_GROUP` | `calib_axis_marker_id`, `calib_axis_move_mm`, `calib_axis_max_attempts`, `calib_axis_delay_after_move` |
| `CALIBRATION_CAMERA_TCP_GROUP` | `calib_tcp_marker_id`, `calib_tcp_run_during_main`, `calib_tcp_max_markers`, `calib_tcp_rotation_step_deg`, `calib_tcp_iterations`, `calib_tcp_approach_z`, `calib_tcp_approach_rx`, `calib_tcp_approach_ry`, `calib_tcp_approach_rz`, `calib_tcp_velocity`, `calib_tcp_acceleration`, `calib_tcp_settle_time_s`, `calib_tcp_detection_attempts`, `calib_tcp_retry_delay_s`, `calib_tcp_recenter_max_iterations`, `calib_tcp_min_samples`, `calib_tcp_max_acceptance_std_mm` |

---

## `movement_groups_tab.py`

`MovementGroupsTab` is a raw `QWidget` (not a `SettingsView` tab) that provides a table or form for editing named movement positions. It emits `values_changed(key, value)` as the user edits rows, and exposes `load(groups: dict)` and `get_values() → Dict[str, MovementGroup]`.

`TargetingDefinitionsTab` is another raw `QWidget` that edits generic targeting metadata:
- named target points with `x_mm`, `y_mm`, and optional aliases
- named frames with optional source/target navigation groups and a height-correction toggle

The tab itself is generic. Robot-system-specific protected rows and serialization are supplied by the application service layer.

---

## Design Notes

- **Named forwarders for all signal bridging**: `_on_inner_save`, `_on_inner_value_changed`, `_on_inner_movement_changed` are named bound methods — no lambdas or `.emit` references are used as connection targets.
- **`SettingsView.add_raw_tab`**: The Movement Groups and Targeting tabs are added with `add_raw_tab()` which accepts any `QWidget` directly, bypassing schema-driven field generation.
