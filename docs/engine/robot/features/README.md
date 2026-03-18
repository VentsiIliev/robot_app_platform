# `src/engine/robot/features/` — High-Level Robot Features

The `features` package provides high-level, business-logic-aware robot capabilities built on top of `IMotionService`. These are not part of the core motion stack — they depend on settings and are optional services.

---

## Classes

### `NavigationService`

**File:** `navigation_service.py`

Moves the robot to pre-configured named positions stored in `RobotSettings.movement_groups`. Navigation calls normally use `wait_to_reach=True`, so they block until the robot reaches the requested pose. In the default `MotionService` implementation that means position convergence on `x,y,z` and, for 6D targets, orientation convergence on `rx,ry,rz`. Callers can also pass a wait-cancel callback to interrupt that wait early.

```python
class NavigationService:
    def __init__(self, motion: IMotionService, settings_service=None): ...
    def move_home(self, z_offset: float = 0.0) -> bool: ...
    def move_to_calibration_position(self, z_offset: float = 0.0) -> bool: ...
    def move_to_login_position(self) -> bool: ...
```

**Named positions required in settings:**

| Method | Movement Group Key | Notes |
|--------|-------------------|-------|
| `move_home(z_offset)` | `"HOME"` | z-axis adjusted by `z_offset` |
| `move_to_calibration_position(z_offset)` | `"CALIBRATION"` | z-axis adjusted by `z_offset` |
| `move_to_login_position()` | `"LOGIN"` | no z adjustment |

Each method:
1. Reads `RobotSettings` via `settings_service.get("robot_config")`
2. Looks up the named `MovementGroup`
3. Parses the position string: `"[x, y, z, rx, ry, rz]"` → `List[float]`
4. Calls `motion.move_ptp(position, tool, user, velocity, acceleration, wait_to_reach=True, wait_cancelled=...)`

Returns `False` if the position is not configured, the movement group is missing, or the move fails.

**Error conditions:**

| Condition | Return | Logged |
|-----------|--------|--------|
| `settings_service` is `None` | `False` (raises `RuntimeError`) | exception |
| Movement group not found | `False` | error |
| `parse_position()` returns `None` | `False` | error |
| `move_ptp()` returns `False` | `False` | — |

---

### `RobotToolService`

**File:** `tool_service.py`

High-level gripper management. Implements `IToolService` by delegating all operations to `ToolManager`.

```python
class RobotToolService(IToolService):
    def __init__(
        self,
        motion_service: IMotionService,
        robot_config,
        tool_changer,
    ): ...

    @property
    def current_gripper(self) -> Optional[int]: ...
    def pickup_gripper(self, gripper_id: int) -> Tuple[bool, Optional[str]]: ...
    def drop_off_gripper(self, gripper_id: int) -> Tuple[bool, Optional[str]]: ...
```

Both `pickup_gripper` and `drop_off_gripper` return `(success, error_message_or_None)`.

Internally creates a `ToolManager` with the provided motion service, robot config, and tool changer.

---

### `ToolManager` (in `robot/tool_manager.py`)

The concrete implementation of pick-and-place logic. `RobotToolService` is a thin facade over `ToolManager`.

```python
class ToolManager:
    def __init__(
        self,
        motion_service: IMotionService,
        tool_changer: IToolChanger,
        robot_config,
    ): ...

    def pickup_gripper(self, gripper_id: int, max_retries: int = 3) -> Tuple[bool, Optional[str]]: ...
    def drop_off_gripper(self, gripper_id: int, max_retries: int = 3) -> Tuple[bool, Optional[str]]: ...
    def verify_gripper_change(self, target_gripper_id: int) -> bool: ...
    def add_tool(self, name: str, tool) -> None: ...
    def get_tool(self, name: str): ...
```

**`pickup_gripper` logic:**
1. Check if gripper is already held → return error
2. Get pickup positions from `robot_config` (supports grippers 0, 1, 4)
3. Execute each position via `move_linear` with retry (up to `max_retries`)
4. Mark tool changer slot as available
5. Set `current_gripper = gripper_id`

**`drop_off_gripper` logic:**
1. Check if gripper is currently held → return error
2. Check if destination slot is already occupied → return error
3. Get drop-off positions from `robot_config`
4. Execute each position via `move_linear` with retry
5. Mark slot as not available
6. Set `current_gripper = None`

**Retry behavior:** On transient errors (detected by `"Request-sent"` in the exception message), retries with exponential backoff (0.2s × attempt). Non-transient errors abort immediately.

---

### `ToolChanger` (in `robot/tool_changer.py`)

Implements `IToolChanger`. Maintains a registry of slots and their occupancy state.

```python
@dataclass
class SlotConfig:
    id: int
    tool_id: int
    occupied: bool = False

class ToolChanger(IToolChanger):
    def __init__(self, slots: list[SlotConfig]): ...
    def get_slot_id_by_tool_id(self, tool_id: int) -> Optional[int]: ...
    def is_slot_occupied(self, slot_id: int) -> bool: ...
    def set_slot_available(self, slot_id: int) -> None: ...
    def set_slot_not_available(self, slot_id: int) -> None: ...
    def get_occupied_slots(self) -> list[int]: ...
    def get_empty_slots(self) -> list[int]: ...
```

---

## Data Flow — Navigation

```
NavigationService.move_home(z_offset=10.0)
        │
        │  settings_service.get("robot_config") → RobotSettings
        │  config.movement_groups["HOME"] → MovementGroup
        │  group.parse_position() → [200.0, -100.0, 400.0, 180.0, 0.0, 0.0]
        │  position[2] += z_offset → [200.0, -100.0, 410.0, ...]
        │
        ▼
IMotionService.move_ptp(
    position=[200.0, -100.0, 410.0, 180.0, 0.0, 0.0],
    tool=config.robot_tool,
    user=config.robot_user,
    velocity=group.velocity,
    acceleration=group.acceleration,
    wait_to_reach=True,
)
```

---

## Usage Example

```python
from src.engine.robot.features.navigation_service import NavigationService

nav = NavigationService(motion=robot_service, settings_service=settings_service)

# Move to home position (with 20mm Z clearance)
ok = nav.move_home(z_offset=20.0)
if not ok:
    print("Failed to move home")

# Move to calibration position
ok = nav.move_to_calibration_position(z_offset=0.0)
```

---

## Design Notes

- **`NavigationService` does not inherit `IMotionService`**: It is a feature service, not a motion service. It is not part of the `IRobotService` interface and is consumed separately by robot system logic.
- **`ToolManager` uses a lock**: All `pickup_gripper` and `drop_off_gripper` operations acquire a `threading.Lock`, making them safe to call from different threads.
- **`robot_config` in `ToolManager`**: The `robot_config` argument is untyped because it accesses gripper-specific methods (`getSlot0PickupPointsParsed`, etc.) that are specific to the concrete glue robot config class, not to the generic `RobotSettings` dataclass.
