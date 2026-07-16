# Paint Process Settings UI Plan

## Goal

Create a standalone MVC application for configuring the Paint process knobs that currently live in:

```text
src/robot_systems/paint/processes/paint/config.py
```

The screen must follow the existing application architecture, use the same visual style as the rest of the platform, support localization from the start, persist values through the established settings system, and update the running Paint process without requiring a full system restart.

## Current Progress

Status as of the first runtime wiring pass:

| Area | Status | Notes |
| --- | --- | --- |
| Standalone MVC app | Done | `PaintProcessSettings` app package exists with factory, model, view, controller, service interface, stub service, mapper, schema, and standalone runner. |
| UI preview runner | Done | `example_usage.py` launches the screen with an in-memory stub service. |
| UI style | Done for first pass | Uses `KeyboardSettingsView`, `SettingGroup`, `SettingField`, and the shared settings view styling. |
| UI grouping | Done for first pass | Values are grouped into Process, Motion Speeds, Distances & Offsets, Paint Path, Cleanup, and Diagnostics tabs. |
| Localization structure | Partially done | Schema labels are built through translation helpers and the view handles language change. Real catalog entries still need to be added. |
| Settings persistence | Done | Added `SettingsID.PAINT_PROCESS_CONFIG`, `PaintProcessConfigSerializer`, and `SettingsSpec(..., "paint/process.json")`. Defaults come from existing `PAINT_PROCESS_CONFIG`. |
| Service folder wiring | Done | `PaintProcessSettings` is registered in Paint system folder `2` / Service. |
| Runtime config service | Done | Added `PaintProcessConfigService` as the single runtime access point. UI saves update this service snapshot. |
| Runtime wiring - motion speeds | Done for first pass | Pickup, cleanup, dropoff release-align, pre-dropoff unwind, and calibration-return speed values read from the runtime settings service. |
| Runtime wiring - cleanup settings | Done | Cleanup enable flag, second-pass flag, spacing, cleanup Z offset, and second-pass pivot Z offset read from the per-cycle runtime snapshot. |
| Runtime wiring - distance/offset settings | Mostly done | Pickup contact offset, approach offset, lift clearance, and cleanup offsets read from the per-cycle runtime snapshot. `default_z_mm` is not wired because it was not part of the existing runtime calculation path. |
| Runtime wiring - diagnostics settings | Done | Pivot debug plot, execution motion trace, and trace sample period read from the per-cycle runtime snapshot. |
| Runtime wiring - remaining non-speed knobs | Not started | Geometry, mode selection, vacuum, target-point behavior, and queue behavior still use the existing config path. |

Implemented files include:

```text
src/robot_systems/paint/applications/paint_process_settings/
src/robot_systems/paint/processes/paint/paint_process_config_serializer.py
src/robot_systems/paint/processes/paint/paint_process_config_service.py
```

The current runtime rule is:

```text
UI save -> PaintProcessConfigService.save(...) -> in-memory snapshot updated
Paint cycle start -> PaintWorkpiecePathExecutor reads one config snapshot
Running cycle -> keeps its start snapshot
Next cycle -> uses newly saved motion speeds, cleanup settings, pickup offsets, and diagnostics settings
```

## Application Shape

Application name:

```text
PaintProcessSettings
```

Suggested location:

```text
src/robot_systems/paint/applications/paint_process_settings/
```

Suggested shell folder:

```text
SERVICE
```

This should be a robot-system-specific application because the settings are specific to the Paint system and should not leak into shared platform code.

## Required Architecture

Use the same standalone MVC pattern as the existing settings applications:

```text
View signal -> Controller -> Model -> Service -> SettingsService
```

Proposed files:

```text
src/robot_systems/paint/applications/paint_process_settings/
  __init__.py
  paint_process_settings_factory.py
  mapper.py
  controller/
    paint_process_settings_controller.py
  model/
    paint_process_settings_model.py
  service/
    i_paint_process_settings_service.py
    paint_process_settings_application_service.py
    stub_paint_process_settings_service.py
  view/
    paint_process_settings_schema.py
    paint_process_settings_view.py
  example_usage.py
```

