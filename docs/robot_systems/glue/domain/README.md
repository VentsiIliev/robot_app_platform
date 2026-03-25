# `src/robot_systems/glue/domain/` — Glue Domain Layer

The domain layer contains all glue-robot-specific business objects and services that sit between the robot-system declaration and the individual applications. None of these modules import Qt or depend on the platform engine directly — they work through injected interfaces.

---

## Package Structure

```
domain/
├── workpieces/
│   ├── model/
│   │   ├── glue_workpiece.py         ← GlueWorkpiece (data model + serialisation)
│   │   └── glue_workpiece_filed.py   ← GlueWorkpieceField enum (JSON field names)
│   ├── repository/
│   │   ├── i_workpiece_repository.py ← IWorkpieceRepository ABC
│   │   └── json_workpiece_repository.py ← JSON-backed implementation
│   ├── service/
│   │   ├── i_workpiece_service.py    ← IWorkpieceService ABC
│   │   └── workpiece_service.py      ← WorkpieceService
│   ├── schemas/
│   │   └── glue_workpiece_form_schema.py ← UI form schema
│   ├── glue_workpiece_library_service.py ← Library catalog management
│   └── workpiece_thumbnail.py        ← Thumbnail utilities
├── matching/
│   ├── i_matching_service.py         ← IMatchingService ABC
│   └── matching_service.py           ← MatchingService
├── dispense_channels/
│   ├── i_dispense_channel_service.py ← IDispenseChannelService ABC
│   └── dispense_channel_service.py   ← DispenseChannelService
├── glue_job_builder_service.py       ← GlueJobBuilderService + GlueJob + GlueJobSegment
├── glue_job_execution_service.py     ← GlueJobExecutionService + GlueExecutionResult
├── users/
│   └── glue_user_schema.py           ← User form schema for glue system
└── vacuum_pump/
    └── vacuum_pump_controller.py     ← (stub — not active)
```

---

## Workpieces

### `GlueWorkpiece`

**File:** `workpieces/model/glue_workpiece.py`

The core domain object for a saved workpiece template.

```python
class GlueWorkpiece(BaseWorkpiece):
    workpieceId:  str            # UUID, stable identifier
    name:         str
    description:  str
    gripperID:    int            # gripper tool index
    glueType:     str            # glue catalog type ID
    contour:      any            # numpy contour or dict with contour + settings
    height:       float          # mm above work surface
    glueQty:      float
    pickupPoint:  Any | None     # robot pose for pick-and-place
    sprayPattern: dict           # {"Contour": [...], "Fill": [...]}
```

**Key accessors:**

```python
def get_main_contour(self) -> np.ndarray: ...          # always returns shape (-1, 1, 2)
def get_spray_pattern_contours(self) -> List[dict]: ... # entries with type "Contour"
def get_spray_pattern_fills(self) -> List[dict]: ...    # entries with type "Fill"
```

**Serialisation:** `GlueWorkpiece.serialize()` / `GlueWorkpiece.deserialize()` handle numpy ↔ JSON-list conversion. `to_dict()` / `from_dict()` work with already-converted Python objects.

**Contour format:** The engine vision layer works with OpenCV-style `(-1, 1, 2)` float32 arrays. `get_main_contour()` always returns this shape, normalising any legacy format.

**Spray pattern structure:**
```json
{
  "Contour": [
    {"contour": [[x, y], ...], "settings": {"spray_width": 10, ...}}
  ],
  "Fill": [
    {"contour": [[x, y], ...], "settings": {...}}
  ]
}
```

---

### `IWorkpieceService` / `WorkpieceService`

**File:** `workpieces/service/i_workpiece_service.py`

```python
class IWorkpieceService(ABC):
    def save(self, workpiece) -> tuple[bool, str]: ...
    def load(self, workpiece_id: str): ...             # returns GlueWorkpiece | None
    def list_all(self) -> List[dict]: ...              # [{id, name, date, path}, ...]
    def delete(self, workpiece_id: str) -> tuple[bool, str]: ...
    def get_thumbnail_bytes(self, workpiece_id: str) -> Optional[bytes]: ...
    def workpiece_id_exists(self, workpiece_id: str) -> bool: ...
    def update(self, storage_id: str, data: dict) -> tuple[bool, str]: ...
```

