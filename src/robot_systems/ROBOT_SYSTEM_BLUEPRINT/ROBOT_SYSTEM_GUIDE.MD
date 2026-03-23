# Robot System Blueprint

Copy `src/robot_systems/ROBOT_SYSTEM_BLUEPRINT/`, rename every `My` / `my` / `ROBOT_SYSTEM_BLUEPRINT`, and implement the marked `TODO` sections in order.

This blueprint is the robot-system equivalent of `APPLICATION_BLUEPRINT/`. It documents the current platform patterns for:
- class-level system declaration
- shared default service builders
- provider-based runtime assembly
- standardized storage and settings layout
- reusable targeting, frames, and jog wiring
- reusable Robot Settings targeting editing

---

## Architecture At A Glance

```
Bootstrap
  └─ SystemBuilder.build(MyRobotSystem)
       ├─ reads MyRobotSystem.settings_specs
       ├─ validates shared default-builder contracts up front
       ├─ builds declared services from MyRobotSystem.services
       ├─ instantiates MyRobotSystem()
       └─ calls MyRobotSystem.on_start()
            ├─ reads resolved services/settings into runtime attrs
            ├─ installs optional providers (targeting, calibration, height measuring)
            ├─ builds provider-based shared services if needed
            └─ starts long-lived runtime services if needed
```

Robot-system responsibilities:
- declare shell folders and applications
- declare service contracts and settings files
- assemble robot-system-specific runtime services
- expose optional providers for reusable base helpers

Robot-system responsibilities do **not** include:
- putting business logic in `BaseRobotSystem`
- hardcoding storage paths in application wiring
- duplicating target/jog math already available in `src/engine/robot/targeting/`
- reimplementing shared default builders for robot, navigation, tool, or vision unless behavior really differs

---

## Recommended File Structure

```
src/robot_systems/my_system/
  __init__.py
  my_robot_system.py
  application_wiring.py
  service_ids.py
  settings_ids.py
  service_builders.py
  settings/
    __init__.py
    targeting.py                optional but recommended if the system supports targeting
    ... other system settings
  calibration/
    __init__.py
    provider.py                optional when the system supports robot calibration
  height_measuring/
    __init__.py
    provider.py                optional when the system supports height measuring
  targeting/
    __init__.py
    point_names.py
    frame_names.py
    provider.py
    registry.py
    frames.py
    settings_adapter.py        adapter for the generic Robot Settings targeting tab
  storage/
    settings/
      robot/
      vision/
      targeting/
      height_measuring/
      ... other settings groups
    users/
      users.csv
    workpieces/
    translations/
      en.json
```

Use this split:
- `settings/` = persisted dataclasses and serializers
- `targeting/` = runtime naming and provider assembly
- `storage/` = checked-in defaults owned by the robot system
- `application_wiring.py` = application composition only

---

## Build Order

Implement in this order.

### 1. Define system identity and shell
File: `my_robot_system.py`

1. Set `metadata`
2. Define `shell.folders`
3. Define `shell.applications`
4. Add empty `settings_specs`
5. Add empty `services`

Goal:
- `SystemBuilder` can instantiate the robot system class
- the shell can discover the initial application list

### 2. Define IDs
Files:
- `service_ids.py`
- `settings_ids.py`

Rules:
- use `Enum` subclasses
- keep names stable after they are published
- one enum member per service/settings concept
- keep shared infrastructure ids in `src/engine/common_settings_ids.py`
- keep only robot-system-specific ids in `settings_ids.py`
- do not duplicate common ids in your robot-system enums

Goal:
- wiring and settings access stop relying on string literals

### 3. Define settings serializers and default files
Files:
- `settings/*.py`
- `storage/settings/...`

Rules:
- shared infrastructure settings should use `CommonSettingsID`
  - `ROBOT_CONFIG`
  - `ROBOT_CALIBRATION`
  - `VISION_CAMERA_SETTINGS`
  - `TOOL_CHANGER_CONFIG`
  - `MODBUS_CONFIG`
  - `HEIGHT_MEASURING_SETTINGS`
  - `HEIGHT_MEASURING_CALIBRATION`
  - `DEPTH_MAP_DATA`
