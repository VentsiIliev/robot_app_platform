# `src/robot_systems/glue/dashboard/` — Glue Dashboard

The Glue Dashboard is the production-mode GUI for the glue dispensing application. It displays live weight readings for each glue cell, robot state, control buttons (Start/Stop/Pause), and action buttons (Clean, Reset Errors, Mode Toggle). It uses a custom factory function (`GlueDashboard.create()`) instead of the standard `ApplicationFactory.build()` pattern, because it requires per-cell tab construction at build time.

---

## Architecture

```
GlueDashboard.create(service, messaging_service, execution_service=None)
  ├─ GlueDashboardConfig   ← cells count, dashboard layout
  ├─ GlueDashboardModel    ← IApplicationModel facade over IGlueDashboardService
  ├─ GlueCardFactory       ← builds GlueMeterCard per cell
  ├─ GlueDashboardView     ← main widget with cards + control buttons
  ├─ DashboardPreviewWidget ← live/progress preview compositor with optional inset
  └─ GlueDashboardController
        ├─ _DashboardBridge(QObject)  ← cross-thread signal dispatch
        └─ subscriptions to: robot/state, weight/cell/*/reading, weight/cell/*/state
```

---

## Class Summary

| Class | File | Role |
|-------|------|------|
| `GlueDashboard` | `glue_dashboard.py` | Static factory: `create(coordinator, settings_service, messaging_service, ..., execution_service=None) → QWidget` |
| `IGlueDashboardService` | `service/i_glue_dashboard_service.py` | ABC: 7 commands + 5 queries |
| `GlueDashboardService` | `service/glue_dashboard_service.py` | Wraps `GlueOperationCoordinator`, settings, optional weight service, and the reusable glue execution service |
| `StubGlueDashboardService` | `service/stub_glue_dashboard_service.py` | Stub for development |
| `GlueDashboardModel` | `model/glue_dashboard_model.py` | Thin `IApplicationModel` facade — no state, delegates to service |
| `GlueDashboardView` | `view/glue_dashboard_view.py` | Main widget with card grid + control row |
| `DashboardPreviewWidget` | `ui/dashboard_preview_widget.py` | Main/inset preview that can switch between live feed and static job progress |
| `GlueDashboardController` | `controller/glue_dashboard_controller.py` | `_DashboardBridge`, broker subscriptions, state machine |
| `GlueDashboardConfig` | `config.py` | `DashboardConfig` subclass + topic namespaces + state map |

---

## `config.py` — Topics and State

### `GlueCellTopics` (app-specific, not in shared_contracts)

```python
class GlueCellTopics:
    glue_type(cell_id) → "glue/cell/{id}/glue_type"
    weight(cell_id)    → "glue/cell/{id}/weight"      # (unused — weight comes from WeightTopics)
    state(cell_id)     → "glue/cell/{id}/state"       # (unused — state comes from WeightTopics)
```

### `SystemTopics`

```python
class SystemTopics:
    APPLICATION_STATE = "vision_service/application_state"
```

> **Note:** `SYSTEM_MODE_CHANGE`, `COMMAND_CLEAN`, and `COMMAND_RESET` were removed when the dashboard was migrated to `ProcessState`. The mode toggle, clean, and reset actions are now handled entirely within the controller and model — no longer published as broker topics.

### `BUTTON_STATE_MAP`

Controls which buttons are enabled for each `ProcessState` value (from `src.engine.process.process_state`):

| State | Start | Stop | Pause | Pause Label | Mode Toggle | Clean | Reset Errors |
|-------|-------|------|-------|------------|-------------|-------|-------------|
| `idle` | ✓ | ✗ | ✗ | "Pause" | ✓ | ✓ | ✗ |
| `running` | ✗ | ✓ | ✓ | "Pause" | ✗ | ✗ | ✗ |
| `paused` | ✗ | ✓ | ✓ | "Resume" | ✗ | ✗ | ✗ |
| `stopped` | ✓ | ✗ | ✗ | "Pause" | ✓ | ✓ | ✗ |
| `error` | ✗ | ✓ | ✗ | "Pause" | ✗ | ✗ | ✓ |

