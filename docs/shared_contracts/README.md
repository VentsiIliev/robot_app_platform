# `src/shared_contracts/` — Shared Contracts

The `shared_contracts` package is the **canonical event bus contract** for the entire platform. It defines the topic strings, payload dataclasses, and enums used by **both** publishers (engine services, robot app services) and subscribers (plugin controllers, dashboard controllers). Nothing in this package has any dependencies on the engine or plugin layers — it is a pure vocabulary module importable by any layer.

---

## Purpose

Without `shared_contracts`, a publisher and subscriber must agree on topic strings by convention (error-prone). With `shared_contracts`, both sides import the same constant:

```python
# Publisher (engine layer):
from src.shared_contracts.events.robot_events import RobotTopics
messaging.publish(RobotTopics.POSITION, [x, y, z, rx, ry, rz])

# Subscriber (plugin / dashboard controller):
from src.shared_contracts.events.robot_events import RobotTopics
messaging.subscribe(RobotTopics.POSITION, self._on_position)
```

This guarantees that renaming a topic (in the contracts file) immediately causes import errors everywhere it is used — compile-time safety instead of silent mismatches.

---

## Package Contents

| File | Status | Description |
|------|--------|-------------|
| `events/robot_events.py` | Implemented | `RobotTopics` — 4 robot state topics |
| `events/weight_events.py` | Implemented | `WeightTopics`, `WeightReading`, `CellStateEvent`, `CellState` |
| `events/process_events.py` | **Placeholder** | Empty — reserved for cross-app process events (process state is in `src/engine/process/`) |
| `events/vision_events.py` | **Placeholder** | Empty — reserved for vision / camera events |
| `enums.py` | **Placeholder** | Empty — reserved for shared platform enums |
| `constants.py` | **Placeholder** | Empty — reserved for shared platform constants |

---

## Complete Topic Reference

### Robot Topics (`robot_events.py`)

| Constant | Topic String | Published By | Payload Type | Frequency |
|----------|-------------|--------------|--------------|-----------|
| `RobotTopics.STATE` | `"robot/state"` | `RobotStatePublisher` | `RobotStateSnapshot` | Every 0.5s |
| `RobotTopics.POSITION` | `"robot/position"` | `RobotStatePublisher` | `List[float]` [x,y,z,rx,ry,rz] mm/° | Every 0.5s |
| `RobotTopics.VELOCITY` | `"robot/velocity"` | `RobotStatePublisher` | `float` | Every 0.5s |
| `RobotTopics.ACCELERATION` | `"robot/acceleration"` | `RobotStatePublisher` | `float` | Every 0.5s |

### Weight Topics (`weight_events.py`)

| Method | Topic String | Published By | Payload Type |
|--------|-------------|--------------|--------------|
| `WeightTopics.state(cell_id)` | `"weight/cell/{id}/state"` | `WeightCellService` | `CellStateEvent` |
| `WeightTopics.reading(cell_id)` | `"weight/cell/{id}/reading"` | `WeightCellService` | `WeightReading` |
| `WeightTopics.all_readings()` | `"weight/cell/all/reading"` | `WeightCellService` | `WeightReading` |

### Process Topics (engine layer — not in shared_contracts)

Process lifecycle events are defined in `src/engine/process/process_state.py`:

| Method | Topic Pattern | Payload | Published By |
|--------|--------------|---------|-------------|
| `ProcessTopics.state(id)` | `"process/{id}/state"` | `ProcessStateEvent` | `BaseProcess._transition()` |
| `ProcessTopics.error(id)` | `"process/{id}/error"` | *(reserved)* | *(reserved)* |

```python
# Import from engine/process, not shared_contracts:
from src.engine.process.process_state import ProcessTopics, ProcessState, ProcessStateEvent
```

### App-Specific Topics (not in shared_contracts)

Some topic strings are defined in the robot app layer for app-specific events:

| Topic String | Defined In | Description |
|-------------|-----------|-------------|
| `"glue/cell/{id}/glue_type"` | `dashboard/config.py::GlueCellTopics` | Glue type assigned to a cell |
| `"system/application_state"` | `dashboard/config.py::SystemTopics` | Legacy system state topic (kept for external integrations) |

---

## Payload Reference

### `WeightReading` (frozen dataclass)

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

### `CellStateEvent` (frozen dataclass)

```python
@dataclass(frozen=True)
class CellStateEvent:
    cell_id:   int
    state:     CellState
    message:   str      = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

### `CellState` (Enum)

| Value | String |
|-------|--------|
| `CellState.DISCONNECTED` | `"disconnected"` |
| `CellState.CONNECTING` | `"connecting"` |
| `CellState.CONNECTED` | `"connected"` |
| `CellState.ERROR` | `"error"` |

### `RobotStateSnapshot` (from engine layer)

Published on `RobotTopics.STATE`. Defined in `src/engine/robot/services/robot_state_snapshot.py` (not in shared_contracts because it depends on engine types):

```python
@dataclass(frozen=True)
class RobotStateSnapshot:
    state:        str
    position:     List[float]
    velocity:     float
    acceleration: float
    extra:        Dict[str, Any]
```

---

## Adding New Events

1. Add a frozen dataclass payload to the appropriate `events/*.py` file
2. Add a topic string constant or static method to the corresponding `Topics` class
3. Import and use from both the publisher and subscriber — the import error at build/start time will catch mismatches

---

## Placeholder Files

`process_events.py`, `vision_events.py`, `enums.py`, and `constants.py` are currently empty. They exist to reserve module locations for future capabilities. Do not remove them — imports referencing these modules should fail visibly rather than silently when the time comes to implement them.

> **`process_events.py` note:** Per-process state (`ProcessState`, `ProcessStateEvent`, `ProcessTopics`) currently lives in `src/engine/process/process_state.py` — not here. `process_events.py` is reserved for higher-level cross-app process notifications if they are needed in future.

→ Details: [events/README.md](events/README.md)