- generic robot/runtime settings stay under `storage/settings/robot/...`
- robot-system-specific targeting should live under `storage/settings/targeting/...`
- process-specific settings should live under their own namespace, not under targeting

Goal:
- `settings_specs` can be filled with concrete `SettingsSpec(...)` entries

### 4. Define service contracts
Files:
- `service_builders.py`
- `services` in `my_robot_system.py`

Rules:
- use `ServiceSpec(...)`
- keep construction logic in builders or providers
- do not move robot-system-specific construction into `BaseRobotSystem`
- prefer shared default builders from:
  - `src/robot_systems/default_service_builders.py`
- prefer shared provider-based builders when available:
  - `build_robot_system_calibration_service(robot_system)`
  - `build_robot_system_height_measuring_services(robot_system)`

Goal:
- `SystemBuilder` can resolve the runtime service graph

### 4a. Understand the loud validation rules

`SystemBuilder` now validates shared service/settings contracts before building anything.

Examples:
- `IVisionService` requires `CommonSettingsID.VISION_CAMERA_SETTINGS`
- `IToolService` requires:
  - `CommonSettingsID.TOOL_CHANGER_CONFIG`
  - `CommonSettingsID.ROBOT_CONFIG`
- `CommonSettingsID.ROBOT_CALIBRATION` requires:
  - `IRobotService`
  - `IVisionService`
  - `NavigationService`
  - `CommonSettingsID.ROBOT_CONFIG`
- `CommonSettingsID.HEIGHT_MEASURING_SETTINGS` requires:
  - `IRobotService`
  - `IVisionService`
  - `CommonSettingsID.ROBOT_CONFIG`
  - `CommonSettingsID.HEIGHT_MEASURING_CALIBRATION`
  - `CommonSettingsID.DEPTH_MAP_DATA`

Plan for those dependencies explicitly in `settings_specs` and `services`. If you omit one side of a shared contract, startup fails loudly with a runtime error that names the missing declaration.

### 5. Implement `on_start()` / `on_stop()`
File: `my_robot_system.py`

In `on_start()`:
- read resolved services into instance attrs
- read settings into instance attrs
- start required background services
- install providers like `_targeting_provider` and `_calibration_provider`

In `on_stop()`:
- stop background services
- release robot-related resources

Goal:
- runtime system is fully initialized and cleanly stoppable

If the system supports robot calibration, prefer this pattern:

1. implement a robot-system-specific `...CalibrationProvider`
2. construct it in `on_start()`
3. call the shared engine builder

Example:

```python
from src.engine.robot.calibration.service_builders import (
    build_robot_system_calibration_service,
)

self._calibration_provider = MyRobotSystemCalibrationProvider(self)
self._calibration_service = build_robot_system_calibration_service(self)
```

Provider rule:
- keep the provider minimal
- it should normally only build the system-specific calibration-navigation
  adapter

If the system supports height measuring, prefer the same split:

1. implement a robot-system-specific `...HeightMeasuringProvider`
2. keep that provider minimal, ideally only `build_laser_control()`
3. call the shared engine builder in `on_start()`

Example:

```python
from src.engine.robot.height_measuring import (
    build_robot_system_height_measuring_services,
)

self._height_measuring_provider = MyRobotSystemHeightMeasuringProvider(self)
self._height_measuring_service, self._height_measuring_calibration_service, \
    self._laser_detection_service = build_robot_system_height_measuring_services(self)
```

Provider rule:
- keep common settings, common repositories, and common robot/vision service
  access in the shared builder
- use the provider only for the truly system-specific hardware piece

### 6. Wire applications
File: `application_wiring.py`

Rules:
- one `_build_<application>()` function per application
- compose services there
- use shared base helpers when available
- do not rebuild providers or shared runtime services in application wiring

