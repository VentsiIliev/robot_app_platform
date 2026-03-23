# `src/engine/robot/configuration/` — Robot Configuration

This package contains the settings dataclasses for robot operation and calibration, along with their serializers. These are the settings objects consumed directly by `MotionService`, `SafetyChecker`, `NavigationService`, and calibration routines.

---

## Class Diagram

```
RobotSettings
  ├── robot_ip: str
  ├── robot_tool: int
  ├── robot_user: int
  ├── camera_to_tcp_x_offset / camera_to_tcp_y_offset: float
  ├── tcp_x/y_step_distance / offset: float
  ├── offset_direction_map: OffsetDirectionMap
  ├── movement_groups: Dict[str, MovementGroup]
  ├── safety_limits: SafetyLimits
  └── global_motion_settings: GlobalMotionSettings
        ─────────────────────
        RobotSettingsSerializer → ISettingsSerializer[RobotSettings]
        settings_type = "robot_config"

RobotCalibrationSettings
  ├── adaptive_movement: AdaptiveMovementConfig
  ├── axis_mapping: AxisMappingConfig
  ├── camera_tcp_offset: CameraTcpOffsetCalibrationConfig
  ├── z_target: int
  └── required_ids: List[int]
        ─────────────────────
        RobotCalibrationSettingsSerializer → ISettingsSerializer[RobotCalibrationSettings]
        settings_type = "robot_calibration"
```

---

## API Reference

### `SafetyLimits`

**File:** `robot_settings.py`

Workspace bounds checked by `SafetyChecker` before every motion command.

```python
@dataclass
class SafetyLimits:
    x_min: int = -500;  x_max: int = 500
    y_min: int = -500;  y_max: int = 500
    z_min: int = 100;   z_max: int = 800
    rx_min: int = 170;  rx_max: int = 190
    ry_min: int = -10;  ry_max: int = 10
    rz_min: int = -180; rz_max: int = 180
```

Only `x`, `y`, `z` bounds are enforced by `SafetyChecker`. Rotation bounds are stored for reference.

---

### `MovementGroup`

**File:** `robot_settings.py`

A named motion configuration used by `NavigationService`. Each group stores a target position (or list of waypoints), velocity, and acceleration.

```python
@dataclass
class MovementGroup:
    velocity: int = 0
    acceleration: int = 0
    position: Optional[str] = None    # e.g., "[200.0, -100.0, 400.0, 180.0, 0.0, 0.0]"
    points: List[str] = field(...)    # list of position strings
    iterations: int = 1

    def parse_position(self) -> Optional[List[float]]: ...
    def parse_points(self) -> List[List[float]]: ...
```

Position strings are stored as `"[x, y, z, rx, ry, rz]"` for human-readability in JSON files.

Named groups used by `NavigationService`:
- `"HOME"` — used by `move_home()`
- `"LOGIN"` — used by `move_to_login_position()`
- `"CALIBRATION"` — used by `move_to_calibration_position()`

---

### `GlobalMotionSettings`

**File:** `robot_settings.py`

```python
@dataclass
class GlobalMotionSettings:
    global_velocity: int = 100
    global_acceleration: int = 100
    emergency_decel: int = 500
    max_jog_step: int = 50
```

---

### `OffsetDirectionMap`

**File:** `robot_settings.py`

Controls which directions are allowed for vision-guided offset corrections.

```python
@dataclass
class OffsetDirectionMap:
    pos_x: bool = True    # JSON key: "+X"
    neg_x: bool = True    # JSON key: "-X"
    pos_y: bool = True    # JSON key: "+Y"
    neg_y: bool = True    # JSON key: "-Y"
```

---

### `RobotSettings`

**File:** `robot_settings.py`

The top-level robot settings object. Retrieved via `settings_service.get("robot_config")`.

```python
@dataclass
class RobotSettings:
    robot_ip: str = "192.168.58.2"
    robot_tool: int = 0
    robot_user: int = 0
    camera_to_tcp_x_offset: float = 0.0
    camera_to_tcp_y_offset: float = 0.0
    tcp_x_step_distance: float = 50.0
    tcp_x_step_offset: float = 0.1
    tcp_y_step_distance: float = 50.0
    tcp_y_step_offset: float = 0.1
    offset_direction_map: OffsetDirectionMap = ...
    movement_groups: Dict[str, MovementGroup] = ...
    safety_limits: SafetyLimits = ...
    global_motion_settings: GlobalMotionSettings = ...
```

JSON key mapping (top-level):

| Dataclass field | JSON key |
|----------------|---------|
| `robot_ip` | `"ROBOT_IP"` |
| `robot_tool` | `"ROBOT_TOOL"` |
| `robot_user` | `"ROBOT_USER"` |
| `camera_to_tcp_x_offset` | `"CAMERA_TO_TCP_X_OFFSET"` |
| `camera_to_tcp_y_offset` | `"CAMERA_TO_TCP_Y_OFFSET"` |
| `movement_groups` | `"MOVEMENT_GROUPS"` |
| `safety_limits` | `"SAFETY_LIMITS"` |
| `global_motion_settings` | `"GLOBAL_MOTION_SETTINGS"` |