Keys are `ProcessState.*.value` strings (`"idle"`, `"running"`, etc.). `_apply_button_state(state_str)` looks up the string in this map.

---

## Data Flow

### Startup

```
GlueDashboard.create(service, messaging_service, execution_service)
  → cells_count = service.get_cells_count()
  → config.GLUE_CELLS = [CardConfig(card_id=i+1) for i in range(cells_count)]
  → model = GlueDashboardModel(service, GlueDashboardConfig())
  → cards = GlueCardFactory(model).build_cards(config.GLUE_CELLS)
  → view  = GlueDashboardView(config, ACTION_BUTTONS, cards)
  → controller = GlueDashboardController(model, view, messaging_service)
  → controller.load()              ← subscribe, connect signals, initialize view
  → view._controller = controller  ← GC ownership (explicit, not from ApplicationFactory)
  → return view
```

### Live data (background thread → GUI)

```
WeightCellService daemon thread
  → WeightTopics.reading(cell_id) → WeightReading
  → lambda emits _DashboardBridge.weight_reading(card_id, value)
  → GlueDashboardController._on_weight(card_id, grams)   ← main thread
  → GlueDashboardView.set_cell_weight(card_id, grams)
```

### Control buttons

```
User clicks Start
  → GlueDashboardView.start_requested.emit()
  → GlueDashboardController._on_start()
  → run model.start() on a worker thread
  → GlueDashboardService.start()

SPRAY_ONLY mode:
  → GlueOperationCoordinator.start()
  → read GlueSettings.spray_on from SettingsID.GLUE_SETTINGS
  → GlueJobExecutionService.prepare_and_load(spray_on=<configured value>)
  → move robot to CALIBRATION with capture offset
  → wait for camera stabilization
  → capture latest contours
  → run matching
  → build job from matched workpieces
  → load GlueProcess
  → ProcessSequence starts GlueProcess

Resume/restart rule in `SPRAY_ONLY`:
  → if the active glue process is `paused`, Start/Resume resumes the current run and skips preparation
  → if glue is `stopped` or the previous run already completed, Start performs a fresh preparation pass and reloads the job before starting

PICK_AND_SPRAY mode:
  → GlueOperationCoordinator.start()
  → ProcessSequence starts PickAndPlaceProcess
  → when pick-and-place stops, the sequence transition hook prepares and loads glue
  → GlueProcess starts only if that preparation succeeds
```

---

## Broker Topics (subscribed by controller)

| Topic | Payload | View update |
|-------|---------|------------|
| `weight/cell/{cell_id}/reading` | `WeightReading` | `set_cell_weight(card_id, value)` |
| `weight/cell/{cell_id}/state` | `CellStateEvent` | `set_cell_state(card_id, state)` |
| `glue/cell/{card_id}/glue_type` | `str` | `set_cell_glue_type(card_id, glue_type)` |
| `robot/state` | `RobotStateSnapshot` | `_apply_button_state` (only when process is IDLE) |
| `process/glue/state` | `ProcessStateEvent` | `_apply_button_state(event.state.value)` |
| `process/coordinator/busy` | `ProcessBusyEvent` | `set_service_warning(message)` |
| `ui/notification` | `UserNotificationEvent` | `UserNotificationPresenter` shows a styled dialog |
| `glue/overlay/job_loaded` | `GlueOverlayJobLoadedEvent` | `set_preview_overlay(image, segments)` |

Note: broker `card_id = cell_id + 1` (cards are 1-indexed, cells 0-indexed).

Robot state only updates buttons when `_current_state == ProcessState.IDLE.value` — the process state takes priority once a process is running.

---

## Glue Change Flow

When the user clicks "Change Glue" on a `GlueMeterCard`:

```
GlueMeterCard.change_glue_requested.emit(card_id)
  → GlueDashboardController._on_glue_change(card_id)
  → create_glue_change_wizard(glue_type_names)   ← QWizard with 7 pages
  → if accepted:
       selected = wizard.page(6).get_selected_option()
       cell_id = card_id - 1
       model.change_glue(cell_id, selected)       ← persists to settings
       view.set_cell_glue_type(card_id, selected) ← updates display
       broker.publish(GlueCellTopics.glue_type(card_id), selected)
```

