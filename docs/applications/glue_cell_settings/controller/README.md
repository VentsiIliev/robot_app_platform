# `src/applications/glue_cell_settings/controller/` — Glue Cell Settings Controller

---

## `GlueCellSettingsController`

**File:** `glue_cell_settings_controller.py`

```python
class GlueCellSettingsController(IApplicationController):
    def __init__(
        self,
        model:  GlueCellSettingsModel,
        view:   GlueCellSettingsView,
        broker: IMessagingService,
    ): ...

    def load(self) -> None: ...
    def stop(self) -> None: ...
```

Wires view signals to model calls and subscribes to live weight/state topics from the broker. Uses a `_Bridge(QObject)` to safely deliver broker callbacks (which arrive on background threads) to the Qt main thread.

---

## `_Bridge(QObject)`

```python
class _Bridge(QObject):
    weight_updated = pyqtSignal(int, float)   # (cell_id, weight_value)
    state_updated  = pyqtSignal(int, str)     # (cell_id, state_string)
```

Created inside the controller. Its signals are connected to `view.set_cell_weight` and `view.set_cell_state`. Broker lambdas emit to the bridge. Because `_Bridge` is a `QObject`, PyQt6's cross-thread signal delivery automatically queues the calls to the main thread.

---

## Signal Wiring

| Source | Controller slot | Action |
|--------|----------------|--------|
| `view.save_requested(cell_id, flat)` | `_on_save(cell_id, flat)` | `model.save(cell_id, flat)` |
| `view.tare_requested(cell_id)` | `_on_tare(cell_id)` | `model.tare(cell_id)` |
| `view.destroyed` | `stop()` | Unsubscribe all broker topics |

---

## Broker Subscriptions

```python
# For each cell_id from model.get_cell_ids():
broker.subscribe(WeightTopics.reading(cell_id),
    lambda r, cid=cell_id: self._bridge.weight_updated.emit(cid, r.value))

broker.subscribe(WeightTopics.state(cell_id),
    lambda e, cid=cell_id: self._bridge.state_updated.emit(cid, e.state.value))
```

Subscriptions are stored in `_subs: List[Tuple[str, Callable]]` and unsubscribed in `stop()`.

---

## `load()` Sequence

```
load()
  → self._active = True
  → config = model.load()
  → for each cell_id in config.get_all_cell_ids():
       flat = model.get_cell_flat(cell_id)
       if flat: view.load_cell(cell_id, flat)
       view.set_cell_state(cell_id, "disconnected")
  → view.save_requested.connect(_on_save)
  → view.tare_requested.connect(_on_tare)
  → view.destroyed.connect(stop)
  → _subscribe()
```

---

## `stop()` Sequence

```
stop()
  → self._active = False
  → for topic, cb in reversed(_subs):
       broker.unsubscribe(topic, cb)
  → _subs.clear()
```

---

## Cross-Thread Data Flow

```
WeightCellService daemon thread publishes WeightReading
  → broker delivers to subscriber lambda (on background thread)
  → lambda emits _bridge.weight_updated(cell_id, value)
  → Qt queues signal delivery to main thread
  → view.set_cell_weight(cell_id, value)        ← called on main thread
  → CellMonitorWidget._bridge.weight_updated.emit(value)
  → CellMonitorWidget._apply_weight(value)      ← updates QLabel safely
```

---

## Design Notes

- **`_active` guard**: `_on_save` and `_on_tare` check `self._active` before acting, preventing callbacks from being processed after `stop()` is called.
- **`_Bridge` instance ownership**: `_Bridge` is stored as `self._bridge`, which keeps it alive as long as the controller is alive. Because `view._controller = controller` (set by `ApplicationFactory`), the bridge lives as long as the view.
- **Lambda subscriptions are safe here**: The lambdas passed to `broker.subscribe` are stored in `_subs`. The broker uses `weakref` for bound methods but the lambda references are kept alive by `_subs`.