Robot-system-specific target-point definitions no longer belong here. In the glue system they live in a separate `GlueTargetingSettings` file under `targeting/definitions.json`, where measured points and frame definitions are stored independently from generic robot connection and motion settings.

---

### `AdaptiveMovementConfig`

**File:** `robot_calibration_settings.py`

Parameters for adaptive step-size control during vision-guided calibration.

```python
@dataclass
class AdaptiveMovementConfig:
    min_step_mm: float = 0.1
    max_step_mm: float = 25.0
    target_error_mm: float = 0.25
    max_error_ref: float = 100.0
    k: float = 2.0
    derivative_scaling: float = 0.5
```

---

### `RobotCalibrationSettings`

**File:** `robot_calibration_settings.py`

Retrieved via `settings_service.get("robot_calibration")`.

```python
@dataclass
class RobotCalibrationSettings:
    adaptive_movement: AdaptiveMovementConfig = ...
    axis_mapping: AxisMappingConfig = ...
    camera_tcp_offset: CameraTcpOffsetCalibrationConfig = ...
    z_target: int = 300
    required_ids: List[int] = [0, 1, 2, 3, 4, 5, 6, 8]
```

### `CameraTcpOffsetCalibrationConfig`

**File:** `robot_calibration_settings.py`

Persisted settings for the standalone camera-TCP offset calibration routine.

```python
@dataclass
class CameraTcpOffsetCalibrationConfig:
    run_during_robot_calibration: bool = False
    marker_id: int = 4
    rotation_step_deg: float = 15.0
    iterations: int = 6
    approach_z: float = 300.0
    approach_rx: float = 180.0
    approach_ry: float = 0.0
    approach_rz: float = 0.0
    velocity: int = 20
    acceleration: int = 10
    settle_time_s: float = 1.0
    detection_attempts: int = 20
    retry_delay_s: float = 0.1
    recenter_max_iterations: int = 20
    min_samples: int = 3
    max_acceptance_std_mm: float = 10.0
```

These values are edited in the Robot Settings calibration tab and consumed by two flows:
- `CameraTcpOffsetCalibrationService` for the standalone camera-TCP calibration action
- the main robot calibration pipeline when `run_during_robot_calibration=True`

Sampling semantics:
- `approach_rz` is the reference wrist angle used to establish the local tool frame
- the reference pose at `approach_rz` is not counted as a saved TCP-offset sample
- `iterations = N` means take `N` rotated samples after the reference pose
- with `rotation_step_deg = 15` and `iterations = 2`, the capture sequence is:
  - reference at `approach_rz`
  - sample 1 at `approach_rz + 15`
  - sample 2 at `approach_rz + 30`

Solve semantics:
- each rotated sample first measures a world-space robot correction `(world_dx, world_dy)` needed to re-center the camera on the same marker
- the saved local camera-to-TCP offset is solved from `t_world = (R_ref - R_sample) * c_local`
- larger `rotation_step_deg` values generally produce a better-conditioned solve than very small wrist rotations

The extra main-pipeline fields mean:
- `run_during_robot_calibration`: enable TCP-offset capture during the normal marker-calibration run
- `max_markers_for_tcp_capture`: limit how many successfully aligned markers are used for in-main TCP-offset capture
- `recenter_max_iterations`: maximum iterative re-centering attempts per rotated sample
- `min_samples`: minimum collected local samples required before saving a result
- `max_acceptance_std_mm`: maximum allowed sample spread on `x` and `y` before the result is rejected

---

## Usage Example

```python
# Reading settings
config: RobotSettings = settings_service.get("robot_config")

# Accessing a named position
home_group = config.movement_groups.get("HOME")
if home_group:
    position = home_group.parse_position()
    print(f"Home position: {position}")

# Checking safety limits
limits = config.safety_limits
print(f"Z range: {limits.z_min}mm to {limits.z_max}mm")

# Calibration settings
calib: RobotCalibrationSettings = settings_service.get("robot_calibration")
print(f"Z target: {calib.z_target}mm")
```

---

## Design Notes

- **Position strings in JSON**: `MovementGroup.position` stores positions as `"[x, y, z, rx, ry, rz]"` strings for easy human editing. `parse_position()` converts them to `List[float]` at runtime.
- **JSON keys are uppercase**: The JSON file uses `"ROBOT_IP"`, `"MOVEMENT_GROUPS"`, etc. (uppercase), while the Python fields use `snake_case`. This is a deliberate convention matching the original configuration format.
- **`RobotSettingsSerializer.settings_type = "robot_config"`**: The `name` used in `settings_service.get()` calls must match the key in `SettingsSpec`, not necessarily `settings_type`.