`WorkpieceService` wraps `IWorkpieceRepository` and is injected into applications that need workpiece CRUD (`WorkpieceLibrary`, `WorkpieceEditor`, `MatchingService`, `GlueJobBuilderService`).

---

### `IWorkpieceRepository`

**File:** `workpieces/repository/i_workpiece_repository.py`

```python
class IWorkpieceRepository(ABC):
    def save(self, workpiece) -> str: ...            # returns file path
    def load(self, workpiece_id: str): ...
    def list_all(self) -> List[dict]: ...            # [{id, name, date, path}, ...]
    def delete(self, workpiece_id: str) -> bool: ...
    def get_thumbnail_bytes(self, workpiece_id: str) -> Optional[bytes]: ...
    def workpiece_id_exists(self, workpiece_id: str) -> bool: ...
```

`JsonWorkpieceRepository` stores each workpiece as a folder containing `workpiece.json` + optional `thumbnail.png`. The `id` in `list_all()` is a timestamp-based folder name.

---

## Matching

### `IMatchingService` / `MatchingService`

**File:** `matching/`

Coordinates a single matching pass: moves the robot to the capture position (external, pre-call), captures a snapshot, and runs contour matching.

```python
class IMatchingService(ABC):
    def run_matching(self) -> Tuple[dict, int, List, List]: ...
    # Returns (match_results_dict, no_match_count, matched, unmatched)

    def get_last_capture_snapshot(self) -> VisionCaptureSnapshot | None: ...
```

`MatchingService` dependencies:

| Dependency | Purpose |
|-----------|---------|
| `IVisionService` | `run_matching(workpieces, contours)` |
| `IWorkpieceService` | Load all workpiece templates |
| `ICaptureSnapshotService` | `capture_snapshot(source="matching")` to get frame + contours |

**Contour pre-processing:** `MatchingService` normalises all contours to closed `(-1, 1, 2)` float32 arrays before passing them to `IVisionService.run_matching()`. A contour is considered closed when the first and last points are within 0.5 pixels; otherwise the first point is appended.

Early exits: returns `({}, 0, [], [])` if there are no contours or no workpieces.

---

## Glue Job Builder

### `GlueJobBuilderService`

**File:** `glue_job_builder_service.py`

Converts matched workpieces into robot-executable dispensing paths.

```python
@dataclass(frozen=True)
class GlueJobSegment:
    workpiece_id:  str
    pattern_type:  str              # "Contour" or "Fill"
    segment_index: int
    points:        list[list[float]] # robot poses [x, y, z, rx, ry, rz]
    image_points:  list[tuple[float, float]]  # original pixel coords
    settings:      dict[str, Any]   # per-segment spray settings

@dataclass(frozen=True)
class GlueJob:
    segments: list[GlueJobSegment]
    segment_count: int              # property
    workpiece_count: int            # property (deduplicated by workpiece_id)
```

```python
class GlueJobBuilderService:
    def __init__(
        self,
        transformer:       ICoordinateTransformer | None = None,
        resolver:          VisionTargetResolver | None   = None,
        z_min:             float = 0.0,
        target_point_name: str   = "",
    ) -> None: ...

    def build_job(self, matched_workpieces: list[dict]) -> GlueJob: ...
    def to_process_paths(self, job: GlueJob) -> list[tuple[points, settings, metadata]]: ...
```

**Coordinate transformation:** For each image-space contour point the builder calls `VisionTargetResolver.resolve(VisionPoseRequest(...))` to obtain the robot pose. The Z coordinate is `z_min + spraying_height` from the segment settings. The fixed tool orientation is `RX=180°, RY=0°`, with `RZ` from the per-segment `rz_angle` setting.

**Pattern ordering:** Contour segments are emitted before Fill segments (`_PATTERN_ORDER = ("Contour", "Fill")`).

