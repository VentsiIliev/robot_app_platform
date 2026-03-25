# `src/applications/pick_and_place_visualizer/` — Pick-and-Place Visualizer

Live monitoring and debug screen for the pick-and-place process. Shows matched workpieces, the placement plane as items are placed, real-time process state, step-by-step control, and a log panel fed from Python's logging system. Also supports a dry-run simulation mode that runs matching and placement planning without moving the robot.

---

## MVC Structure

```
pick_and_place_visualizer/
├── service/
│   ├── i_pick_and_place_visualizer_service.py        ← IPickAndPlaceVisualizerService (10 methods)
│   ├── pick_and_place_visualizer_service.py          ← Live impl: delegates to coordinator + matching
│   └── stub_pick_and_place_visualizer_service.py     ← Returns fixed SimResult, no process control
├── model/
│   └── pick_and_place_visualizer_model.py            ← Thin delegation
├── view/
│   ├── pick_and_place_visualizer_view.py             ← Split layout: camera + plane canvas + log + controls
│   └── plane_canvas.py                               ← PlaneCanvas(QWidget) — painted placement grid
├── controller/
│   └── pick_and_place_visualizer_controller.py       ← Broker subscriptions, log handler, bridge
├── pick_and_place_visualizer_factory.py
└── example_usage.py
```

---

## `IPickAndPlaceVisualizerService`

```python
@dataclass
class MatchedItem:
    workpiece_name: str
    workpiece_id:   str
    gripper_id:     int
    orientation:    float

@dataclass
class PlacedItem:
    workpiece_name: str
    gripper_id:     int
    plane_x:        float    # robot mm
    plane_y:        float    # robot mm
    width:          float
    height:         float

@dataclass
class SimResult:
    matched:         List[MatchedItem]
    placements:      List[PlacedItem]
    unmatched_count: int
    error:           Optional[str]

class IPickAndPlaceVisualizerService(ABC):
    # Simulation (dry-run, no robot motion)
    def run_simulation(self) -> SimResult: ...
    def get_plane_bounds(self) -> Tuple[float, float, float, float, float]:
        """Returns (x_min, x_max, y_min, y_max, spacing) in robot mm."""

    # Live process control
    def set_simulation(self, value: bool) -> None: ...
    def start_process(self) -> None: ...
    def stop_process(self) -> None: ...
    def pause_process(self) -> None: ...
    def reset_process(self) -> None: ...
    def get_process_state(self) -> str: ...
    def set_step_mode(self, value: bool) -> None: ...
    def is_step_mode_enabled(self) -> bool: ...
    def step_process(self) -> None: ...
```

---

## `PlaneCanvas`

**File:** `view/plane_canvas.py`

Custom `QWidget` that paints the robot placement plane and placed workpieces using `QPainter`.

```python
class PlaneCanvas(QWidget):
    def set_bounds(self, x_min, x_max, y_min, y_max, spacing) -> None: ...
    def set_placed(self, items: List[PlacedItem]) -> None: ...
    def add_item(self, item: PlacedItem) -> None: ...
    def clear(self) -> None: ...
```

Robot-space bounds are projected onto widget pixel space with a uniform scale factor. Each placed workpiece is drawn as a labelled rectangle in a rotating 6-colour palette. The label shows `G{gripper_id}\n{workpiece_name}`.

---

## Broker Subscriptions

The controller subscribes to six broker topics on `load()`, all unsubscribed on `stop()`:

| Topic | Payload | Handler |
|-------|---------|---------|
| `VisionTopics.LATEST_IMAGE` | `{"image": ndarray}` | Updates camera feed via bridge |
| `ProcessTopics.state(PICK_AND_PLACE)` | `ProcessStateEvent` | Updates process state badge |
| `PickAndPlaceTopics.WORKPIECE_PLACED` | placed event | Adds `PlacedItem` to canvas |
| `PickAndPlaceTopics.PLANE_RESET` | event | Clears canvas, resets matched list |
| `PickAndPlaceTopics.MATCH_RESULT` | list of match info | Updates matched workpiece table |
| `PickAndPlaceTopics.DIAGNOSTICS` | snapshot dict | Updates step-mode status |

All broker callbacks are on hardware/worker threads and marshal to Qt via `_Bridge(QObject)` with `pyqtSignal`.

---

## Log Panel

The controller installs a `_BridgeLogHandler(logging.Handler)` on the root logger during `load()` and removes it on `stop()`. It captures records from these logger name prefixes:

- `src.robot_systems.glue.processes.pick_and_place`
- `src.robot_systems.glue.domain.matching`
- `PickAndPlaceVisualizerService`
- `PickAndPlaceVisualizerController`

Records are formatted as `HH:MM:SS [LEVEL  ] name — message` and appended to the view's log widget.

---

## Step Mode

When step mode is enabled the pick-and-place process pauses at each configured checkpoint and waits for `step_process()` before continuing. The diagnostics subscription updates the view with:
- current checkpoint name
- whether the process is waiting for a step
- remaining step budget
- current workpiece name

---

## Simulation Mode

`set_simulation(True)` switches the live process into dry-run: matching runs normally but robot motion is skipped. `run_simulation()` is a one-shot dry-run that performs matching + placement planning offline (e.g. for debugging the placement strategy without starting the full process).

---

## Design Notes

- **`_BridgeLogHandler` lifetime** — it is installed globally on the root logger, so it captures log records from any thread. It must be removed in `stop()` to avoid holding a reference to the destroyed view.
- **`_active` flag** — all bridge slot handlers check `self._active` before touching the view, guarding against queued signals arriving after `stop()` has run.
- **Plane canvas origin** — robot Y increases upward in physical space; the canvas maps robot Y to screen Y without flipping, so the visual orientation matches the robot's coordinate system convention.
