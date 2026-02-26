# `src/robot_apps/glue/dashboard/` — Glue Dashboard

The Glue Dashboard is the production-mode GUI for the glue dispensing application. It displays live weight readings for each glue cell, robot state, control buttons (Start/Stop/Pause), and action buttons (Clean, Reset Errors, Mode Toggle). It uses a custom factory function (`GlueDashboard.create()`) instead of the standard `PluginFactory.build()` pattern, because it requires per-cell tab construction at build time.

---

## Architecture

```
GlueDashboard.create(service, messaging_service)
  ├─ GlueDashboardConfig   ← cells count, dashboard layout
  ├─ GlueDashboardModel    ← IPluginModel facade over IGlueDashboardService
  ├─ GlueCardFactory       ← builds GlueMeterCard per cell
  ├─ GlueDashboardView     ← main widget with cards + control buttons
  └─ GlueDashboardController
        ├─ _DashboardBridge(QObject)  ← cross-thread signal dispatch
        └─ subscriptions to: robot/state, weight/cell/*/reading, weight/cell/*/state
```

---

## Class Summary

| Class | File | Role |
|-------|------|------|
| `GlueDashboard` | `glue_dashboard.py` | Static factory: `create(service, messaging_service) → QWidget` |
| `IGlueDashboardService` | `service/i_glue_dashboard_service.py` | ABC: 7 commands + 5 queries |
| `GlueDashboardService` | `service/glue_dashboard_service.py` | Wraps `IRobotService` + `ISettingsService` + `IWeightCellService` |
| `StubGlueDashboardService` | `service/stub_glue_dashboard_service.py` | Stub for development |
| `GlueDashboardModel` | `model/glue_dashboard_model.py` | Thin `IPluginModel` facade — no state, delegates to service |
| `GlueDashboardView` | `view/glue_dashboard_view.py` | Main widget with card grid + control row |
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
    APPLICATION_STATE  = "system/application_state"
    SYSTEM_MODE_CHANGE = "system/mode_change"
    COMMAND_CLEAN      = "glue/command/clean"
    COMMAND_RESET      = "glue/command/reset_errors"
```

### `ApplicationState`

```python
class ApplicationState:
    IDLE         = "idle"
    STARTED      = "started"
    PAUSED       = "paused"
    INITIALIZING = "initializing"
    CALIBRATING  = "calibrating"
    STOPPED      = "stopped"
    ERROR        = "error"
```

### `BUTTON_STATE_MAP`

Controls which buttons are enabled for each `ApplicationState`:

| State | Start | Stop | Pause | Pause Label |
|-------|-------|------|-------|------------|
| `IDLE` | ✓ | ✗ | ✗ | "Pause" |
| `STARTED` | ✗ | ✓ | ✓ | "Pause" |
| `PAUSED` | ✗ | ✓ | ✓ | "Resume" |
| `STOPPED` / `INITIALIZING` / `CALIBRATING` | ✗ | ✗ | ✗ | "Pause" |
| `ERROR` | ✗ | ✓ | ✗ | "Pause" |

---

## Data Flow

### Startup

```
GlueDashboard.create(service, messaging_service)
  → cells_count = service.get_cells_count()
  → config.GLUE_CELLS = [CardConfig(card_id=i+1) for i in range(cells_count)]
  → model = GlueDashboardModel(service, GlueDashboardConfig())
  → cards = GlueCardFactory(model).build_cards(config.GLUE_CELLS)
  → view  = GlueDashboardView(config, ACTION_BUTTONS, cards)
  → controller = GlueDashboardController(model, view, messaging_service)
  → controller.load()              ← subscribe, connect signals, initialize view
  → view._controller = controller  ← GC ownership (explicit, not from PluginFactory)
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
  → model.start() → GlueDashboardService.start() → robot_service.enable_robot()
  → _apply_button_state(ApplicationState.STARTED)
  → broker.publish(SystemTopics.APPLICATION_STATE, ApplicationState.STARTED)
```

---

## Broker Topics (subscribed by controller)

| Topic | Payload | View update |
|-------|---------|------------|
| `weight/cell/{cell_id}/reading` | `WeightReading` | `set_cell_weight(card_id, value)` |
| `weight/cell/{cell_id}/state` | `CellStateEvent` | `set_cell_state(card_id, state)` |
| `glue/cell/{card_id}/glue_type` | `str` | `set_cell_glue_type(card_id, glue_type)` |
| `robot/state` | `RobotStateSnapshot` | `_apply_button_state(state.state)` |
| `system/application_state` | `str` or `dict` | `_apply_button_state(state)` |

Note: broker `card_id = cell_id + 1` (cards are 1-indexed, cells 0-indexed).

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

- **`GlueDashboard.create()` is not a `PluginFactory` subclass**: The dashboard requires cell count at build time (to construct the right number of cards), which `PluginFactory._create_view()` can't easily support. The static `create()` method replicates the GC fix (`view._controller = controller`) manually.
- **`_view_ok()` guard**: The controller checks both `self._active` and tests the C++ pointer validity via `self._view.isVisible()`. This prevents crashes when the view is destroyed before all broker callbacks complete.
- **`MODE_TOGGLE_LABELS`**: `("Pick And Spray", "Spray Only")` — toggled by index. State managed in `_mode_index`.

→ Subpackages: [service/](service/README.md) · [model/](model/README.md) · [view/](view/README.md) · [controller/](controller/README.md)
