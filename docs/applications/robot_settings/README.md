# `src/applications/robot_settings/` — Robot Settings Application

The `robot_settings` application provides a GUI for editing all robot configuration: network settings, global motion parameters, TCP offsets, safety limits, offset direction map, movement groups (named positions), and calibration parameters. It now also exposes both:
- the standalone camera-TCP offset calibration routine settings
- the optional camera-TCP offset capture settings used inside the main robot calibration pipeline
- optional robot-system-specific targeting definitions such as named points and named frames

This is intended to be the shared robot-settings application for any robot system that adopts the common platform contracts:
- `CommonSettingsID.ROBOT_CONFIG`
- `CommonSettingsID.ROBOT_CALIBRATION`
- `NavigationService`

Optional integrations:
- `CommonSettingsID.TOOL_CHANGER_CONFIG` for slot/tool display
- robot-system-specific targeting load/save adapters for the `Targeting` tab

The shared `CameraSettings` application follows the same model:
- `CommonServiceID.VISION`
- `CommonSettingsID.VISION_CAMERA_SETTINGS`

---

## Architecture

```
RobotSettingsApplication(IApplication)
  └─ RobotSettingsFactory(ApplicationFactory).build(settings_service)
       ├─ RobotSettingsModel          ← load/save RobotSettings + RobotCalibrationSettings
       ├─ RobotSettingsView           ← multi-tab SettingsView + raw tabs for movement groups and targeting definitions
       └─ RobotSettingsController     ← save_requested → model.save(flat, movement_groups, targeting_definitions)
```

One service interface:

```
IRobotSettingsService   ← load_config / save_config / load_calibration / save_calibration / optional targeting-definition callbacks
```

---

## Class Summary

| Class | Role |
|-------|------|
| `RobotSettingsApplication(IApplication)` | Bootstrap entry point; constructs `RobotSettingsApplicationService` + factory |
| `RobotSettingsFactory(ApplicationFactory)` | Standard 3-method override |
| `IRobotSettingsService` | ABC: load/save `RobotSettings` + `RobotCalibrationSettings` |
| `RobotSettingsApplicationService` | Wraps `ISettingsService`; always handles robot/calibration settings and can optionally adapt robot-system targeting definitions |
| `RobotSettingsModel` | Holds both configs plus optional targeting-definition editor data; `save()` writes all active sections |
| `RobotSettingsMapper` | `to_flat_dict / from_flat_dict` for `RobotSettings` |
| `RobotCalibrationMapper` | `to_flat_dict / from_flat_dict` for `RobotCalibrationSettings` |
| `RobotSettingsView` | schema-driven tabs + raw tabs for movement groups and targeting definitions |
| `RobotSettingsController` | `save_requested` → reads view flat + movement groups + targeting definitions → `model.save()` |

---

## Data Flow

### Load

```
controller.load()
  → config, calibration, targeting_definitions = model.load()
  → view.load_config(config)            ← SettingsView populates all tabs
  → view.load_movement_groups(config.movement_groups)
  → view.load_targeting_definitions(targeting_definitions)
```

### Save

```
User clicks Save
  → RobotSettingsView.save_requested.emit(values_dict)
  → RobotSettingsController._on_save(_values)
  → flat = view.get_values()
  → movement_groups = view.get_movement_groups()
  → targeting_definitions = view.get_targeting_definitions()
  → model.save(flat, movement_groups, targeting_definitions)
       ├─ RobotSettingsMapper.from_flat_dict(flat, _config) → updated RobotSettings
       │    updated.movement_groups = movement_groups
       │    settings_service.save("robot_config", updated)
       └─ RobotCalibrationMapper.from_flat_dict(flat, _calibration) → updated RobotCalibrationSettings
            settings_service.save("robot_calibration", updated_calib)
```

---

## View Tabs

| Tab | Schema Groups | Fields |
|-----|--------------|--------|
| General | `ROBOT_INFO_GROUP`, `GLOBAL_MOTION_GROUP`, `TCP_STEP_GROUP`, `OFFSET_DIRECTION_GROUP` | IP, tool, user, global vel/acc, jog step, TCP steps, direction map |
| Safety | `SAFETY_LIMITS_GROUP` | x/y/z/rx/ry/rz min+max bounds |
| Movement Groups | `MovementGroupsTab` (raw) | Named positions: name, position string, vel, acc |
| Targeting | `TargetingDefinitionsTab` (raw) | Generic named points and frames supplied by the active robot system |
| Calibration | `CALIBRATION_ADAPTIVE_GROUP`, `CALIBRATION_MARKER_GROUP`, `CALIBRATION_AXIS_MAPPING_GROUP`, `CALIBRATION_CAMERA_TCP_GROUP` | Adaptive movement params, marker/z settings, axis-mapping settings, standalone camera-TCP settings, and optional in-main-calibration TCP capture settings |

---

## Usage Example

```python
from src.applications.robot_settings.robot_settings_application import RobotSettingsApplication


# In robot vision_service wiring:
def _build_robot_settings(robot_system):
    return RobotSettingsApplication(robot_system._settings_service)


# Standalone (requires ISettingsService stub):
widget = RobotSettingsFactory().build(RobotSettingsApplicationService(settings_service))
```

---

## Design Notes

- **Two mappers, one `save()`**: `RobotSettings` and `RobotCalibrationSettings` are persisted separately under different keys, but the view presents them in one unified flat dict. The model's `save()` calls both mappers and writes both files in one user action.
- **`movement_groups` is not in the flat dict**: `MovementGroupsTab` has its own `get_values() → Dict[str, MovementGroup]` method. The controller reads both `get_values()` and `get_movement_groups()` separately and passes them to `model.save()`.
- **Reusable app, robot-system adapters**: The application remains generic. Robot-system-specific targeting structures are converted to and from the editor payload in the wiring/service layer.
- **Standard shared app**: If a robot system uses the shared `RobotSettings` and `RobotCalibrationSettings` engine models, it should reuse this application rather than creating a robot-system-specific copy.
- **No broker subscriptions**: `RobotSettingsController.stop()` is a no-op. The application does not receive live data.

→ Subpackages: [service/](service/README.md) · [model/](model/README.md) · [view/](view/README.md) · [controller/](controller/README.md)
