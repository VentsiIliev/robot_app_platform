# `src/engine/robot/safety/` — Safety Checker

The `safety` package implements the workspace bounds enforcement that gates every motion command. `SafetyChecker` is the concrete implementation of `ISafetyChecker` and is called by `MotionService` before forwarding any position to the robot SDK.

---

## Class Diagram

```
ISafetyChecker (ABC)
       │
       └── SafetyChecker
                 │
                 │ reads from (optional)
                 └── ISettingsService → RobotSettings.safety_limits
```

---

## API Reference

### `SafetyChecker`

**File:** `safety_checker.py`

```python
class SafetyChecker(ISafetyChecker):
    def __init__(self, settings_service=None): ...
    def is_within_safety_limits(self, position: List[float]) -> bool: ...
```

#### `is_within_safety_limits(position) → bool`

Checks whether the target Cartesian position is within the configured workspace bounds.

**Logic:**

```
if position is empty or has fewer than 3 elements:
    return False            ← invalid position

if settings_service is None:
    return True             ← no settings → fail-safe (motion allowed)

config = settings_service.get("robot_config")
limits = config.safety_limits

if limits is None:
    return True             ← no limits configured → motion allowed

x, y, z = position[0], position[1], position[2]
return (
    limits.x_min <= x <= limits.x_max and
    limits.y_min <= y <= limits.y_max and
    limits.z_min <= z <= limits.z_max
)

on any exception:
    log warning → return True   ← exception → fail-safe (motion allowed)
```

Only the translational axes (x, y, z) are checked. Rotation axes (rx, ry, rz) are not checked even if `SafetyLimits` contains rotation bounds.

---

## Data Flow

```
MotionService.move_ptp(position, ...)
        │
        │  safety.is_within_safety_limits(position)
        ▼
SafetyChecker
        │
        ├─ settings_service is None? → return True (motion allowed)
        │
        ├─ settings_service.get("robot_config") → RobotSettings
        │       └─ .safety_limits → SafetyLimits
        │
        ├─ x_min ≤ x ≤ x_max?
        ├─ y_min ≤ y ≤ y_max?
        └─ z_min ≤ z ≤ z_max?
                │
                ├─ all True → return True (motion allowed)
                └─ any False → return False (motion blocked)

MotionService (on False):
    log warning "move_ptp blocked by safety limits"
    return False                        ← no motion command sent to robot
```

---

## Default Safety Limits

From `SafetyLimits` defaults in `robot_settings.py`:

| Axis | Min (mm) | Max (mm) |
|------|---------|---------|
| X | −500 | 500 |
| Y | −500 | 500 |
| Z | 100 | 800 |

---

## Usage Example

```python
from src.engine.robot.safety.safety_checker import SafetyChecker

# Without settings (fail-safe mode — all positions allowed)
checker = SafetyChecker()
print(checker.is_within_safety_limits([0.0, 0.0, 300.0, 180.0, 0.0, 0.0]))  # True

# With settings
checker = SafetyChecker(settings_service=settings_service)
print(checker.is_within_safety_limits([0.0, 0.0, 50.0, 0.0, 0.0, 0.0]))   # False (z < 100)
print(checker.is_within_safety_limits([0.0, 0.0, 300.0, 0.0, 0.0, 0.0]))  # True
```

---

## Design Notes

### Fail-Safe Behavior

`SafetyChecker` is intentionally **permissive** when configuration is unavailable:

- No `settings_service` → **motion allowed** (useful for test environments and standalone runners)
- `safety_limits` attribute missing → **motion allowed**
- Exception during limit check → **motion allowed** (logs a warning)

This is the correct fail-safe for a development platform where the safety system is optional and the physical robot is not always connected.

### What Is Not Checked

- **Rotation bounds** (rx, ry, rz): `SafetyLimits` stores rotation min/max values, but `SafetyChecker` only validates x, y, z.
- **Joint limits**: These are enforced by the robot firmware (FairinoRobot SDK), not by this layer.
- **Velocity/acceleration limits**: `GlobalMotionSettings` has these values, but they are not enforced here.

### Singleton-Free

`SafetyChecker` has no singleton or class-level state. Each `MotionService` receives its own instance, configured with (or without) a settings service.
