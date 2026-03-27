# `src/robot_systems/glue/navigation.py` — GlueNavigationService

`GlueNavigationService` is a glue-specific facade over the generic `NavigationService`. It adds Z-offset-aware movement, named semantic positions (HOME, CALIBRATION, LOGIN), and automatic work-area activation after each move.

---

## Responsibilities

- **Z-offset movement** — HOME and CALIBRATION positions apply a Z offset before moving, so the robot stops at the correct capture height above the surface.
- **Work-area activation** — After certain moves the active work area is switched automatically (`"pickup"` after HOME, `"spray"` after CALIBRATION).
- **Observer binding** — Named groups declared in `GlueRobotSystem.work_area_observers` are wired in at construction; any move to a bound group activates the corresponding work area.

---

## Constructor

```python
class GlueNavigationService:
    def __init__(
        self,
        navigation:              NavigationService,
        vision:                  Optional[IVisionService]    = None,
        robot_service:           Optional[IRobotService]     = None,
        work_area_service:       Optional[IWorkAreaService]  = None,
        observed_area_by_group:  Optional[dict[str, str]]    = None,
    ) -> None: ...
```

`observed_area_by_group` maps group name → work-area ID. Built from `GlueRobotSystem.get_work_area_observer_bindings()` during `on_start()`.

---

## API

### Semantic positions

```python
def move_home(self) -> bool: ...
```
Moves to the `HOME` group, applying the vision capture Z offset (`IVisionService.get_capture_pos_offset()`). Activates work area `"pickup"` on success.

```python
def move_to_login_position(self) -> bool: ...
```
Moves to `LOGIN`. No Z offset. No work-area change.

```python
def move_to_calibration_position(
    self,
    z_offset: float = 0.0,
    wait_cancelled: Callable[[], bool] | None = None,
) -> bool: ...
```
Moves to `CALIBRATION` with optional Z offset. Activates work area `"spray"` on success. `wait_cancelled` is polled during motion — return `True` to abort.

---

### Generic group movement

```python
def move_to(
    self,
    group_name: str,
    z_offset:   float = 0.0,
    wait_cancelled: Callable[[], bool] | None = None,
) -> bool: ...
```
Point-to-point move to a named group, with optional Z offset. Activates the bound work area if the group has an observer binding.

```python
def move_linear(self, group_name: str) -> bool: ...
def move_to_group(self, group_name: str, wait_cancelled: ...) -> bool: ...
def move_linear_group(self, group_name: str) -> bool: ...
```
Linear / PTP variants — same observer-binding behaviour.

```python
def move_to_position(
    self,
    position:   list,
    group_name: str,
    wait_cancelled: Callable[[], bool] | None = None,
) -> bool: ...
```
Move to an explicit `[x, y, z, rx, ry, rz]` position, using `group_name` for velocity/acceleration lookup and for the observer binding.

---

### Utilities

```python
def get_group_names(self) -> list[str]: ...
def get_group_position(self, group_name: str) -> list[float] | None: ...
```

`get_group_position()` is also used outside direct motion:
- calibration-area observer guards resolve `HOME` / `CALIBRATION` positions through it before starting area-grid verification or measurement
- frame builders use it to construct `PlanePoseMapper` instances from declared navigation groups

If the named group is missing or its saved position cannot be parsed, it returns `None`.

---

## Z-offset Mechanics

When a non-zero Z offset is supplied the service reads the stored group position from `NavigationService`, adds `z_offset` to the Z component (index `2`), then calls `move_to_position()`. If the group position cannot be resolved, the move returns `False` without raising.

```
stored_position[z] + z_offset  →  final robot Z position
```

The HOME offset comes from `IVisionService.get_capture_pos_offset()` — the height at which the camera captures a sharp image of the work surface. This ensures the camera is at the right height before contour detection runs.

---

## Work-Area Activation

After a successful move the service calls `IWorkAreaService.set_active_area_id()` (preferred) or falls back to `IVisionService.set_active_work_area()`. This switches the active detection region so the vision system only searches within the bounds relevant to the current robot position.

| Move | Active area |
|------|-------------|
| `move_home()` | `"pickup"` |
| `move_to_calibration_position()` | `"spray"` |
| `move_to()` / `move_to_group()` / `move_linear()` | bound area from `work_area_observers`, or unchanged |

---

## Design Notes

- **Wrapper, not replacement** — `GlueNavigationService` delegates all motion to the underlying `NavigationService`; it adds no motion logic of its own.
- **Optional dependencies** — `vision`, `robot_service`, and `work_area_service` are all optional. Missing services cause graceful degradation (no Z offset, no area activation) rather than errors.
- **`wait_cancelled` propagation** — Callers that run navigation inside a process must pass `lambda: cancel_event.is_set()` to allow operator interruption without spinning a separate thread.
- **Shared position lookup** — the same saved movement-group lookup is used for both runtime motion and observer-position checks, so `HOME` / `CALIBRATION` consistency depends on `get_group_position()` resolving the exact stored group definition from `NavigationService`.
