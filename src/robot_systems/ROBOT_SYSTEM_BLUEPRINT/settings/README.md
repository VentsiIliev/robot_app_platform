# Robot-System-Specific Settings Pattern

Use this folder for settings that belong to the concrete robot system, not to shared platform infrastructure.

## What belongs here

Put a settings module in `settings/` when all of these are true:
- the data is persisted
- the data is specific to this robot system or process
- the data is not already a shared engine setting under `src/engine/`

Examples:
- targeting definitions
- glue process settings
- glue motor board topology
- cell layout / addresses for one robot system

Do not put these here:
- `RobotSettings`
- `RobotCalibrationSettings`
- `ModbusConfig`
- `CameraSettings`
- `ToolChangerSettings`

Those are shared settings and should stay in `src/engine/`.

## File layout

Recommended pattern:

```text
settings/
  __init__.py
  targeting.py
  glue.py
  device_control.py
```

Each module should normally contain:
- one persisted dataclass
- one serializer
- optional small helper dataclasses used only by that settings object

## Naming rule

Use the robot system or domain in the type name so ownership is obvious.

Good:
- `GlueTargetingSettings`
- `GlueSettings`
- `GlueMotorConfig`

Avoid vague names in robot-system code:
- `Settings`
- `Config`
- `TargetingSettings`

## Serializer rule

Each persisted settings type needs an `ISettingsSerializer` implementation.

Example shape:

```python
@dataclass
class MyProcessSettings:
    enabled: bool = True
    timeout_s: float = 1.0


class MyProcessSettingsSerializer(ISettingsSerializer[MyProcessSettings]):
    @property
    def settings_type(self) -> str:
        return "my_process_settings"

    def get_default(self) -> MyProcessSettings:
        return MyProcessSettings()

    def to_dict(self, settings: MyProcessSettings) -> dict:
        return {
            "ENABLED": settings.enabled,
            "TIMEOUT_S": settings.timeout_s,
        }

    def from_dict(self, data: dict) -> MyProcessSettings:
        return MyProcessSettings(
            enabled=bool(data.get("ENABLED", True)),
            timeout_s=float(data.get("TIMEOUT_S", 1.0)),
        )
```

## Where to register it

1. Add a robot-system-specific key in `component_ids.py`
2. Add a `SettingsSpec(...)` entry in `my_robot_system.py`
3. Add the default JSON file under `storage/settings/...`

Example:

```python
class SettingsID(str, Enum):
    MY_PROCESS = "my_process"


settings_specs = [
    SettingsSpec(
        SettingsID.MY_PROCESS,
        MyProcessSettingsSerializer(),
        "process/my_process.json",
    ),
]
```

## Storage rule

Use the storage path to show ownership.

Good examples:
- `robot/config.json` for shared robot config
- `vision/camera_settings.json` for shared vision config
- `targeting/definitions.json` for robot-system targeting
- `glue/settings.json` for glue-process settings
- `hardware/motors.json` for robot-system-specific hardware mapping

Do not hide unrelated settings under the wrong namespace just because a file already exists there.

## Access rule

At runtime:
- use `CommonSettingsID` for shared settings
- use `SettingsID` from `component_ids.py` for robot-system-specific settings

Example:

```python
self._robot_config = self.get_settings(CommonSettingsID.ROBOT_CONFIG)
self._targeting = self.get_settings(SettingsID.MY_TARGETING)
```

## Boundary rule

If a settings type starts being reused by multiple robot systems, move it out of the robot system and into `src/engine/`.

That usually means:
- move the dataclass + serializer
- switch the key to `CommonSettingsID`
- update the blueprint/docs
