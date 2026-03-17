# `src/robot_systems/glue/settings/` — Glue App Settings Definitions

This package contains all settings dataclasses and serializers specific to the `GlueRobotSystem`, plus re-export shims for settings types that live in the engine layer.

---

## Files Overview

| File | Type | Description |
|------|------|-------------|
| `glue.py` | Settings dataclass + serializer | Application-level glue dispenser parameters |
| `glue_types.py` | Domain model + serializer | Glue type catalog (`GlueCatalog`, `Glue`) |
| `cells.py` | Serializer subclass | `GlueCellsConfigSerializer` with glue-specific cell defaults |
| `device_control.py` | Settings dataclass + serializer | `GlueMotorConfig` / `GlueMotorConfigSerializer` for glue motor board settings |
| `modbus.py` | Re-export shim | `ModbusConfig`, `ModbusConfigSerializer` from engine layer |
| `robot.py` | Re-export shim | `RobotSettings`, `RobotSettingsSerializer` etc. from engine layer |
| `robot_calibration.py` | Legacy class | `RobotCalibrationConfig` — runtime config object (not a serializer) |

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

## Re-export Shims

`modbus.py` and `robot.py` re-export types from `src/engine/` for backwards compatibility. **Prefer importing from `src/engine/` directly** in new code.

---

## Design Notes

- **`GlueSettingKey` enum**: All 19 field names are declared as enum values. This prevents typos in key access (`GlueSettingKey.FAN_SPEED.value` rather than `"fan_speed"`). The `GlueSettings.from_dict()` and `to_dict()` methods use enum values as keys.
- **`robot_calibration.py` is a legacy runtime config**: `RobotCalibrationConfig` is an old-style class used in calibration procedures (takes `vision_system`, `robot_service`, etc.). It is distinct from `RobotCalibrationSettings` (the persisted dataclass). Do not confuse the two.
- **`device_control.py` keeps the old alias names alive**: `DeviceControlConfig` and `DeviceControlConfigSerializer` are backwards-compatible aliases for `GlueMotorConfig` and `GlueMotorConfigSerializer`.
