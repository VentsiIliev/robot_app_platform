# `src/shared_contracts/events/` — Event Contracts

This package contains all topic-string namespaces and payload dataclasses used across the platform's publish-subscribe bus. Both publishers (engine layer) and subscribers (application/dashboard controllers) import from here.

---

## `robot_events.py` — Robot State

```python
class RobotTopics:
    STATE        = "robot/state"
    POSITION     = "robot/position"
    VELOCITY     = "robot/velocity"
    ACCELERATION = "robot/acceleration"
    TARGETING_DEFINITIONS_CHANGED = "robot/targeting_definitions_changed"
```

All four topics are published together on every polling tick (every 0.5s) by `RobotStatePublisher`.

| Topic | Payload | Subscribers |
|-------|---------|-------------|
| `robot/state` | `RobotStateSnapshot` | Dashboard controller (robot state display) |
| `robot/position` | `List[float]` [x,y,z,rx,ry,rz] | `RobotTrajectoryWidget` in `pl_gui` |
| `robot/velocity` | `float` | Dashboard, telemetry |
| `robot/acceleration` | `float` | Dashboard, telemetry |
| `robot/targeting_definitions_changed` | `dict` editor payload (robot-system-specific) | shared `JogController` refreshes frame options and live jog targeting |

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

## `notification_events.py` — User Notifications

Defines the generic operator-notification contract used for application-wide dialogs. This is intentionally platform-level and reusable across robot systems.

### Topics

```python
class NotificationTopics:
    USER = "ui/notification"
```

### Payload

#### `UserNotificationEvent`

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
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

Design intent:
- `title_key` / `message_key` make the contract localization-ready
- `fallback_title` / `fallback_message` allow immediate use before translations exist
- `params` is formatted by the UI presenter, not by backend layers
- `dedupe_key` lets presenters suppress repeated dialogs from the same failure loop

### `NotificationSeverity`

```python
class NotificationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
```

The UI layer maps severities to presentation:
- `info` → informational dialog
- `warning` → warning dialog
- `error` / `critical` → critical dialog

---

## `localization_events.py` — Language Changes

Defines the shared language-change event emitted by the runtime localization service.

### Topics

```python
class LocalizationTopics:
    LANGUAGE_CHANGED = "localization/language_changed"
```

### Payload

```python
@dataclass(frozen=True)
class LanguageChangedEvent:
    language_code: str
    timestamp: datetime
```

This topic is useful for non-widget consumers that need to refresh localized dynamic text when the active language changes.

---

## `pick_and_place_events.py` — Pick-And-Place Events

These topics are used by `PickAndPlaceProcess`, the pick-and-place visualizer, and any future diagnostics subscribers.

### Topics

```python
class PickAndPlaceTopics:
    WORKPIECE_PLACED = "pick_and_place/workpiece_placed"
    PLANE_RESET      = "pick_and_place/plane_reset"
    MATCH_RESULT     = "pick_and_place/match_result"
    DIAGNOSTICS      = "pick_and_place/diagnostics"
```

### Payloads

#### `WorkpiecePlacedEvent`

Published after a successful place step.

#### `MatchedWorkpieceInfo`

Published as a list on `MATCH_RESULT` after each matching pass.

#### `PickAndPlaceDiagnosticsEvent`

Published on `DIAGNOSTICS` with a `snapshot` dict describing:
- current workflow stage
- active workpiece and gripper
- resolved height source and pickup points
- current plane offsets/state
- last typed error, if any

This diagnostics topic is intended for operator-facing tooling and debugging, not for commanding behavior.

---

## `glue_overlay_events.py` — Glue Preview Overlay

These topics are used by the glue execution flow and the production dashboard preview.

### Topics

```python
class GlueOverlayTopics:
    JOB_LOADED = "glue/overlay/job_loaded"
```

### Payloads

#### `GlueOverlaySegment`

Represents one planned glue segment in image coordinates.

Fields:
- `path_index`
- `workpiece_id`
- `pattern_type`
- `segment_index`
- `points`

#### `GlueOverlayJobLoadedEvent`

Published after a glue job is prepared and loaded successfully.

Fields:
- `image`
- `image_width`
- `image_height`
- `segments`

Design intent:
- the image is the static capture background used during matching/job preparation
- the segment points stay in image space
- the dashboard can render pending/completed progress without reconstructing robot-space paths

