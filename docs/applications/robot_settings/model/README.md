# `src/applications/robot_settings/model/` — Robot Settings Model

---

## `RobotSettingsModel`

**File:** `robot_settings_model.py`

```python
class RobotSettingsModel(IApplicationModel):
    def __init__(self, service: IRobotSettingsService): ...

    def load(self) -> tuple[RobotSettings, RobotCalibrationSettings]: ...
    def save(self, flat: dict, movement_groups: Dict[str, MovementGroup] = None) -> None: ...
```

Holds both `_config: Optional[RobotSettings]` and `_calibration: Optional[RobotCalibrationSettings]` in memory after `load()`. Contains zero Qt imports.

| Method | Behaviour |
|--------|-----------|
| `load()` | Calls `service.load_config()` + `service.load_calibration()`, caches both, returns `(config, calibration)` |
| `save(flat, movement_groups)` | Maps flat dict → updated `RobotSettings`; sets `updated.movement_groups = movement_groups`; saves via service; then maps flat dict → updated `RobotCalibrationSettings`; saves via service |

---

## `RobotSettingsMapper`

**File:** `mapper.py`

```python
class RobotSettingsMapper:
    @staticmethod
    def to_flat_dict(config: RobotSettings) -> dict: ...

    @staticmethod
    def from_flat_dict(flat: dict, base: RobotSettings) -> RobotSettings: ...
```

### `to_flat_dict` keys

| Key | Source |
|-----|--------|
| `robot_ip` | `config.robot_ip` |
| `robot_tool` | `config.robot_tool` |
| `robot_user` | `config.robot_user` |
| `camera_to_tcp_x_offset`, `camera_to_tcp_y_offset` | `config.camera_to_tcp_x_offset`, `config.camera_to_tcp_y_offset` |
| `camera_to_tool_x_offset`, `camera_to_tool_y_offset` | `config.camera_to_tool_x_offset`, `config.camera_to_tool_y_offset` |
| `global_velocity`, `global_acceleration`, `emergency_decel`, `max_jog_step` | `config.global_motion_settings.*` |
| `tcp_x_step_distance`, `tcp_x_step_offset`, `tcp_y_step_distance`, `tcp_y_step_offset` | `config.tcp_*` |
| `offset_pos_x`, `offset_neg_x`, `offset_pos_y`, `offset_neg_y` | `str(config.offset_direction_map.*)` |
| `safety_x_min/max`, `safety_y_min/max`, `safety_z_min/max`, `safety_rx_min/max`, `safety_ry_min/max`, `safety_rz_min/max` | `config.safety_limits.*` |

### `from_flat_dict` type coercions

| Field group | Coercion |
|-------------|---------|
| `robot_tool`, `robot_user`, motion integers, safety bounds | `int()` |
| `camera_to_*_offset`, `tcp_*_distance`, `tcp_*_step_offset` | `float()` |
| `offset_*` | `str(...) == "True"` → `bool` |
| `robot_ip` | `str()` |

---

## `RobotCalibrationMapper`

**File:** `mapper.py`

```python
class RobotCalibrationMapper:
    @staticmethod
    def to_flat_dict(settings: RobotCalibrationSettings) -> dict: ...

    @staticmethod
    def from_flat_dict(flat: dict, base: RobotCalibrationSettings) -> RobotCalibrationSettings: ...
```

### Keys

| Key | Source | Type |
|-----|--------|------|
| `calib_min_step_mm`, `calib_max_step_mm`, `calib_target_error_mm`, `calib_max_error_ref`, `calib_k`, `calib_derivative_scaling` | `settings.adaptive_movement.*` | `float` |
| `calib_z_target` | `settings.z_target` | `int` |
| `calib_required_ids` | `settings.required_ids` | unchanged (list) |
| `calib_axis_*` | `settings.axis_mapping.*` | `int` / `float` |
| `calib_tcp_*` | `settings.camera_tcp_offset.*` | `int` / `float` |

`calib_tcp_*` holds the persisted configuration for both camera-TCP offset flows:
- the standalone camera-TCP offset calibration routine
- the optional capture phase inside the main robot calibration pipeline

Additional keys used by the in-main-calibration capture flow:
- `calib_tcp_run_during_main`
- `calib_tcp_max_markers`
- `calib_tcp_recenter_max_iterations`
- `calib_tcp_min_samples`
- `calib_tcp_max_acceptance_std_mm`

---

## Design Notes

- **`deepcopy` before mutation**: Both mappers use `deepcopy(base)` before applying flat values. This prevents accidental mutation of the cached `_config` / `_calibration` objects.
- **`movement_groups` bypasses the flat dict**: The `MovementGroupsTab` widget produces `Dict[str, MovementGroup]` objects directly, not flat string values. The model receives them as a separate argument and assigns them after mapping.