**`to_process_paths()` output format:**

```python
[
    (
        [[x, y, z, rx, ry, rz], ...],   # robot path points
        {"spray_width": 10, ...},         # segment settings dict
        {"workpiece_id": "...", "pattern_type": "Contour", "segment_index": 0},
    ),
    ...
]
```

This tuple format is consumed directly by `GlueProcess.set_paths()`.

---

## Glue Job Execution

### `GlueJobExecutionService`

**File:** `glue_job_execution_service.py`

Orchestrates the full preparation pipeline: navigate → capture → match → build → load → (optionally) start. Supports operator cancellation at every stage.

```python
@dataclass(frozen=True)
class GlueExecutionResult:
    success:         bool
    stage:           GlueExecutionStage   # "positioning" | "matching" | "job_build" | "load" | "start"
    message:         str
    matched_ids:     list[str]
    workpiece_count: int
    segment_count:   int
    loaded:          bool = False
    started:         bool = False
    job_summary:     dict | None = None
```

```python
class GlueJobExecutionService:
    def prepare_and_load(self, spray_on: bool) -> GlueExecutionResult: ...
    # Navigate → match → build → load into GlueProcess; does NOT start

    def prepare_load_and_start(self, spray_on: bool) -> GlueExecutionResult: ...
    # Navigate → match → build → load → start GlueProcess

    def cancel_pending(self) -> bool: ...
    # Signals cancellation and calls robot.stop_motion(); returns True if was running
```

### Execution pipeline

```
1. positioning  — move_to_calibration_position(z_offset=capture_offset)
                  + stabilization delay (default 0.5 s)
2. matching     — IMatchingService.run_matching()
3. job_build    — GlueJobBuilderService.build_job(matched_workpieces)
4. load         — GlueProcess.set_paths(process_paths, spray_on=spray_on)
                  + publish GlueOverlayJobLoadedEvent
5. start        — GlueProcess.start()  (prepare_load_and_start only)
```

A cancellation check runs between every stage. If `cancel_pending()` is called mid-run the service sets the cancel event, stops the robot, and the pipeline returns a failed result at the current stage with `message="Cancelled by operator"`.

### Overlay event

After successful load, `GlueJobExecutionService` publishes `GlueOverlayTopics.JOB_LOADED` with the capture frame and per-segment image-space paths. The dashboard preview uses this to draw the planned dispensing paths over the live camera image.

---

## Dispense Channels

### `IDispenseChannelService`

**File:** `dispense_channels/i_dispense_channel_service.py`

```python
class IDispenseChannelService(ABC):
    def resolve_motor_address(self, glue_type: str | None) -> int: ...
    # Returns motor address, or -1 if glue_type is unresolved

    def start_dispense(
        self, glue_type: str | None, settings: DispensingSegmentSettings | None = None,
    ) -> tuple[bool, int | None]: ...
    # (success, motor_address)

    def stop_dispense(
        self, glue_type: str | None, settings: DispensingSegmentSettings | None = None,
    ) -> tuple[bool, int | None]: ...
    # (success, motor_address)

    def get_last_exception(self) -> Exception | None: ...
```

`DispenseChannelService` wraps `IGlueTypeResolver` (maps glue-type string → motor address) and `GluePumpController` (low-level pump on/off). Used by the glue dispensing state machine when starting and stopping each spray segment.

---

## Design Notes

- **No Qt, no engine imports** — Domain objects and services are pure Python. They depend only on injected interfaces and the standard library.
- **`GlueWorkpiece` serialisation** — numpy arrays are not JSON-serialisable. `serialize()` / `deserialize()` handle the conversion; application code should use these rather than `to_dict()` / `from_dict()` directly.
- **`GlueJobBuilderService` is stateless** — It holds no mutable state between calls. It can be shared across calls as long as the injected `VisionTargetResolver` is thread-safe.
- **`GlueJobExecutionService` is single-threaded per call** — Only one preparation pipeline should run at a time. The `_running` flag enforces this; `cancel_pending()` returns `False` when idle.