Examples:
- `robot_system.get_shared_vision_resolver()`
- `build_robot_system_jog_service(robot_system, ...)`
- `robot_system.workpieces_storage_path()`

Goal:
- applications are built consistently and do not know robot-system internals

---

## Storage Rules

Use standardized `BaseRobotSystem` helpers:
- `workpieces_storage_path()`
- `users_storage_path()`
- `permissions_storage_path()`
- `storage_path(...)` for everything else

Do **not** do this in wiring:

```python
_SYSTEM_DIR = os.path.dirname(os.path.abspath(__file__))
```

Do this instead:

```python
repo = JsonWorkpieceRepository(robot_system.workpieces_storage_path())
```

This keeps storage conventions identical across robot systems.

---

## Targets And Frames

If the robot system supports image-target -> robot-pose resolution or target-aware jogging, define targeting explicitly.

### Where to define target names
File: `targeting/point_names.py`

Example:

```python
CAMERA_POINT = "camera"
TRANSDUCER_POINT = "transducer"
GRIPPER_POINT = "gripper"

POINT_ALIASES = {
    "camera_center": CAMERA_POINT,
}
```

Rules:
- these are canonical internal ids
- UI labels should be separate persisted values like `display_name`
- do not rename required canonical ids just to change UI text

### Where to define frame names
File: `targeting/frame_names.py`

Example:

```python
CALIBRATION_FRAME = "calibration"
PICKUP_FRAME = "pickup"
```

Rules:
- frame names are robot-system vocabulary, not engine vocabulary
- only define frames your system actually uses
- if your system supports calibration, define a navigation group named
  `CALIBRATION`
- the reusable calibration path should move through the generic engine
  `CalibrationNavigationService`, not a robot-system-specific navigation facade
- any robot-system-specific side effects before the calibration move should be
  injected explicitly as a callback, not hidden inside navigation

### Where to persist point and frame definitions
File:
- `settings/targeting.py`
- `storage/settings/targeting/definitions.json`

Recommended persisted shape:

```json
{
  "POINTS": [
    {"name": "camera", "display_name": "camera", "x_mm": 0.0, "y_mm": 0.0},
    {"name": "transducer", "display_name": "transducer", "x_mm": 0.0, "y_mm": 0.0}
  ],
  "FRAMES": [
    {
      "name": "calibration",
      "source_navigation_group": "",
      "target_navigation_group": "",
      "use_height_correction": true
    }
  ],
  "ALIASES": {
    "camera_center": "camera"
  }
}
```

Rules:
- points are measured in robot XY
- the `camera` point is the reference point
- other point offsets are derived relative to the camera point
- frames optionally define navigation-group source/target pairs
- height correction belongs to frame definitions, not to point definitions

### Where to turn settings into runtime targeting objects
Files:
- `targeting/registry.py`
- `targeting/frames.py`
- `targeting/provider.py`
- `targeting/settings_adapter.py`

Recommended runtime split:
- `registry.py`
  builds `PointRegistry`
- `frames.py`
  builds `dict[str, TargetFrame]`
- `provider.py`
  implements `RobotSystemTargetingProvider`
  and should stay focused on robot-system vocabulary only:
  - `build_point_registry()`
  - `build_frames()`
  - `get_target_options()`
  - `get_default_target_name()`
- `settings_adapter.py`
  converts your persisted targeting settings to/from the generic Robot Settings
  targeting editor payload

Goal:
- `BaseRobotSystem.get_shared_vision_resolver()` can build and cache one shared resolver
- `build_robot_system_jog_service(robot_system, ...)` can build a generic jog service using the same definitions
- the generic Robot Settings application can edit your points and frames without becoming system-specific
- the shared base layer owns:
  - homography transformer creation
  - camera-to-TCP offset application
  - `VisionTargetResolver` assembly
  - jog pose resolver assembly

### Shared base helpers you should use

For vision targeting:

```python
transformer, resolver = robot_system.get_shared_vision_resolver()
```

For jog:

```python
jog_service = build_robot_system_jog_service(robot_system)
```

When targeting definitions change:

