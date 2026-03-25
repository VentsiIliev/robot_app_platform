# `src/robot_systems/glue/settings/` — Glue App Settings Definitions

This package contains the settings dataclasses and serializers specific to the `GlueRobotSystem`.

---

## Files Overview

| File | Type | Description |
|------|------|-------------|
| `glue.py` | Settings dataclass + serializer | Application-level glue dispenser parameters |
| `glue_types.py` | Domain model + serializer | Glue type catalog (`GlueCatalog`, `Glue`) |
| `cells.py` | Serializer subclass | `GlueCellsConfigSerializer` with glue-specific cell defaults |
| `device_control.py` | Settings dataclass + serializer | `GlueMotorConfig` / `GlueMotorConfigSerializer` for glue motor board settings |
| `glue_segment_settings_schema.py` | `SegmentSettingsSchema` instance | Per-segment dispensing field definitions used by the Workpiece Editor |

---

## `GlueSettings` (`glue.py`)

Persisted under key `"glue_settings"` → `glue/settings.json`.

```python
@dataclass
class GlueSettings:
    spray_width: int                         = 5
    spraying_height: int                     = 10
    fan_speed: int                           = 50
    time_between_generator_and_glue: float   = 1.0
    motor_speed: int                         = 10000
    reverse_duration: float                  = 1.0
    speed_reverse: int                       = 1000
    rz_angle: float                          = 0.0
    glue_type: str                           = "Type A"
    generator_timeout: float                 = 5.0
    time_before_motion: float                = 1.0
    time_before_stop: float                  = 1.0
    reach_start_threshold: float             = 1.0
    reach_end_threshold: float               = 1.0
    initial_ramp_speed: int                  = 5000
    forward_ramp_steps: int                  = 1
    reverse_ramp_steps: int                  = 1
    initial_ramp_speed_duration: float       = 1.0
    spray_on: bool                           = True
```

All field names are also defined as `GlueSettingKey` enum values for type-safe key access.

---

## `GlueCatalog` / `Glue` (`glue_types.py`)

Persisted under key `"glue_catalog"` → `glue/catalog.json`. Stores the library of named glue types available for the dispenser.

```python
@dataclass
class Glue:
    id:          str    # UUID auto-generated
    name:        str    # display name, trimmed
    description: str    = ""

@dataclass
class GlueCatalog:
    glue_types: List[Glue] = field(default_factory=list)

    def get_by_id(self, glue_id: str) -> Optional[Glue]: ...
    def get_by_name(self, name: str) -> Optional[Glue]: ...
    def get_all_names(self) -> List[str]: ...
    def get_all_ids(self) -> List[str]: ...
    def add(self, glue: Glue) -> None: ...        # raises ValueError if name duplicate
    def remove_by_id(self, glue_id: str) -> bool: ...
    def count: int  # property
```

Default catalog (auto-created on first run): `"Type A"`, `"Type B"`.

---

## `GlueCellsConfigSerializer` (`cells.py`)

Subclasses `CellsConfigSerializer` (from engine layer). The only glue-specific content is:
- `settings_type = "glue_cells"`
- Default 3 cells: IPs `192.168.222.143/weight1..3`, capacity 1000g, motor addresses 0/2/4

## `GlueMotorConfig` (`device_control.py`)

Persisted under key `"glue_motor_config"` → `hardware/motors.json`.

```python
@dataclass
class GlueMotorConfig:
    motors: List[MotorSpec]
    health_check_trigger_register: int = 17
    motor_error_count_register: int = 20
    motor_error_registers_start: int = 21
    health_check_delay_s: float = 3.0
```

`GlueMotorConfigSerializer` stores the register map under a top-level `"board"` object and the motor topology under `"motors"`. Default topology is four glue pumps at addresses `0/2/4/6` with error prefixes `1/2/3/4`.

`build_motor_service()` reads this settings object and maps it into the generic engine-layer `MotorConfig`, so board register changes no longer require editing `service_builders.py`.

---

## `GLUE_SEGMENT_SETTINGS_SCHEMA` (`glue_segment_settings_schema.py`)

A `SegmentSettingsSchema` instance that declares all per-segment dispensing fields shown in the Workpiece Editor UI. Each field specifies a `GlueSettingKey` name, a default string value, an optional tab name, and an optional validator.

Fields declared in this schema (with defaults):

| Field | Default | Tab | Notes |
|-------|---------|-----|-------|
| `spray_width` | `"10"` | | mm |
| `spraying_height` | `"0"` | | mm above z_min |
| `fan_speed` | `"100"` | | % |
| `time_between_generator_and_glue` | `"1"` | | seconds |
| `motor_speed` | `"500"` | | rpm |
| `reverse_duration` | `"0.5"` | | seconds |
| `speed_reverse` | `"3000"` | | rpm |
| `rz_angle` | `"0"` | | degrees |
| `glue_type` | `""` | | **required** (validator: non-empty) |
| `generator_timeout` | `"5"` | | minutes |
| `time_before_motion` | `"0.1"` | | seconds |
| `time_before_stop` | `"1.0"` | | seconds |
| `reach_start_threshold` | `"1.0"` | | mm |
| `reach_end_threshold` | `"30.0"` | | mm |
| `initial_ramp_speed_duration` | `"1.0"` | | seconds |
| `initial_ramp_speed` | `"5000"` | | rpm |
| `reverse_ramp_steps` | `"1"` | | count |
| `forward_ramp_steps` | `"3"` | | count |
| `glue_speed_coefficient` | `"5"` | | |
| `glue_acceleration_coefficient` | `"0"` | | |
| `adaptive_spacing_mm` | `"10"` | | mm |
| `spline_density_multiplier` | `"2.0"` | | |
| `smoothing_lambda` | `"0.0"` | | |
| `velocity` | `"60"` | Motion | mm/s |
| `acceleration` | `"30"` | Motion | mm/s² |

This schema is imported by the Workpiece Editor application to render the per-segment settings form and validate inputs. The actual runtime values are stored inside each `GlueWorkpiece.sprayPattern` segment's `"settings"` dict.

---

## Shared Engine Settings

These shared settings now live in the engine layer and should be imported directly from `src/engine/`:
- `ModbusConfig`, `ModbusConfigSerializer`
- `RobotSettings`, `RobotSettingsSerializer`
- `RobotCalibrationSettings`, `RobotCalibrationSettingsSerializer`
- [tool_changer_settings.py](/home/ilv/Desktop/robot_app_platform/src/engine/robot/configuration/tool_changer_settings.py)

---

## Design Notes

- **`GlueSettingKey` enum**: All 19 field names are declared as enum values. This prevents typos in key access (`GlueSettingKey.FAN_SPEED.value` rather than `"fan_speed"`). The `GlueSettings.from_dict()` and `to_dict()` methods use enum values as keys.
- **`device_control.py` keeps the old alias names alive**: `DeviceControlConfig` and `DeviceControlConfigSerializer` are backwards-compatible aliases for `GlueMotorConfig` and `GlueMotorConfigSerializer`.