This event is intentionally glue-specific, but still lives in `shared_contracts` because it is the canonical broker contract between the glue backend and the production dashboard.

---

## `vision_events.py` — Vision Events

Defines `VisionTopics` — the topic-string constants for the `VisionSystem` messaging integration.

```python
class VisionTopics:
    SERVICE_STATE              = "vision-service/state"
    LATEST_IMAGE               = "vision-vision_service/latest-image"
    FPS                        = "vision-vision_service/fps"
    CALIBRATION_IMAGE_CAPTURED = "vision-vision_service/calibration-image-captured"
    BRIGHTNESS_REGION          = "vision-vision_service/brightness-region"
    THRESHOLD_REGION           = "vision-vision_service/threshold"
    CALIBRATION_FEEDBACK       = "vision-vision_service/calibration-feedback"
    THRESHOLD_IMAGE            = "vision-vision_service/threshold-image"
    AUTO_BRIGHTNESS            = "vision-vision_service/auto-brightness"
    TRANSFORM_TO_CAMERA_POINT  = "vision-vision_service/transform-to-camera-point"
```

| Topic | Direction | Publisher / Subscriber |
|-------|-----------|----------------------|
| `SERVICE_STATE` | Publish | `StateManager` on every state change |
| `LATEST_IMAGE` | Publish | `MessagePublisher` on each processed frame |
| `FPS` | Publish | `MessagePublisher` at each tick |
| `CALIBRATION_FEEDBACK` | Publish | `CalibrationService` during calibration |
| `THRESHOLD_REGION` | Subscribe | `VisionSystem.on_threshold_update()` |
| `TRANSFORM_TO_CAMERA_POINT` | Subscribe | Coordinate transform requests |

See `docs/engine/vision/README.md` for the full `VisionSystem` API.

> **Known typos in source** — `vision_events.py` defines `AUTO_BRIGHTNESS_START` and `AUTO_BRIGHTNESS_STOP` with the string `"vison-auto-brightness"` (missing `i`). Both constants also share the same string value, making them indistinguishable at runtime. These are bugs in the source file, not documentation errors.

---

## `workpiece_events.py` — Workpiece Navigation Events

Defines the cross-application navigation contract that lets the workpiece library signal the workpiece editor to open a specific entry.

### Topics

```python
class WorkpieceTopics:
    OPEN_IN_EDITOR = "workpiece/open-in-editor"
```

### Payload

Raw workpiece JSON `dict` — the persisted representation of a workpiece as stored in the repository. Subscribers (the workpiece editor) deserialise it back into a `GlueWorkpiece` domain object.

| Topic | Direction | Publisher | Subscriber |
|-------|-----------|-----------|------------|
| `workpiece/open-in-editor` | Publish | `workpiece_library` controller — user double-clicks an entry | `workpiece_editor` controller — opens the entry for editing |

---

## `glue_process_events.py` — Glue Process Diagnostics

Defines the topic constant for glue-specific process diagnostics, separate from the pick-and-place diagnostics event in `pick_and_place_events.py`.

### Topics

```python
class GlueProcessTopics:
    DIAGNOSTICS = "glue/process/diagnostics"
```

### Payload

Diagnostics snapshot `dict` — structure is defined by the glue process publisher. Intended for operator-facing tooling and debugging; not used to command process behaviour.

| Topic | Direction | Publisher | Subscriber |
|-------|-----------|-----------|------------|
| `glue/process/diagnostics` | Publish | Glue process / coordinator | Diagnostic panels, logging |

---

## Design Notes

- **All payloads are frozen dataclasses**: Immutability prevents subscribers from accidentally mutating state that other subscribers are reading.
- **Timestamps use UTC**: `datetime.now(timezone.utc)` — always timezone-aware, safe for logging and comparison.
- **`WeightTopics` uses static methods, not constants**: Because cell IDs are runtime values, generating topics programmatically is cleaner than declaring `CELL_0_STATE = "weight/cell/0/state"` for each possible ID.
- **Payloads cross thread boundaries**: Both `WeightReading` and `CellStateEvent` are published from daemon threads. Using frozen dataclasses (immutable) means no locking is needed for read access.
- **Notification events are semantic, not UI-specific**: Publishers send severity, keys, params, and fallback text. They do not import Qt or decide how a dialog looks. Presentation happens in the application layer.
