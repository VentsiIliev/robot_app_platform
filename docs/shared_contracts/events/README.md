# `src/shared_contracts/events/` — Event Contracts

This package contains all topic-string namespaces and payload dataclasses used across the platform's publish-subscribe bus. Both publishers (engine layer) and subscribers (plugin/dashboard controllers) import from here.

---

## `robot_events.py` — Robot State

```python
class RobotTopics:
    STATE        = "robot/state"
    POSITION     = "robot/position"
    VELOCITY     = "robot/velocity"
    ACCELERATION = "robot/acceleration"
```

All four topics are published together on every polling tick (every 0.5s) by `RobotStatePublisher`.

| Topic | Payload | Subscribers |
|-------|---------|-------------|
| `robot/state` | `RobotStateSnapshot` | Dashboard controller (robot state display) |
| `robot/position` | `List[float]` [x,y,z,rx,ry,rz] | `RobotTrajectoryWidget` in `pl_gui` |
| `robot/velocity` | `float` | Dashboard, telemetry |
| `robot/acceleration` | `float` | Dashboard, telemetry |

---

## `weight_events.py` — Weight Cell Events

### Topics

```python
class WeightTopics:
    @staticmethod
    def state(cell_id: int) -> str:
        return f"weight/cell/{cell_id}/state"

    @staticmethod
    def reading(cell_id: int) -> str:
        return f"weight/cell/{cell_id}/reading"

    @staticmethod
    def all_readings() -> str:
        return "weight/cell/all/reading"
```

Topic strings are generated per-cell, not stored as class-level constants, because the number of cells is runtime-configurable.

### Payloads

#### `WeightReading` (frozen dataclass)

```python
@dataclass(frozen=True)
class WeightReading:
    cell_id:   int
    value:     float
    unit:      str      = "g"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_valid(self, min_threshold: float, max_threshold: float) -> bool:
        return min_threshold <= self.value <= max_threshold
```

Published on `weight/cell/{id}/reading` by `WeightCellService` daemon thread. Also published on `weight/cell/all/reading` after each per-cell reading. `is_valid()` checks the reading against the cell's configured thresholds.

#### `CellStateEvent` (frozen dataclass)

```python
@dataclass(frozen=True)
class CellStateEvent:
    cell_id:   int
    state:     CellState
    message:   str      = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

Published on `weight/cell/{id}/state` whenever a cell's connection state changes.

#### `CellState` (Enum)

```python
class CellState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING   = "connecting"
    CONNECTED    = "connected"
    ERROR        = "error"
```

Used as `event.state.value` to get the string for display.

---

## `process_events.py` — Process Lifecycle Events

Defines the canonical state machine contract for any robot application process. Imported by `BaseProcess` (publisher) and dashboard controllers (subscribers).

### `ProcessState` (Enum)

```python
class ProcessState(Enum):
    IDLE    = "idle"
    RUNNING = "running"
    PAUSED  = "paused"
    STOPPED = "stopped"
    ERROR   = "error"
```

### `ProcessStateEvent` (frozen dataclass)

Published on every state transition via `ProcessTopics.state(process_id)`:

```python
@dataclass(frozen=True)
class ProcessStateEvent:
    process_id: str
    state:      ProcessState    # new state
    previous:   ProcessState    # state before transition
    message:    str      = ""   # error message or empty
    timestamp:  datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

### `ProcessTopics`

```python
class ProcessTopics:
    @staticmethod
    def state(process_id: str) -> str:
        return f"process/{process_id}/state"   # e.g. "process/glue/state"

    @staticmethod
    def error(process_id: str) -> str:
        return f"process/{process_id}/error"   # reserved for future use
```

| Method | Topic Pattern | Payload | Published By |
|--------|--------------|---------|-------------|
| `state(id)` | `"process/{id}/state"` | `ProcessStateEvent` | `BaseProcess._transition()` |
| `error(id)` | `"process/{id}/error"` | *(reserved)* | *(reserved)* |

---

## `vision_events.py` — Vision Events (Placeholder)

**Currently empty.** Reserved for camera and computer vision events such as:
- Detection results
- Coordinate transformation responses
- Camera state changes

When implemented, this will define topics under the `vision/` namespace and corresponding payload dataclasses. See `docs/engine/vision/README.md` for the intended API.

---

## Design Notes

- **All payloads are frozen dataclasses**: Immutability prevents subscribers from accidentally mutating state that other subscribers are reading.
- **Timestamps use UTC**: `datetime.now(timezone.utc)` — always timezone-aware, safe for logging and comparison.
- **`WeightTopics` uses static methods, not constants**: Because cell IDs are runtime values, generating topics programmatically is cleaner than declaring `CELL_0_STATE = "weight/cell/0/state"` for each possible ID.
- **Payloads cross thread boundaries**: Both `WeightReading` and `CellStateEvent` are published from daemon threads. Using frozen dataclasses (immutable) means no locking is needed for read access.