```python
robot_system.invalidate_shared_vision_resolver()
```

This ensures the next resolver request is rebuilt from the updated settings.

### Robot Settings targeting integration

If your system uses the generic Robot Settings application for point/frame editing:

1. persist your targeting under a robot-system-specific `SettingsID`
2. implement `targeting/settings_adapter.py`
3. pass these into `RobotSettingsApplicationService`:
   - `targeting_key`
   - `targeting_to_editor`
   - `targeting_from_editor`
4. install your targeting provider in `on_start()`

This keeps:
- the Robot Settings application reusable
- the editor payload generic
- the real persisted structure owned by the robot system

---

## Providers

Current reusable provider patterns:
- targeting provider
- calibration provider
- height-measuring provider

Rule:
- if the logic is generic and only the dependencies differ, create a provider
- do not move robot-system-specific builders into `BaseRobotSystem`

---

## Shared Default Builders

Some service builders should be reused directly instead of being recopied into each robot system.

### Robot

`IRobotService` has a shared default builder.

Prerequisites:
- the platform robot object is provided to `SystemBuilder.with_robot(...)`

Declaration:

```python
ServiceSpec(ServiceID.ROBOT, IRobotService, required=True, description="Motion and lifecycle control")
```

### Navigation

`NavigationService` has a shared default builder.

Prerequisites:
- declare `CommonSettingsID.ROBOT_CONFIG`

Declaration:

```python
ServiceSpec(ServiceID.NAVIGATION, NavigationService, required=True, description="Named group navigation")
```

### Tool

`IToolService` has a shared default builder.

Prerequisites:
- declare `CommonSettingsID.TOOL_CHANGER_CONFIG`
- declare `CommonSettingsID.ROBOT_CONFIG`

Declaration:

```python
ServiceSpec(ServiceID.TOOLS, IToolService, required=False, description="Tool manager")
```

### Vision

`IVisionService` has a shared default builder.

Prerequisites:
- declare `CommonSettingsID.VISION_CAMERA_SETTINGS`
- use the standard robot-system storage layout

What the default builder does:
- reads the camera settings repo
- stores calibration/runtime vision data under:
  - `storage/settings/vision/data`
- creates `VisionService`

Declaration:

```python
ServiceSpec(ServiceID.VISION, IVisionService, required=False, description="Vision pipeline")
```

and do not need a custom `build_vision_service(ctx)` at all.

Only add a custom builder if:
- your system uses a different vision implementation
- your settings shape is different
- your runtime storage layout is intentionally different

---

## Minimal Checklist

1. Copy `ROBOT_SYSTEM_BLUEPRINT/` to `my_system/`
2. Rename all identifiers
3. Fill `metadata`, `shell`, `settings_specs`, `services`
4. Create `ServiceID` and `SettingsID`
5. Create settings serializers and default JSON files
6. Reuse shared default builders where possible
7. Implement `on_start()` / `on_stop()`
8. Add provider-based shared services if needed
9. Add targeting names/settings/provider/adapter if the system needs targeting
10. Wire applications in `application_wiring.py`
11. Use standardized storage helpers from `BaseRobotSystem`
12. Add translations under `storage/translations/`
13. Register the robot system in bootstrap when ready

---

## Common Mistakes

- Hardcoding package paths inside `application_wiring.py`
- Putting robot-system-specific service assembly into `BaseRobotSystem`
- Using strings everywhere instead of `ServiceID` / `SettingsID`
- Mixing process-specific settings into targeting settings
- Defining point labels as canonical point ids
- Creating multiple independent `VisionTargetResolver` instances instead of using `get_shared_vision_resolver()`
- Hardcoding jog target combos in views instead of using the shared jog service
- Rebuilding shared provider-based services inside application wiring instead of `on_start()`
- Forgetting the Robot Settings targeting adapter when enabling the generic targeting tab

---

## TODO Guide

When copying this blueprint, search for:

```text
TODO:
```

Those comments mark the minimum set of edits needed to make the new robot system real.
