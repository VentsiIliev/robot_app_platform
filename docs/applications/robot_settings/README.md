# `src/applications/robot_settings/` — Robot Settings Application

The `robot_settings` application provides a GUI for editing all robot configuration: network settings, global motion parameters, TCP offsets, safety limits, offset direction map, movement groups (named positions), and calibration parameters. It follows the standard application MVC pattern.

---

## Architecture

```
RobotSettingsApplication(IApplication)
  └─ RobotSettingsFactory(ApplicationFactory).build(settings_service)
       ├─ RobotSettingsModel          ← load/save RobotSettings + RobotCalibrationSettings
       ├─ RobotSettingsView           ← multi-tab SettingsView + MovementGroupsTab
       └─ RobotSettingsController     ← save_requested → model.save(flat, movement_groups)
```

One service interface:

```
IRobotSettingsService   ← load_config / save_config / load_calibration / save_calibration
```

---

## Class Summary

| Class | Role |
|-------|------|
| `RobotSettingsApplication(IApplication)` | Bootstrap entry point; constructs `RobotSettingsApplicationService` + factory |
| `RobotSettingsFactory(ApplicationFactory)` | Standard 3-method override |
| `IRobotSettingsService` | ABC: load/save `RobotSettings` + `RobotCalibrationSettings` |
| `RobotSettingsApplicationService` | Wraps `ISettingsService`; keys `"robot_config"` + `"robot_calibration"` |
| `RobotSettingsModel` | Holds both configs; `save()` maps flat dict + movement groups → both configs |
| `RobotSettingsMapper` | `to_flat_dict / from_flat_dict` for `RobotSettings` |
| `RobotCalibrationMapper` | `to_flat_dict / from_flat_dict` for `RobotCalibrationSettings` |
| `RobotSettingsView` | 4-tab `SettingsView` + movement groups raw tab |
| `RobotSettingsController` | `save_requested` → reads view flat + movement groups → `model.save()` |

---

## Data Flow

### Load

```
controller.load()
  → config, calibration = model.load()
  → view.load_config(config)            ← SettingsView populates all tabs
  → view.load_movement_groups(config.movement_groups)
```

### Save

```
User clicks Save
  → RobotSettingsView.save_requested.emit(values_dict)
  → RobotSettingsController._on_save(_values)
  → flat = view.get_values()
  → movement_groups = view.get_movement_groups()
  → model.save(flat, movement_groups)
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
| Calibration | `CALIBRATION_ADAPTIVE_GROUP`, `CALIBRATION_MARKER_GROUP` | Adaptive movement params, z target, required IDs |

---

## Usage Example

```python
from src.applications.robot_settings.robot_settings_application import RobotSettingsApplication


# In robot system wiring:
def _build_robot_settings(robot_system):
    return RobotSettingsApplication(robot_system._settings_service)


# Standalone (requires ISettingsService stub):
widget = RobotSettingsFactory().build(RobotSettingsApplicationService(settings_service))
```

---

## Design Notes

- **Two mappers, one `save()`**: `RobotSettings` and `RobotCalibrationSettings` are persisted separately under different keys, but the view presents them in one unified flat dict. The model's `save()` calls both mappers and writes both files in one user action.
- **`movement_groups` is not in the flat dict**: `MovementGroupsTab` has its own `get_values() → Dict[str, MovementGroup]` method. The controller reads both `get_values()` and `get_movement_groups()` separately and passes them to `model.save()`.
- **No broker subscriptions**: `RobotSettingsController.stop()` is a no-op. The application does not receive live data.

→ Subpackages: [service/](service/README.md) · [model/](model/README.md) · [view/](view/README.md) · [controller/](controller/README.md)