The app must not import or control the Paint process directly. It should only load and save settings through its service interface.

## Layering Rules

The implementation must preserve the established repository architecture:

```text
Platform / Engine
  -> RobotSystem
    -> Application
```

Do not move Paint-specific behavior into `src/engine/`, and do not make shared applications depend on Paint runtime classes.

### Ownership Boundaries

| Area | Responsibility for this feature |
| --- | --- |
| `src/engine/` | Existing settings infrastructure only. No Paint-specific config or UI code should be added here. |
| `src/shared_contracts/` | Only use if a truly cross-system topic/payload/contract is needed. Paint-only settings should not be added here. |
| `src/robot_systems/paint/` | Owns Paint process config, serializer, runtime settings service, runtime integration, and Paint-specific application wiring. |
| `src/robot_systems/paint/applications/paint_process_settings/` | Owns the standalone MVC screen for editing Paint process settings. |
| `pl_gui/` | Reused for existing UI widgets/styles only. Do not modify it for this feature unless a shared UI bug is discovered and explicitly accepted. |

### Application Layer Import Rules

The new app should follow the same import discipline as other applications:

| File / Layer | May import | Must not import |
| --- | --- | --- |
| `i_paint_process_settings_service.py` | stdlib, Paint settings data type if needed | Qt, `ISettingsService`, robot services, process classes |
| `paint_process_settings_application_service.py` | Paint process config service interface | Qt, view, controller, robot services |
| `paint_process_settings_model.py` | service interface, stdlib | Qt, view, controller, `ISettingsService`, Paint process runtime |
| `paint_process_settings_view.py` | Qt, `KeyboardSettingsView`, `SettingGroup`, `SettingField`, shared styles | model, service, Paint process runtime |
| `paint_process_settings_controller.py` | model, view, optional messaging if needed | `ISettingsService`, robot services, Paint process runtime |
| `paint_process_settings_factory.py` | model, view, controller, service interface | broker directly, robot system internals |

The service is the only application layer allowed to touch persistence. The controller should not call `SettingsService` or reach into `PaintRobotSystem`.

### Robot System Integration Boundary

Paint system wiring should happen in:

```text
src/robot_systems/paint/application_wiring.py
src/robot_systems/paint/paint_robot_system.py
```

The application factory should receive an application service that already has the dependencies it needs. The UI application must not receive the whole `PaintRobotSystem` object.

Correct wiring shape:

```python
service = PaintProcessSettingsApplicationService(
    process_config_service=robot_system._paint_process_config_service,
)
return WidgetApplication(
    widget_factory=lambda _ms: PaintProcessSettingsFactory().build(service)
)
```

Avoid passing `robot_system` into the app, model, view, or controller.

### Runtime Config Boundary

Paint runtime code may depend on one Paint-owned process config service, not on the UI application.

Allowed:

```text
paint process runtime -> IPaintProcessConfigService -> SettingsService
```

Not allowed:

```text
paint process runtime -> PaintProcessSettingsController/View/App
```

This keeps production execution independent from the operator screen while still allowing saved values to be refreshed live.

The runtime config service should be the only object passed into Paint process runtime services for reading Paint process knobs. Do not pass raw config dictionaries, individual knob values, or the whole `PaintRobotSystem`.

Recommended interface shape:

```python
class IPaintProcessConfigService(Protocol):
    def get_snapshot(self) -> PaintProcessConfig: ...
    def save(self, settings: PaintProcessConfig) -> None: ...
    def reload(self) -> PaintProcessConfig: ...
```

The concrete implementation can be named:

```text
PaintProcessConfigService
```

Suggested location:

```text
src/robot_systems/paint/processes/paint/paint_process_config_service.py
```

Both the UI application service and the Paint runtime should depend on this service interface:

```text
PaintProcessSettingsApplicationService -> IPaintProcessConfigService
Paint runtime services                  -> IPaintProcessConfigService
```

The runtime config service must not import Qt or the settings UI application.

## Persistence

Use the established settings repository pattern:

1. Add a Paint-specific settings enum:

```python
class SettingsID(str, Enum):
    PAINT_PROCESS_CONFIG = "paint_process_config"
```

