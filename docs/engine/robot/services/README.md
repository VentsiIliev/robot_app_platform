# `src/engine/robot/services/` — Robot Services

This package contains the core service implementations that sit between the physical robot driver and the application layer: `MotionService` (safety-checked motion), `RobotStateManager` (state polling and broadcasting), `RobotStatePublisher` (message bus bridge), and `RobotService` (the assembled `IRobotService` facade). It also contains the `create_robot_service` factory.

---

## Class Diagram

```
IRobotService (public interface)
       │
      └── RobotService
                 ├── _motion: IMotionService
                 │       └── MotionService
                 │                 ├── _robot: IRobot
                 │                 ├── _safety: ISafetyChecker
                 │                 └── _cached_position: List[float]  ← updated by "robot/position" subscription
                 ├── _robot: IRobot  (same instance — for enable/disable + remote safety walls)
                 ├── _state: IRobotStateProvider
                 │       └── RobotStateManager
                 │                 ├── _robot: FairinoRobot(robot.ip)  ← dedicated connection, correct IP
                 │                 └── _publisher: IStatePublisher
                 │                         └── RobotStatePublisher
                 │                                   └── IMessagingService
                 └── _tools: Optional[IToolService]
```

---

## API Reference

### `MotionService`

**File:** `motion_service.py`

Implements `IMotionService`. Wraps `IRobot` calls with safety checking and optional blocking pose wait.

```python
class MotionService(IMotionService):
    _WAIT_THRESHOLD_MM = 2.0
    _WAIT_THRESHOLD_DEG = 1.0
    _WAIT_DELAY_S      = 0.1
    _WAIT_TIMEOUT_S    = 10.0

    def __init__(
        self,
        robot: IRobot,
        safety_checker: ISafetyChecker,
        jog_velocity: float = 10.0,
        jog_acceleration: float = 10.0,
        messaging_service=None,          # Optional[IMessagingService]
    ): ...
```

If `messaging_service` is provided, `MotionService` subscribes to `RobotTopics.POSITION` (`"robot/position"`) via the named bound method `_on_position`. The received position is cached in `self._cached_position`. This eliminates a competing XML-RPC call to the robot during move-wait loops (see `_wait_for_position` below).

| Method | Safety checked | Returns |
|--------|---------------|---------|
| `move_ptp(position, tool, user, velocity, acceleration, wait_to_reach=False, wait_cancelled=None)` | Yes | `bool` |
| `move_linear(position, tool, user, velocity, acceleration, blendR=0.0, wait_to_reach=False, wait_cancelled=None)` | Yes | `bool` |
| `start_jog(axis, direction, step)` | Yes (pre-flight) | `int` (SDK code) |
| `stop_motion()` | No | `bool` |
| `get_current_position()` | No | `List[float]` |

**`wait_to_reach` semantics:**

When `wait_to_reach=True`, after issuing the motion command, `_wait_for_position` checks the robot pose every `_WAIT_DELAY_S = 0.1s` until:
- Euclidean distance on `(x, y, z)` is ≤ `_WAIT_THRESHOLD_MM = 2.0mm`
- and, when the target includes orientation, the wrapped angular error on `(rx, ry, rz)` is ≤ `_WAIT_THRESHOLD_DEG = 1.0°`
- or timeout after `_WAIT_TIMEOUT_S = 10.0s` (logs warning, returns `False`)

If `wait_cancelled` is provided, `_wait_for_position` also checks that callback on each poll loop and aborts the wait immediately when it returns `True`.

Position is read from `self._cached_position` (updated by the `"robot/position"` subscription). If the cache is empty (subscription not yet received), it falls back to `self._robot.get_current_position()` directly. This avoids a concurrent XML-RPC connection to the robot while the poll thread is already reading the same endpoint.

Angular error uses wrapped-angle comparison, so targets around `-180° / 180°` are treated correctly. Example: current `rz=-179.5°` and target `rz=179.8°` is treated as `0.7°`, not `359.3°`.

**`stop_motion()` retries:**

