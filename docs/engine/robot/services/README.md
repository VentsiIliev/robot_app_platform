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
                 │                 └── _safety: ISafetyChecker
                 ├── _robot: IRobot  (same instance — for enable/disable)
                 ├── _state: IRobotStateProvider
                 │       └── RobotStateManager
                 │                 ├── _robot: IRobot
                 │                 └── _publisher: IStatePublisher
                 │                         └── RobotStatePublisher
                 │                                   └── IMessagingService
                 └── _tools: Optional[IToolService]
```

---

## API Reference

### `MotionService`

**File:** `motion_service.py`

Implements `IMotionService`. Wraps `IRobot` calls with safety checking and optional blocking position wait.

```python
class MotionService(IMotionService):
    _WAIT_THRESHOLD_MM = 2.0
    _WAIT_DELAY_S      = 0.1
    _WAIT_TIMEOUT_S    = 10.0

    def __init__(
        self,
        robot: IRobot,
        safety_checker: ISafetyChecker,
        jog_velocity: float = 10.0,
        jog_acceleration: float = 10.0,
    ): ...
```

| Method | Safety checked | Returns |
|--------|---------------|---------|
| `move_ptp(position, tool, user, velocity, acceleration, wait_to_reach=False)` | Yes | `bool` |
| `move_linear(position, tool, user, velocity, acceleration, blendR=0.0, wait_to_reach=False)` | Yes | `bool` |
| `start_jog(axis, direction, step)` | No | `int` (SDK code) |
| `stop_motion()` | No | `bool` |
| `get_current_position()` | No | `List[float]` |

**`wait_to_reach` semantics:**

When `wait_to_reach=True`, after issuing the motion command, `_wait_for_position` polls `get_current_position()` every `_WAIT_DELAY_S = 0.1s` until:
- Euclidean distance on (x, y, z) only: `√(Σ(aᵢ − bᵢ)²)` ≤ `_WAIT_THRESHOLD_MM = 2.0mm`
- Or timeout after `_WAIT_TIMEOUT_S = 10.0s` (logs warning, returns `False`)

Rotation axes (rx, ry, rz) are not included in the distance calculation.

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

Implements `IRobotStateProvider`. Polls the robot hardware at 0.5s intervals in a daemon thread and publishes `RobotStateSnapshot` via `IStatePublisher`.

```python
class RobotStateManager(IRobotStateProvider):
    _POLL_INTERVAL_S = 0.5

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
- All `IMotionService` methods → `self._motion`
- `enable_robot()` / `disable_robot()` → `self._robot.enable()` / `.disable()`
- `get_current_velocity()` / `get_current_acceleration()` / `get_state()` / `get_state_topic()` → `self._state`

---

### `create_robot_service` (factory)

**File:** `robot_service_factory.py`

```python
def create_robot_service(
    robot: IRobot,
    messaging_service: IMessagingService,
    settings_service=None,
    tool_changer=None,
) -> IRobotService:
    ...
```

Assembly order:
1. `SafetyChecker(settings_service)` ← optional settings
2. `MotionService(robot, safety_checker)` ← default jog params
3. `RobotStatePublisher(messaging_service)` ← required
4. `RobotStateManager(robot, publisher)` + `state.start_monitoring()`
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
```

### State Broadcasting (background thread)

```
RobotStateManager._poll_loop()  [every 0.5s, daemon thread]
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