2. Add a settings serializer for the Paint process config.

3. Register the settings in `PaintRobotSystem.settings_specs`:

```python
SettingsSpec(
    SettingsID.PAINT_PROCESS_CONFIG,
    PaintProcessConfigSerializer(),
    "paint/process.json",
)
```

4. Store values under:

```text
src/robot_systems/paint/storage/settings/paint/process.json
```

Do not add custom JSON read/write code inside the application. Persistence should go through the Paint process config service, which internally uses `ISettingsService.get()` and `ISettingsService.save()`.

## Runtime Config Rule

The Paint process must not use stale values.

Do not keep using the module-level `PAINT_PROCESS_CONFIG` as the live runtime source of truth. Treat it as defaults only.

Add a runtime config service:

```text
src/robot_systems/paint/processes/paint/paint_process_config_service.py
```

Expected responsibility:

```text
SettingsService -> PaintProcessConfigService -> Paint process runtime
```

The config service should:

- load the persisted Paint process settings
- keep the latest valid snapshot in memory
- expose `get_snapshot()`
- expose `reload()`, `save(settings)`, or `update(settings)`
- be shared by the Paint system services that need config

The UI save flow should:

```text
save settings through PaintProcessConfigService
update/reload the service snapshot
notify runtime consumers if needed
```

Recommended behavior:

```text
changes apply to the next Paint cycle
```

Avoid mutating motion parameters halfway through an active robot movement. A running cycle may finish with the config snapshot it started with, while the next cycle must use the newly saved values.

## Paint Runtime Integration

`PaintRobotSystem.on_start()` should create and store:

```python
self._paint_process_config_service = PaintProcessConfigService(self._settings_service)
```

Runtime builders should receive the service instance:

```python
paint_process_config_service=self._paint_process_config_service
```

Avoid passing individual config values into constructors when those values are meant to be editable at runtime.

Places that currently depend on `PAINT_PROCESS_CONFIG` should be reviewed and moved to runtime snapshots where appropriate:

- navigation return tuning
- path preparation settings
- path executor settings
- pickup/dropoff behavior
- edge cleanup settings
- pivot/motion-plane settings
- diagnostics/debug flags

## UI Style Requirements

Use the shared settings UI style and components:

- `KeyboardSettingsView`
- `SettingGroup`
- `SettingField`
- shared virtual keyboard behavior
- shared stylesheet constants where custom widgets are unavoidable

The view must not hard-code colors or create a separate visual style. It should look like the existing settings screens such as `CalibrationSettings`, `CameraSettings`, and `ModbusSettings`.

## Localization Requirements

Localization must be designed in from the first implementation.

Required behavior:

- static widget text uses `self.tr(...)`
- config-driven labels use `QCoreApplication.translate(...) or source_text`
- long-lived view handles `QEvent.LanguageChange`
- view exposes or calls `retranslateUi()`
- tab labels, group labels, field labels, choices, validation messages, and save messages are translatable

The schema should be built by functions, not fixed module constants, so translated labels can be regenerated:

```python
def build_paint_process_settings_tabs():
    return [
        (_t("Process"), build_process_groups()),
        (_t("Motion Speeds"), build_motion_speed_groups()),
        (_t("Distances & Offsets"), build_distance_offset_groups()),
        (_t("Paint Path"), build_paint_path_groups()),
        (_t("Cleanup"), build_cleanup_groups()),
        (_t("Diagnostics"), build_diagnostics_groups()),
    ]
```

## UI Grouping

The screen should be easy for an operator or developer to scan. Group values logically by purpose, not by Python dataclass names.

Recommended tabs:

| Tab | Sections | Purpose |
| --- | --- | --- |
| Process | General, Targeting, Execution Mode | High-level process behavior and selected mode |
| Motion Speeds | Pickup, Paint, Cleanup, Dropoff, Return | All velocity and acceleration knobs in one place |
| Distances & Offsets | Pickup Heights, Contact Offsets, Cleanup Offsets | Physical distances and clearances |
| Paint Path | Pivot Setup, Direction, Contact Side, Axis Alignment | Geometry and head-orientation behavior |
| Cleanup | Cleanup Enable, Cleanup Passes, Cleanup Spacing | Post-paint cleanup behavior |
| Diagnostics | Debug Plots, Motion Trace, Sampling | Debug and trace controls |