`MotionService.stop_motion()` now retries the low-level stop command a few times with a short delay. This makes pause/stop more reliable when the transport reports a transient failed stop on the first attempt.

**`start_jog` safety pre-flight:**

Before issuing the jog command to the robot, `start_jog` computes where the robot *would* end up after the step and runs `is_within_safety_limits` on that projected target. If the target falls outside the limits, the jog is blocked and `-1` is returned without touching the hardware.

For **linear axes** (X/Y/Z), the projected target is computed using a rotation-matrix projection of the tool-frame step into base-frame coordinates — see `_tool_frame_delta` below. This handles tool orientations where base and tool axes differ (e.g. `rx≈180°` flips the tool Z axis relative to base Z).

For **rotational axes** (RX/RY/RZ), the offset is applied directly to the corresponding element of the current position.

**`_tool_frame_delta` static helper:**

```python
@staticmethod
def _tool_frame_delta(position: List[float], axis_idx: int,
                      direction_value: float, step: float) -> tuple[float, float, float]:
```

Projects a single tool-frame jog step into a base-frame `(dx, dy, dz)` displacement.

Builds the ZYX extrinsic rotation matrix `R = Rz(rz) · Ry(ry) · Rx(rx)` from the current Euler angles `position[3:6]` (degrees), then returns the scaled column corresponding to the jogged axis:

| `axis_idx` | Tool axis | Column of R |
|-----------|-----------|-------------|
| 0 | X | `(cy·cz, cy·sz, −sy)` |
| 1 | Y | `(cz·sx·sy − cx·sz, cx·cz + sx·sy·sz, cy·sx)` |
| 2 | Z | `(cx·cz·sy + sx·sz, cx·sy·sz − cz·sx, cx·cy)` |

Verification at `rx=180°, ry=0°, rz=0°` (R = diag(1, −1, −1)):
- Tool Z PLUS → base `(0, 0, −1)·step` → base Z decreases ✓
- Tool X PLUS → base `(1, 0, 0)·step` → base X increases ✓

**`start_jog` note:** Jog uses the `jog_velocity` and `jog_acceleration` values set at construction time (defaults: 10.0), not parameters passed by the caller.

---

### `RobotStateSnapshot`

**File:** `robot_state_snapshot.py`

Immutable snapshot of robot state. Published to the messaging bus on every polling tick.

```python
@dataclass(frozen=True)
class RobotStateSnapshot:
    state:        str
    position:     List[float]      # [x, y, z, rx, ry, rz] in mm/degrees
    velocity:     float
    acceleration: float
    extra:        Dict[str, Any] = field(default_factory=dict)

    def with_extra(self, **kwargs) -> RobotStateSnapshot: ...
```

`with_extra()` returns a new snapshot with additional fields merged into `extra`. Useful for subclasses that add domain-specific state fields.

---

### `RobotStateManager`

**File:** `robot_state_manager.py`

Implements `IRobotStateProvider`. Polls the robot hardware at 0.1s intervals in a daemon thread and publishes `RobotStateSnapshot` via `IStatePublisher`.

```python
class RobotStateManager(IRobotStateProvider):
    _POLL_INTERVAL_S = 0.1

    def __init__(
        self,
        robot: IRobot,
        publisher: Optional[IStatePublisher] = None,
        state_topic: str = "robot/state",
    ): ...

    # IRobotStateProvider (all thread-safe via lock):
    @property def position(self) -> List[float]: ...
    @property def velocity(self) -> float: ...
    @property def acceleration(self) -> float: ...
    @property def state(self) -> str: ...
    @property def state_topic(self) -> str: ...
    def start_monitoring(self) -> None: ...
    def stop_monitoring(self) -> None: ...

    # Extension hook:
    def _build_snapshot(self) -> RobotStateSnapshot: ...  # override to add fields
```

**Thread safety:** All property reads acquire `self._lock`. `_build_snapshot` also acquires the lock.

**`stop_monitoring()`** signals the thread to stop and joins with a 2s timeout.