---

## Design Notes

- **`GlueDashboard.create()` is not a `ApplicationFactory` subclass**: The dashboard requires cell count at build time (to construct the right number of cards), which `ApplicationFactory._create_view()` can't easily support. The static `create()` method replicates the GC fix (`view._controller = controller`) manually.
- **`_view_ok()` guard**: The controller checks both `self._active` and tests the C++ pointer validity via `self._view.isVisible()`. This prevents crashes when the view is destroyed before all broker callbacks complete.
- **`MODE_TOGGLE_LABELS`**: `("Pick And Spray", "Spray Only")` — toggled by index. State managed in `_mode_index`.
- **Background Start action**: The dashboard controller dispatches Start on a worker thread so the camera view and other live UI updates remain responsive while the robot moves to the capture position and preparation runs.
- **Automated glue-only start**: In `SPRAY_ONLY`, the coordinator performs the reusable glue preparation flow before starting the glue sequence, instead of starting glue immediately with preloaded paths.
- **Resume vs restart in spray-only mode**: The coordinator only skips preparation for a truly paused glue run. If the previous spray-only run ended in `stopped`, the next Start is treated as a fresh run and goes back through capture/match/build/load.
- **Mandatory capture positioning**: The shared execution service first moves the robot to the calibration capture pose with the vision capture offset, then waits briefly before matching. If that move fails, the glue flow stops at the `positioning` stage and nothing is matched or loaded.
- **Cancellable pre-start preparation**: If the operator presses Stop or Pause during capture positioning, stabilization, matching, build, or load, the pending glue preparation is cancelled and `robot.stop_motion()` is issued before glue starts.
- **Cancellable capture-position move**: The move to the calibration capture pose now uses a cancellable wait path. Stop/Pause no longer have to wait for the navigation move to finish or time out before the dashboard becomes responsive again.
- **Settings-driven spray flag**: The automated dashboard path does not hardcode spray enable. The coordinator reads `GlueSettings.spray_on` from the shared settings service and passes that configured value into the execution service.
- **Operator failure feedback**: If automated glue-only preparation fails, `GlueDashboardService` publishes a coordinator busy/warning event with the failure stage and message so the controller surfaces it in the system status widget.
- **Reusable notification path**: The dashboard controller now owns a `UserNotificationPresenter` from `src/applications/base/`. It subscribes to `NotificationTopics.USER` and displays user-facing dialogs through the shared styled message box instead of hardcoding dialog rendering in the controller.
- **Localization pilot**: The dashboard is the first translated production view. Runtime language changes now update dashboard action labels, system status labels, card titles/tooltips, and the shared start/stop/pause controls through the engine localization service.
- **Initial localization pass**: The dashboard has two localization paths:
  - `ControlButtonsWidget` translates itself through `self.tr(...)`
  - dashboard action buttons are created from raw config labels in `pl_gui`
  Because of that, [GlueDashboardController](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/applications/dashboard/controller/glue_dashboard_controller.py) must call `_retranslate()` from `_initialize_view()` so the initial render is translated correctly when the app starts in a non-English language.
- **Preview modes**: The dashboard preview now supports a primary mode plus an optional inset:
  - primary `Live` + static progress inset
  - primary `Progress` + live inset
  - inset enabled/disabled without changing the primary mode
- **Static progress source**: `GlueJobExecutionService` publishes `GlueOverlayJobLoadedEvent` once a glue job is prepared and loaded. That event carries the static capture image and the glue segments in image coordinates.
- **Progress source of truth**: The dashboard does not guess completion from the image. It polls `GlueProcess.get_dispensing_snapshot()` through the model/service and uses `current_path_index` / `current_point_index` from the glue process snapshot to color completed vs pending path portions.
- **Continuous update**: The dashboard service also polls the live robot TCP, converts it back into image coordinates through `HomographyTransformer.inverse_transform(...)`, and passes that projected point into the preview widget. The widget uses that point to advance the active segment continuously between waypoints instead of only updating when the segment starts or ends.

→ Subpackages: [service/](service/README.md) · [model/](model/README.md) · [view/](view/README.md) · [controller/](controller/README.md)
