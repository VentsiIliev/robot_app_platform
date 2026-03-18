# `src/engine/robot/interfaces/` — Robot Interface Hierarchy

This package defines all abstract contracts for the robot control stack. Every interface is consumed by at least one service layer above it and implemented by at least one concrete class below it.

---

## Interface Hierarchy

```
IRobotLifecycle (ABC)
  enable_robot() / disable_robot()

IMotionService (ABC)
  move_ptp() / move_linear() / start_jog() / stop_motion() / get_current_position()

IRobotService (ABC)   ← IMotionService + IRobotLifecycle
  + get_current_velocity() / get_current_acceleration()
  + get_state() / get_state_topic()

IRobot (ABC)
  move_ptp() / move_linear() / start_jog() / stop_motion()
  get_current_position() / get_current_velocity() / get_current_acceleration()
  enable() / disable()

ISafetyChecker (ABC)
  is_within_safety_limits(position)

IRobotStateProvider (ABC)
  position / velocity / acceleration / state / state_topic  (properties)
  start_monitoring() / stop_monitoring()

IStatePublisher (ABC)
  publish(snapshot: RobotStateSnapshot)

IToolChanger (ABC)
  get_slot_id_by_tool_id() / is_slot_occupied()
  set_slot_available() / set_slot_not_available()

IToolService (ABC)
  current_gripper (property)
  pickup_gripper() / drop_off_gripper()
```

---

## API Reference

### `IRobot`

**File:** `i_robot.py`

The lowest-level interface. Represents the physical robot hardware — speaks in terms of SDK calls and returns integer error codes.

```python
class IRobot(ABC):
    def move_ptp(self,
        position: List[float], tool: int, user: int,
        vel: float, acc: float,
    ) -> int: ...

    def move_linear(self,
        position: List[float], tool: int, user: int,
        vel: float, acc: float,
        blend_radius: float = 0.0,
    ) -> int: ...

    def start_jog(self,
        axis: RobotAxis, direction: Direction,
        step: float, vel: float, acc: float,
    ) -> int: ...

    def stop_motion(self) -> int: ...
    def get_current_position(self) -> List[float]: ...
    def get_current_velocity(self) -> float: ...
    def get_current_acceleration(self) -> float: ...
    def enable(self) -> None: ...
    def disable(self) -> None: ...
```

Return convention: `0` = success, any other integer = SDK error code.

Implementations: `FairinoRobot`, `TestRobotWrapper`

---

### `IMotionService`

**File:** `i_motion_service.py`

Mid-level interface. Wraps `IRobot` calls, applies safety checks, and returns `bool`. This is what `RobotService` and `NavigationService` use.

```python
class IMotionService(ABC):
    def move_ptp(self,
        position: List[float], tool: int, user: int,
        velocity: float, acceleration: float,
        wait_to_reach: bool = False,
        wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool: ...

    def move_linear(self,
        position: List[float], tool: int, user: int,
        velocity: float, acceleration: float,
        blendR: float,
        wait_to_reach: bool = False,
        wait_cancelled: Callable[[], bool] | None = None,
    ) -> bool: ...

    def start_jog(self,
        axis: RobotAxis, direction: Direction, step: float,
    ) -> int: ...

    def stop_motion(self) -> bool: ...
    def get_current_position(self) -> List[float]: ...
```

- `wait_to_reach=True`: blocks until the robot reaches the target pose. The default `MotionService` implementation requires Euclidean position error ≤ 2mm on `x,y,z` and, when the target includes orientation, wrapped angular error ≤ 1.0° on `rx,ry,rz`, or it times out after 10s.
- `wait_cancelled`: optional callback checked during that wait loop; when it returns `True`, the wait aborts early.

Implementation: `MotionService`

---

### `IRobotLifecycle`

**File:** `i_robot_lifecycle.py`

Power and enable/disable control.

```python
class IRobotLifecycle(ABC):
    def enable_robot(self) -> None: ...
    def disable_robot(self) -> None: ...
```

---

### `IRobotService`

**File:** `i_robot_service.py`

The **top-level public interface** that applications import. Combines `IMotionService` and `IRobotLifecycle` and adds state query methods.

```python
class IRobotService(IMotionService, IRobotLifecycle, ABC):
    def get_current_velocity(self) -> float: ...
    def get_current_acceleration(self) -> float: ...
    def get_state(self) -> str: ...
    def get_state_topic(self) -> str: ...
```

Implementation: `RobotService`

---

### `ISafetyChecker`

**File:** `i_safety_checker.py`

```python
class ISafetyChecker(ABC):
    def is_within_safety_limits(self, position: List[float]) -> bool: ...
```

Called by `MotionService` before every `move_ptp` and `move_linear`. Returns `True` if the target position is within the configured workspace bounds (x, y, z only). Implementation: `SafetyChecker`.

---

### `IRobotStateProvider`

**File:** `i_robot_state_provider.py`

Read-only view of the current robot state. Used by `RobotService` to answer state queries without calling the robot SDK directly.

```python
class IRobotStateProvider(ABC):
    @property
    def position(self) -> List[float]: ...
    @property
    def velocity(self) -> float: ...
    @property
    def acceleration(self) -> float: ...
    @property
    def state(self) -> str: ...
    @property
    def state_topic(self) -> str: ...

    def start_monitoring(self) -> None: ...
    def stop_monitoring(self) -> None: ...
```

Implementation: `RobotStateManager`

---

### `IStatePublisher`

**File:** `i_state_publisher.py`

```python
class IStatePublisher(ABC):
    def publish(self, snapshot: RobotStateSnapshot) -> None: ...
```

Called by `RobotStateManager` on each polling tick to broadcast the current state to all subscribers. Implementation: `RobotStatePublisher`.

---

### `IToolChanger`

**File:** `i_tool_changer.py`

Registry of tool slots — which slot holds which tool ID, and whether each slot is currently occupied.

```python
class IToolChanger(ABC):
    def get_slot_id_by_tool_id(self, tool_id: int) -> Optional[int]: ...
    def is_slot_occupied(self, slot_id: int) -> bool: ...
    def set_slot_available(self, slot_id: int) -> None: ...
    def set_slot_not_available(self, slot_id: int) -> None: ...
```

Implementation: `ToolChanger` (`src/engine/robot/tool_changer.py`)

---

### `IToolService`

**File:** `i_tool_service.py`

High-level gripper management interface exposed to applications.

```python
class IToolService(ABC):
    @property
    def current_gripper(self) -> Optional[int]: ...
    def pickup_gripper(self, gripper_id: int) -> Tuple[bool, Optional[str]]: ...
    def drop_off_gripper(self, gripper_id: int) -> Tuple[bool, Optional[str]]: ...
```

Returns `(success: bool, error_message: Optional[str])` tuples. Implementation: `RobotToolService` (wraps `ToolManager`).

---

## Design Notes

- **`IRobot` vs `IMotionService`**: `IRobot` is SDK-level (int codes, no safety). `IMotionService` is application-level (bool success, safety-checked, optional blocking wait). Applications never use `IRobot`.
- **`IRobotService` is the application boundary**: Application services import only `IRobotService`. Everything below it is hidden.
- **All properties on `IRobotStateProvider` are thread-safe**: `RobotStateManager` uses a lock on all property reads.