### Motion Speeds Tab

Group all velocity and acceleration values into this tab:

```text
Motion Speeds
  Pickup
    Approach velocity
    Approach acceleration
    Descend velocity
    Descend acceleration
    Lift/align velocity
    Lift/align acceleration
    Change-plane velocity
    Change-plane acceleration
    Stage transition velocity
    Stage transition acceleration
    First-contact velocity
    First-contact acceleration

  Paint
    Paint contact velocity
    Paint contact acceleration

  Cleanup
    Cleanup velocity
    Cleanup acceleration

  Dropoff
    Release-align velocity
    Release-align acceleration

  Return
    Joint unwind velocity
    Joint unwind acceleration
    Calibration-return velocity
    Calibration-return acceleration
```

### Distances & Offsets Tab

Group physical distances separately from speeds:

```text
Distances & Offsets
  Pickup Heights
    Default pickup Z
    Approach offset
    Contact offset
    Initial lift clearance

  Cleanup Offsets
    Cleanup Z offset
    Second-pass pivot Z offset
```

### Process Tab

High-level choices and feature flags:

```text
Process
  General
    Execution target point
    Enable vacuum pump
    Apply camera-to-TCP pickup offset
    Enable Z-shift pixel compensation

  Execution Mode
    Motion plane
    Pixel-to-mm mode
```

### Paint Path Tab

Geometry and head-orientation behavior:

```text
Paint Path
  Pivot Setup
    Pivot motion plane
    Pivot axis
    Pivot direction
    Pivot contact side
    Mirror XZ/RY execution rotation
    Pickup axis alignment sign
```

### Cleanup Tab

Post-paint cleanup behavior:

```text
Cleanup
  Enable
    Enable cleanup after XZ/RY paint
    Enable second cleanup pass

  Path
    Cleanup spacing
```

### Diagnostics Tab

Debug values that should normally remain off in production:

```text
Diagnostics
  Debug
    Enable pivot debug plot
    Enable execution motion trace
    Motion trace sample period
```

## Extensibility Requirement

Adding, editing, or removing a knob should be straightforward.

Target edit points:

1. Settings dataclass / serializer
2. Schema field in `paint_process_settings_schema.py`
3. Mapper entry in `mapper.py`

The controller and view should not need structural changes when a new field is added to an existing tab/group.

## Validation

The UI should constrain values with field-level min/max/choices where possible:

- velocity and acceleration percentages: bounded numeric fields
- booleans: checkbox/toggle fields
- modes: combo fields
- distances: double spin boxes with `mm` suffix
- trace period: double spin box with seconds suffix

Validation should prevent saving unsupported enum-like values such as unknown motion planes, target points, pivot directions, or pixel-to-mm modes.

## Save Behavior

On save:

1. Read current settings from the model.
2. Map flat UI values back to a full `PaintProcessConfig`.
3. Save through `IPaintProcessConfigService`.
4. Update the runtime config service snapshot.
5. Show a localized confirmation.

Recommended user-facing behavior:

```text
Saved. Changes will be used by the next Paint cycle.
```

If a Paint cycle is running, do not silently alter the active trajectory. The process should use a config snapshot taken at cycle start.

## Verification Plan

1. Compile touched modules:

```bash
python3 -m py_compile <new files>
```

2. Run standalone app:

```bash
python src/robot_systems/paint/applications/paint_process_settings/example_usage.py
```

3. Start full application and verify:

```bash
python src/bootstrap/main.py
```

4. Confirm the screen appears in the Service folder.

5. Save settings and confirm:

```text
src/robot_systems/paint/storage/settings/paint/process.json
```

is created or updated through `SettingsService`.

6. Change a value while the app is running and verify:

- runtime config service snapshot updates without full system restart
- the next Paint cycle uses the new value
- an already running cycle does not mutate mid-motion

7. Add focused tests for:

- serializer default/load/save round trip
- mapper flat dict round trip
- config service reload/update behavior

## Verification Completed

