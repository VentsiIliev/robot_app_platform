# `src/shared_contracts/` — Shared Contracts

The `shared_contracts` package is the **canonical event bus contract** for the entire platform. It defines the topic strings, payload dataclasses, and enums used by **both** publishers (engine services, robot system services) and subscribers (application controllers, dashboard controllers). Nothing in this package has any dependencies on the engine or application layers — it is a pure vocabulary module importable by any layer.

---

## Purpose

Without `shared_contracts`, a publisher and subscriber must agree on topic strings by convention (error-prone). With `shared_contracts`, both sides import the same constant:

```python
# Publisher (engine layer):
from src.shared_contracts.events.robot_events import RobotTopics
messaging.publish(RobotTopics.POSITION, [x, y, z, rx, ry, rz])

# Subscriber (application / dashboard controller):
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
| `events/process_events.py` | Implemented | `ProcessState`, `ProcessStateEvent`, `ProcessTopics` — process lifecycle state machine contract |
| `events/notification_events.py` | Implemented | `UserNotificationEvent`, `NotificationSeverity`, `NotificationTopics` — generic operator notification contract |
| `events/localization_events.py` | Implemented | `LanguageChangedEvent`, `LocalizationTopics` — runtime language-change notification |
| `events/pick_and_place_events.py` | Implemented | Pick-and-place visualizer and diagnostics topics |
| `events/glue_overlay_events.py` | Implemented | Glue job preview overlay contract for the production dashboard |
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

### Process Topics (`process_events.py`)

| Method | Topic Pattern | Payload | Published By |
|--------|--------------|---------|-------------|
| `ProcessTopics.state(id)` | `"process/{id}/state"` | `ProcessStateEvent` | `BaseProcess._transition()` |
| `ProcessTopics.error(id)` | `"process/{id}/error"` | *(reserved)* | *(reserved)* |

```python
from src.shared_contracts.events.process_events import ProcessTopics, ProcessState, ProcessStateEvent
```

### Notification Topics (`notification_events.py`)

| Constant | Topic String | Payload | Published By |
|----------|--------------|---------|-------------|
| `NotificationTopics.USER` | `"ui/notification"` | `UserNotificationEvent` | Processes, coordinators, services, controllers |

```python
from src.shared_contracts.events.notification_events import (
    NotificationSeverity,
    NotificationTopics,
    UserNotificationEvent,
)
```

### Localization Topics (`localization_events.py`)

| Constant | Topic String | Payload | Published By |
|----------|--------------|---------|-------------|
| `LocalizationTopics.LANGUAGE_CHANGED` | `"localization/language_changed"` | `LanguageChangedEvent` | `LocalizationService` |

### Pick-And-Place Topics (`pick_and_place_events.py`)

| Constant | Topic String | Payload | Published By |
|----------|--------------|---------|-------------|
| `PickAndPlaceTopics.WORKPIECE_PLACED` | `"pick_and_place/workpiece_placed"` | `WorkpiecePlacedEvent` | `PickAndPlaceProcess` |
| `PickAndPlaceTopics.PLANE_RESET` | `"pick_and_place/plane_reset"` | `dict` (currently `{}`) | `PickAndPlaceProcess` |
| `PickAndPlaceTopics.MATCH_RESULT` | `"pick_and_place/match_result"` | `list[MatchedWorkpieceInfo]` | `PickAndPlaceProcess` |
| `PickAndPlaceTopics.DIAGNOSTICS` | `"pick_and_place/diagnostics"` | `PickAndPlaceDiagnosticsEvent` | `PickAndPlaceProcess` |

### Glue Overlay Topics (`glue_overlay_events.py`)

| Constant | Topic String | Payload | Published By |
|----------|--------------|---------|-------------|
| `GlueOverlayTopics.JOB_LOADED` | `"glue/overlay/job_loaded"` | `GlueOverlayJobLoadedEvent` | `GlueJobExecutionService` |

### App-Specific Topics (not in shared_contracts)

Some topic strings are defined in the robot system layer for app-specific events:

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

### `WorkpiecePlacedEvent`

Published when a placement succeeds:

```python
@dataclass(frozen=True)
class WorkpiecePlacedEvent:
    workpiece_name: str
    gripper_id:     int
    plane_x:        float
    plane_y:        float
    width:          float
    height:         float
    timestamp:      datetime
```

### `MatchedWorkpieceInfo`

Published as part of `PickAndPlaceTopics.MATCH_RESULT`:

```python
@dataclass(frozen=True)
class MatchedWorkpieceInfo:
    workpiece_name: str
    workpiece_id:   str
    gripper_id:     int
    orientation:    float
```

### `PickAndPlaceDiagnosticsEvent`

Published on `PickAndPlaceTopics.DIAGNOSTICS`:

```python
@dataclass(frozen=True)
class PickAndPlaceDiagnosticsEvent:
    snapshot: dict[str, Any]
    timestamp: datetime
```

The `snapshot` currently includes the workflow stage, active workpiece/gripper, resolved height source, pickup points, plane state, and last typed error.

### `UserNotificationEvent`

Published on `NotificationTopics.USER`:

```python
@dataclass(frozen=True)
class UserNotificationEvent:
    source: str
    severity: NotificationSeverity
    title_key: str = ""
    message_key: str = ""
    params: Mapping[str, object] = field(default_factory=dict)
    fallback_title: str = ""
    fallback_message: str = ""
    detail: str | None = None
    dedupe_key: str | None = None
    timestamp: datetime
```

This contract is localization-ready:
- backend layers can provide stable keys plus params
- UI presenters can translate later
- fallback text keeps the event usable before translations are implemented

---

## Adding New Events

1. Add a frozen dataclass payload to the appropriate `events/*.py` file
2. Add a topic string constant or static method to the corresponding `Topics` class
3. Import and use from both the publisher and subscriber — the import error at build/start time will catch mismatches

For user-facing notifications:
- publish `UserNotificationEvent` from backend layers
- render it in the application layer with a presenter such as `UserNotificationPresenter`
- do not import Qt or message-box helpers into engine or robot-system code

---

## Placeholder Files

`vision_events.py`, `enums.py`, and `constants.py` are currently empty. They exist to reserve module locations for future capabilities. Do not remove them — imports referencing these modules should fail visibly rather than silently when the time comes to implement them.

→ Details: [events/README.md](events/README.md)