**Dedicated connection:** `RobotStateManager` opens its own `FairinoRobot` connection (using `robot.ip` when available, falling back to the passed robot for test doubles). This dedicated connection is the **only** caller of `GetActualTCPPose` — the command thread no longer polls position directly, preventing `http.client.CannotSendRequest` errors from simultaneous XML-RPC calls.

---

### `RobotStatePublisher`

**File:** `robot_state_publisher.py`

Implements `IStatePublisher`. Publishes all four robot topics on every call.

```python
class RobotStatePublisher(IStatePublisher):
    def __init__(self, broker: IMessagingService): ...
    def publish(self, snapshot: RobotStateSnapshot) -> None: ...
```

Published topics per call:

| Topic | Payload |
|-------|---------|
| `RobotTopics.STATE` = `"robot/state"` | `RobotStateSnapshot` |
| `RobotTopics.POSITION` = `"robot/position"` | `snapshot.position` (`List[float]`) |
| `RobotTopics.VELOCITY` = `"robot/velocity"` | `snapshot.velocity` (`float`) |
| `RobotTopics.ACCELERATION` = `"robot/acceleration"` | `snapshot.acceleration` (`float`) |

---

### `RobotService`

**File:** `robot_service.py`

Implements `IRobotService`. Assembles the motion layer, state provider, and optional tool service into a single facade.

```python
class RobotService(IRobotService):
    def __init__(
        self,
        motion: IMotionService,
        robot: IRobot,
        state_provider: IRobotStateProvider,
        tool_service: Optional[IToolService] = None,
    ): ...

    @property def tools(self) -> Optional[IToolService]: ...
```

Delegates:
- Motion commands (`move_ptp`, `move_linear`, `start_jog`, `stop_motion`) → `self._motion`
- `get_current_position()` → `list(self._state.position)` — reads the cache maintained by `RobotStateManager`, **no XML-RPC call**
- `enable_robot()` / `disable_robot()` → `self._robot.enable()` / `.disable()`
- `get_current_velocity()` / `get_current_acceleration()` / `get_state()` / `get_state_topic()` → `self._state`
- remote safety-wall control:
  - `enable_safety_walls()` → `self._robot.enable_safety_walls()`
  - `disable_safety_walls()` → `self._robot.disable_safety_walls()`
  - `are_safety_walls_enabled()` → `self._robot.are_safety_walls_enabled()`
  - `get_safety_walls_status()` → `self._robot.get_safety_walls_status()`

Remote safety-wall support is intentionally part of `IRobotService`, not `ISafetyChecker`:

- `ISafetyChecker`
  - local platform-side pose validation
- remote safety walls
  - execution-environment / MoveIt planning-scene control

---

### `create_robot_service` (factory)

**File:** `robot_service_factory.py`

```python
def create_robot_service(
    robot: IRobot,
    messaging_service: IMessagingService,   # required
    robot_settings_key,
    settings_service=None,
    tool_changer=None,
) -> IRobotService:
    ...
```

Assembly order:
1. `SafetyChecker(robot_settings_key, settings_service)` ← optional settings
2. `MotionService(robot, safety_checker, messaging_service=messaging_service)` ← subscribes to `"robot/position"`
3. `RobotStatePublisher(messaging_service)` ← required
4. `RobotStateManager(robot, publisher)` + `state.start_monitoring()` ← opens dedicated connection via `robot.ip`
5. Optionally: `RobotToolService(motion, robot_config, tool_changer)`
6. Returns `RobotService(motion, robot, state, tool_service)`

---

## Data Flow

### Motion Command

```
Application → IRobotService.move_ptp(pos, tool, user, vel, acc)
    │
    ▼
RobotService.move_ptp(...)
    │ delegates to
    ▼
MotionService.move_ptp(...)
    │
    ├─ SafetyChecker.is_within_safety_limits(pos) → bool
    │       False → log warning, return False
    │
    ├─ IRobot.move_ptp(pos, tool, user, vel, acc) → int
    │       ret != 0 → return False
    │
    └─ wait_to_reach? → _wait_for_position(pos, threshold=2mm, timeout=10s)
                              reads self._cached_position (from "robot/position" subscription)
                              falls back to IRobot.get_current_position() if cache is empty
```

