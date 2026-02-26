# `src/engine/robot/drivers/` — Driver System Overview

The `drivers` package contains concrete implementations of `IRobot` — the lowest-level interface that talks directly to physical or simulated robot hardware. Each driver translates `IRobot` method calls into vendor-specific SDK calls.

---

## Structure

```
drivers/
├── fairino/
│   ├── fairino_robot.py   ← FairinoRobot: production driver (FairinoRobot SDK)
│   └── test_robot.py      ← TestRobotWrapper: full mock for development
└── zeroerr_robot.py       ← (empty placeholder)
```

---

## Interface Contract

All drivers implement `IRobot`:

```
IRobot (ABC)
  move_ptp(position, tool, user, vel, acc) → int
  move_linear(position, tool, user, vel, acc, blend_radius) → int
  start_jog(axis, direction, step, vel, acc) → int
  stop_motion() → int
  get_current_position() → List[float]   # [x, y, z, rx, ry, rz]
  get_current_velocity() → float
  get_current_acceleration() → float
  enable() → None
  disable() → None
```

Return convention: `0` = success, non-zero = vendor error code.

---

## Available Drivers

| Driver | File | Target |
|--------|------|--------|
| `FairinoRobot` | `fairino/fairino_robot.py` | FairinoRobot SDK over TCP/IP |
| `TestRobotWrapper` | `fairino/test_robot.py` | In-process mock (dev/test) |

→ See [fairino/README.md](fairino/README.md) for full documentation.

---

## Swapping Drivers

To use a different physical robot, create a new class that implements `IRobot` and pass it to `create_robot_service()`. No changes are required anywhere else in the stack.

```python
class MyCustomRobot(IRobot):
    def move_ptp(self, position, tool, user, vel, acc) -> int:
        # Call your SDK here
        return 0
    # ... implement remaining methods

robot_service = create_robot_service(
    robot=MyCustomRobot(),
    messaging_service=messaging,
)
```
