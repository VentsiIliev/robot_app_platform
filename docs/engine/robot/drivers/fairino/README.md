# `src/engine/robot/drivers/fairino/` — FairinoRobot Driver

This package contains the production driver for the FairinoRobot collaborative arm (`FairinoRobot`) and a full in-process mock (`TestRobotWrapper`) for development and testing without physical hardware.

---

## Class Diagram

```
IRobot (ABC)
  │
  ├── FairinoRobot          ← production driver; wraps FairinoRobot SDK RPC
  │       └── robot: TestRobotWrapper   ← currently wired (replace for production)
  │
  └── TestRobotWrapper      ← mock; returns safe dummy values for all calls
```

---

## API Reference

### `FairinoRobot`

**File:** `fairino_robot.py`

Production `IRobot` implementation that wraps the FairinoRobot SDK.

```python
class FairinoRobot(IRobot):
    def __init__(self, ip: str): ...
```

**Current state:** `FairinoRobot.__init__` creates a `TestRobotWrapper` internally (`self.robot = TestRobotWrapper()`). Replace this line with `Robot.RPC(self.ip)` to connect to real hardware:

```python
# In fairino_robot.y_pixels, __init__:
# Replace:
self.robot = TestRobotWrapper()
# With:
import fairino
self.robot = fairino.Robot.RPC(self.ip)
```

| `IRobot` Method | SDK Call | Notes |
|----------------|----------|-------|
| `move_ptp(position, tool, user, vel, acc)` | `robot.MoveCart(position, tool, user, vel=vel, acc=acc)` | Returns 0 if SDK returns `None` |
| `move_linear(position, tool, user, vel, acc, blend_radius)` | `robot.MoveL(position, tool, user, vel=vel, acc=acc, blendR=blend_radius)` | |
| `start_jog(axis, direction, step, vel, acc)` | `robot.StartJOG(ref=4, nb=axis.value, dir=direction.value, vel=vel, acc=acc, max_dis=step)` | `ref=4` = Cartesian TCP frame |
| `stop_motion()` | `robot.StopMotion()` | |
| `get_current_position()` | `robot.GetActualTCPPose()` | Returns `result[1]` (list); `[]` on error |
| `get_current_velocity()` | — | Returns `0.0` (not supported by SDK) |
| `get_current_acceleration()` | — | Returns `0.0` (not supported by SDK) |
| `enable()` | `robot.RobotEnable(1)` | |
| `disable()` | `robot.RobotEnable(0)` | |

**Additional methods** (not in `IRobot`, used by application-level code):

| Method | SDK Call | Description |
|--------|----------|-------------|
| `execute_trajectory(path, rx, ry, rz, vel, acc, blocking)` | `robot.execute_path(...)` | Execute a multi-point trajectory |
| `reset_all_errors()` | `robot.ResetAllError()` | Clear all SDK error flags |
| `set_digital_output(port_id, value)` | `robot.SetDO(port_id, value)` | Control digital I/O port |

---

### `TestRobotWrapper`

**File:** `test_robot.py`

A complete in-process mock of `IRobot`. All motion commands return `0` (success) immediately. State queries return safe dummy values.

```python
class TestRobotWrapper(IRobot):
    def __init__(self): ...                          # prints "TestRobot initialized"
    def move_ptp(self, ...) -> int: return 0
    def move_linear(self, ...) -> int: return 0
    def start_jog(self, ...) -> int: return 0
    def stop_motion(self) -> int: return 0
    def get_current_position(self) -> List[float]: return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    def get_current_velocity(self) -> float: return 0.0
    def get_current_acceleration(self) -> float: return 0.0
    def enable(self) -> None: pass
    def disable(self) -> None: pass
```

Also stubs the raw SDK methods used internally by `FairinoRobot` (for when `FairinoRobot` delegates to `TestRobotWrapper`):

| Stub | Mimics |
|------|--------|
| `MoveCart(...)` | `Robot.MoveCart` |
| `MoveL(...)` | `Robot.MoveL` |
| `StartJOG(...)` | `Robot.StartJOG` |
| `StopMotion()` | `Robot.StopMotion` |
| `GetActualTCPPose()` | `Robot.GetActualTCPPose` → `(0, [0.0, …])` |
| `RobotEnable(param)` | `Robot.RobotEnable` |
| `ResetAllError()` | `Robot.ResetAllError` |
| `SetDO(port_id, value)` | `Robot.SetDO` |
| `execute_path(...)` | SDK trajectory execution |
| `GetSDKVersion()` | Returns `"TestRobot SDK v1.0"` |

---

## Data Flow

```
FairinoRobot.move_ptp(position, tool, user, vel, acc)
        │
        │  robot.MoveCart(position, tool, user, vel=vel, acc=acc)
        ▼
  TestRobotWrapper.MoveCart(...)   ← (currently)
        │ returns 0
        ▼
  FairinoRobot returns 0 to MotionService
```

---

## Usage Example

```python
from src.engine.robot.drivers.fairino.fairino_robot import FairinoRobot
from src.engine.robot.drivers.fairino.test_robot import TestRobotWrapper

# Development (mock)
robot = TestRobotWrapper()
robot.move_ptp([200.0, 0.0, 400.0, 180.0, 0.0, 0.0], tool=0, user=0, vel=50, acc=50)
# → 0 (immediate)

# Production (through FairinoRobot — currently uses TestRobotWrapper internally)
robot = FairinoRobot(ip="192.168.58.2")
robot.enable()
pos = robot.get_current_position()  # → [0.0, 0.0, 0.0, 0.0, 0.0, 0.0] in test mode
```

---

## Design Notes

### Current Wiring Status

`FairinoRobot.__init__` uses `TestRobotWrapper` instead of the real SDK. This is because the FairinoRobot Python SDK (`fairino.Robot.RPC`) requires a live robot or specific network conditions. The mock lets the full platform start without hardware.

To connect to a real robot:
1. Install the `fairino` SDK package
2. Replace `self.robot = TestRobotWrapper()` with `self.robot = fairino.Robot.RPC(self.ip)`

### `get_current_velocity` / `get_current_acceleration`

Both always return `0.0`. The FairinoRobot SDK does not expose these values directly. The `RobotStateManager` tolerates `0.0` without error, and subscribers to `robot/velocity` and `robot/acceleration` topics will receive `0.0` as long as this driver is in use.

### `jog` Reference Frame

`start_jog` uses `ref=4` (Cartesian TCP frame). This means jog moves are in the tool coordinate frame, which is the expected behavior for manual robot teaching.