### Jog Command

```
Application → IRobotService.start_jog(axis, direction, step)
    │
    ▼
MotionService.start_jog(...)
    │
    ├─ IRobot.get_current_position() → List[float]  (6 elements: x,y,z,rx,ry,rz)
    │
    ├─ compute projected target:
    │       linear axis (idx < 3):
    │           _tool_frame_delta(current, idx, direction, step)
    │           → R = Rz(rz)·Ry(ry)·Rx(rx); project tool-axis column into base frame
    │           target[0..2] += (dx, dy, dz)
    │       rotational axis (idx ≥ 3):
    │           target[idx] += direction * step
    │
    ├─ SafetyChecker.is_within_safety_limits(target) → bool
    │       False → log warning, return -1  (hardware not touched)
    │
    └─ IRobot.start_jog(axis, direction, step, jog_vel, jog_acc) → int
```

### State Broadcasting (background thread)

```
RobotStateManager._poll_loop()  [every 0.1s, daemon thread]
    │  (runs on a dedicated FairinoRobot(robot.ip) connection — sole XML-RPC caller)
    │
    ├─ IRobot.get_current_position() → List[float]
    ├─ IRobot.get_current_velocity() → float
    ├─ IRobot.get_current_acceleration() → float
    │
    ├─ update _position, _velocity, _acceleration (under lock)
    │
    └─ RobotStatePublisher.publish(snapshot)
            │
            ├─ messaging.publish("robot/state",        snapshot)
            ├─ messaging.publish("robot/position",     snapshot.position)
            │       └─▶ MotionService._on_position(position)  ← updates _cached_position
            ├─ messaging.publish("robot/velocity",     snapshot.velocity)
            └─ messaging.publish("robot/acceleration", snapshot.acceleration)
```

---

## Usage Example

```python
from src.engine.robot.services.robot_service_factory import create_robot_service
from src.engine.robot.drivers.fairino.fairino_robot import FairinoRobot

robot = FairinoRobot(ip="192.168.58.2")
robot_service = create_robot_service(
    robot=robot,
    messaging_service=messaging,
    settings_service=settings,
)

# Move to a position
ok = robot_service.move_ptp(
    position=[200.0, 0.0, 400.0, 180.0, 0.0, 0.0],
    tool=0,
    user=0,
    velocity=50,
    acceleration=50,
    wait_to_reach=True,
)

# Subscribe to state updates
def on_state(snapshot):
    print(snapshot.position)

messaging.subscribe("robot/state", on_state)
```

---

## Design Notes

- **`RobotStateManager` is thread-safe by design**: Position, velocity, acceleration, and state are protected by a `threading.Lock` to prevent torn reads from the Qt main thread.
- **`_build_snapshot` is overridable**: Subclasses can override `RobotStateManager._build_snapshot()` to include additional application-specific state fields in the published snapshot (using `with_extra()`).
- **`start_monitoring()` is idempotent**: Calling it when already running does nothing. `stop_monitoring()` signals the thread and waits up to 2s.
- **`create_robot_service` requires `messaging_service`**: Unlike `settings_service` and `tool_changer`, the messaging service is not optional. State publishing is fundamental to the platform's reactive architecture.
- **Single XML-RPC caller for position**: `RobotStateManager` opens its own `FairinoRobot(robot.ip)` connection and is the **only** code path that calls `GetActualTCPPose`. `MotionService._wait_for_position` reads from its subscription cache instead, and `RobotService.get_current_position()` reads from `RobotStateManager.position` (no XML-RPC). This prevents `http.client.CannotSendRequest` errors caused by two threads simultaneously using the same XML-RPC connection.
- **`_on_position` is a named bound method**: Required for correct behaviour with `MessageBroker`'s weak references — lambdas would be silently garbage-collected.
