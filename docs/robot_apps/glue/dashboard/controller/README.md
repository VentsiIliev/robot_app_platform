# `src/robot_apps/glue/dashboard/controller/` — Glue Dashboard Controller

---

## `GlueDashboardController`

**File:** `glue_dashboard_controller.py`

```python
class GlueDashboardController(IPluginController):
    def __init__(self, model: GlueDashboardModel, view: GlueDashboardView, broker: IMessagingService): ...
    def load(self) -> None: ...
    def stop(self) -> None: ...
```

The most complex controller in the platform. Manages:
- Cross-thread broker → GUI delivery via `_DashboardBridge`
- Application state machine via `BUTTON_STATE_MAP`
- Glue change wizard invocation
- Qt localization (`QCoreApplication.translate`)

---

## `_DashboardBridge(QObject)`

```python
class _DashboardBridge(QObject):
    weight_reading = pyqtSignal(int, float)   # (card_id, grams)
    cell_state     = pyqtSignal(int, str)     # (card_id, state_string)
    glue_type      = pyqtSignal(int, str)     # (card_id, glue_type_name)
    robot_state    = pyqtSignal(str)          # state string from RobotStateSnapshot
    process_state  = pyqtSignal(str)          # ProcessState.value from BaseProcess
```

Broker callbacks (background threads) emit to bridge signals. Bridge signals are connected to named slots on the main thread (auto-queued by Qt).

---

## `load()` Sequence

```
load()
  1. _active = True
  2. _wire_bridge()     ← connect bridge signals to named slot methods
  3. _subscribe()       ← subscribe broker topics; store in _subs
  4. _connect_signals() ← connect view signals to controller slots
  5. _initialize_view() ← set initial button state + load per-cell state/glue_type
  6. view.destroyed.connect(stop)
```

---

## Broker Subscriptions

`_PROCESS_ID = "glue"` — the process identifier used for all `ProcessTopics` calls.

For each `CardConfig` in `config.GLUE_CELLS` (card_id 1-indexed, cell_id = card_id - 1):

```
WeightTopics.reading(cell_id)       → lambda r: bridge.weight_reading.emit(card_id, r.value)
WeightTopics.state(cell_id)         → lambda e: bridge.cell_state.emit(card_id, e.state.value)
GlueCellTopics.glue_type(card_id)   → lambda t: bridge.glue_type.emit(card_id, t)
RobotTopics.STATE                   → lambda s: bridge.robot_state.emit(getattr(s, "state", "") or "")
ProcessTopics.state("glue")         → lambda e: bridge.process_state.emit(e.state.value)
```

Robot state updates buttons only when `_current_state == ProcessState.IDLE.value` (process state takes priority once a process starts).

---

## State Machine

`_apply_button_state(state_str)` looks up the `ProcessState.value` string in `BUTTON_STATE_MAP` and calls the corresponding view setters (`set_start_enabled`, `set_stop_enabled`, `set_pause_enabled`, `set_pause_text`, `set_action_button_enabled`).

`_current_state` tracks the last known state string and is initialized to `ProcessState.IDLE.value`.

### State Transitions via Buttons

| Button | Controller slot | Model call | State change published by |
|--------|----------------|-----------|--------------------------|
| Start | `_on_start()` | `model.start()` | `BaseProcess` via `ProcessTopics.state("glue")` |
| Stop | `_on_stop()` | `model.stop()` | `BaseProcess` via `ProcessTopics.state("glue")` |
| Pause (or Resume) | `_on_pause()` | `model.pause()` or `model.start()` | `BaseProcess` via `ProcessTopics.state("glue")` |

`_on_pause()` checks `_current_state`: if already `PAUSED`, it calls `model.start()` (which delegates to `BaseProcess.start()` which detects PAUSED → calls `_on_resume`).

### Action Buttons

| `action_id` | Effect |
|-------------|--------|
| `"mode_toggle"` | Toggle `_mode_index` 0↔1; `view.set_action_button_text()`; `model.set_mode(label)` |
| `"clean"` | `model.clean()` |
| `"reset_errors"` | `model.reset_errors()` |

Action buttons are enabled/disabled by `BUTTON_STATE_MAP` — no broker topics are published for these actions.

---

## `stop()` Sequence

```
stop()
  1. _active = False    ← disarms all slots before any unsubscribe
  2. for topic, cb in reversed(_subs): broker.unsubscribe(topic, cb)
  3. _subs.clear()
  4. _disconnect_signals()
```

---

## `_view_ok()` Guard

```python
def _view_ok(self) -> bool:
    if not self._active:
        return False
    try:
        _ = self._view.isVisible()   # forces C++ pointer check
        return True
    except RuntimeError:
        return False
```

All bridge slots and view-mutating methods guard with `_view_ok()` to prevent crashes if the Qt widget is destroyed before a pending broker callback runs.

---

## Design Notes

- **Localization**: `_t(text)` calls `QCoreApplication.translate("GlueDashboard", text)`. The `_retranslate()` slot is connected to `view.language_changed` and re-applies all translated strings to buttons.
- **`_active` flag before unsubscribing**: Setting `_active = False` first disarms all slots so that any pending broker callbacks that arrive during `stop()` will see `_active = False` and return immediately without touching the (possibly-destroyed) view.
