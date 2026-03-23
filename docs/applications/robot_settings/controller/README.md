# `src/applications/robot_settings/controller/` — Robot Settings Controller

---

## `RobotSettingsController`

**File:** `robot_settings_controller.py`

```python
class RobotSettingsController(IApplicationController):
    def __init__(self, model: RobotSettingsModel, view: RobotSettingsView): ...
    def load(self) -> None: ...
    def stop(self) -> None: ...
```

Wires the view's `save_requested` signal to the model. No broker subscriptions.

---

## Signal Wiring

| View signal | Controller slot | Action |
|-------------|----------------|--------|
| `save_requested(dict)` | `_on_save(values)` | Read flat settings + movement groups + targeting definitions from view, call `model.save()` |
| `destroyed` | `stop()` | No-op (no subscriptions to clean up) |

---

## `load()` Sequence

```
load()
  → config, calibration, targeting_definitions = model.load()
  → view.load_config(flat_config_and_calibration)
  → view.load_movement_groups(config.movement_groups)
  → view.load_targeting_definitions(targeting_definitions)
```

Note: calibration fields still appear in the "Calibration" tab via the unified flat dict assembled from `RobotSettingsMapper` and `RobotCalibrationMapper`. Targeting definitions are loaded separately into the raw targeting tab.

---

## `_on_save()` Sequence

```
_on_save(_values)               ← _values is the dict from save_requested, ignored
  → flat            = view.get_values()
  → movement_groups = view.get_movement_groups()
  → targeting       = view.get_targeting_definitions()
  → model.save(flat, movement_groups, targeting)
       ├─ RobotSettingsMapper.from_flat_dict(flat, _config) → updated_config
       │    updated_config.movement_groups = movement_groups
       │    service.save_config(updated_config)
       └─ RobotCalibrationMapper.from_flat_dict(flat, _calibration) → updated_calib
            service.save_calibration(updated_calib)
       └─ service.save_targeting_definitions(targeting)
```

---

## Design Notes

- **`stop()` is a no-op**: `RobotSettingsController` has no broker subscriptions and no background threads. `stop()` satisfies the `IApplicationController` contract but does nothing.
- **Calibration fields share the flat dict**: The view's `SettingsView` renders calibration fields as part of the same form. `get_values()` returns them all in one dict. The mapper knows which keys belong to calibration and which to robot config.
- **Targeting definitions are separate from the flat dict**: The raw targeting tab returns a generic payload with named points and frames. The controller saves it alongside the normal robot/calibration settings, but the app layer stays robot-system agnostic.
- **`view.get_values()` not `_values`**: The `_values` argument from `save_requested` is discarded. The controller calls `view.get_values()` to get the current state of all fields, ensuring the latest values are read (not just those that triggered the signal).