Completed checks so far:

```bash
python3 -m py_compile ...
```

Compiled the new app modules, Paint system wiring, runtime config service, navigation service, and affected Paint executors.

Serializer checks completed:

- `PaintProcessConfigSerializer.get_default()` matches the existing `PAINT_PROCESS_CONFIG`
- serializer round trip preserves the default config
- partial/older JSON falls back to current dataclass defaults for missing fields

Runtime service checks completed:

- `PaintProcessConfigService.save(...)` updates the in-memory snapshot
- executor can read a modified runtime snapshot
- `PaintProcessSettings` remains registered in the Service folder

Manual preview completed:

- standalone runner launched successfully after adding repo-root path setup

## Findings And Potential Issues

### 1. Remaining module-level config use

There are still many valid references to `PAINT_PROCESS_CONFIG`.

The first runtime passes intentionally moved motion-speed values and cleanup behavior first. The following areas still use the existing module-level config and should be wired in later passes:

- process geometry and pivot mode
- execution target point
- pixel-to-mm mode
- vacuum enable flag
- queue-if-busy behavior

This is intentional for incremental safety, but it means the UI currently exposes more knobs than the runtime consumes live.

### 1a. `default_z_mm` is not currently live

`PickupMotionConfig.default_z_mm` exists in `config.py` and is exposed in the UI, but the existing pickup planner did not use it in the active pickup-Z calculation.

Current runtime behavior calculates pickup Z from:

```text
robot safety z_min + workpiece height + contact_offset_mm
```

Wiring `default_z_mm` directly would change current behavior because its existing default is `200.0`. For now it is intentionally left unwired until the expected semantics are clarified:

- use as an absolute pickup Z override
- use only when no workpiece height is available
- remove it from the UI if it is obsolete
- migrate the current calculation into an explicit mode

### 2. Settings UI exposes non-live fields

The screen currently allows editing all planned fields, but only motion speeds, cleanup settings, pickup offsets, and diagnostics settings are wired into runtime behavior.

Until the remaining knobs are wired, the UI should either:

- clearly indicate which fields are live, or
- temporarily limit operator-facing fields to the Motion Speeds tab.

Otherwise an operator may save a non-speed value and expect it to affect the process immediately.

### 3. Active cycle snapshot behavior is deliberate

The Paint path executor reads one `PaintProcessConfig` snapshot at cycle start. This avoids changing velocities during an active robot sequence.

This means:

```text
saved during idle      -> next cycle uses new speed values
saved during a cycle   -> current cycle keeps old speed values
saved before return    -> current cycle still keeps old speed values
```

This is the safer behavior, but it should be reflected in operator text.

### 4. Navigation reads live values per action

`PaintNavigationService` reads navigation-return velocity/acceleration from the runtime settings service when return actions run. This is slightly different from the path executor cycle snapshot behavior.

This is acceptable for standalone navigation actions, but if strict cycle-level immutability is required for every return move, navigation return should also receive a per-cycle snapshot from the process instead of reading the service directly.

### 5. Queue behavior intentionally not live yet

`unwind_queue_if_busy` is still treated as existing behavior, not as part of the first live wiring pass.

Reason: the first pass is limited to motion speeds only. Changing queue behavior can affect sequencing semantics and should be reviewed separately.

### 6. Paint process config service is Paint-owned

The runtime service lives under the Paint process package and depends on `SettingsService`. The UI service depends on this Paint-owned runtime service.

This keeps the UI from talking directly to `SettingsService`, but the service interface currently lives with its concrete implementation. If more implementations are needed, the interface may be split into a dedicated interface file.

### 7. Real localization catalogs are still missing

The code structure supports translation, but actual translation keys/catalog entries still need to be added under the Paint system translations folder.

Without catalog entries, the UI will display source English text.

### 8. Documentation follow-up required

This work touches `src/robot_systems/paint`. The robot-system documentation should be reviewed once runtime wiring is complete.

## Documentation Impact

This change touches `src/robot_systems/paint`, so the robot-system docs should be reviewed when implementation is completed.

If the schema-driven settings approach becomes a shared pattern beyond Paint, update application documentation as well.
