# `src/plugins/modbus_settings/controller/` — Modbus Settings Controller

---

## `ModbusSettingsController`

**File:** `modbus_settings_controller.py`

```python
class ModbusSettingsController(IPluginController):
    def __init__(self, model: ModbusSettingsModel, view: ModbusSettingsView): ...
    def load(self) -> None: ...
    def stop(self) -> None: ...
```

Wires view signals to model calls. All blocking operations (port detection, connection test) are dispatched to worker threads to avoid freezing the Qt main thread.

---

## Signal Wiring

| View signal | Controller slot | Action |
|-------------|----------------|--------|
| `save_requested` | `_on_save(flat)` | `model.save(flat)` |
| `detect_ports_requested` | `_on_detect_ports()` | Thread dispatch → `model.detect_ports()` |
| `test_connection_requested` | `_on_test_connection()` | Thread dispatch → `model.test_connection()` |
| `destroyed` | `stop()` | Unsubscribes, stops threads |

---

## `QThread + _Worker` Pattern

`detect_ports` and `test_connection` both call `pyserial` which may block for seconds. The controller dispatches them off the GUI thread using:

```python
class _Worker(QObject):
    finished = pyqtSignal(object)   # carries the result back

    def __init__(self, fn: Callable): ...
    def run(self) -> None:
        result = self._fn()
        self.finished.emit(result)
```

Dispatch sequence:

```
_on_detect_ports()
  → view.set_busy(True)
  → thread = QThread()
    worker = _Worker(fn=self._model.detect_ports)
    worker.moveToThread(thread)
    thread.started → worker.run
    worker.finished → _on_ports_ready(ports)
    thread.start()
  → _active.append((thread, worker))

_on_ports_ready(ports)
  → view.set_detected_ports(ports)
  → view.set_busy(False)
  → thread.quit() + cleanup
```

The `_active: List[Tuple[QThread, _Worker]]` list keeps strong references to all in-flight threads. `stop()` iterates `_active` in reverse, calls `thread.quit()` and `thread.wait()`, and clears the list.

---

## `load()` Sequence

```
controller.load()
  → config = model.load()
  → view.load_config(config)
```

---

## Design Notes

- **`_active` list prevents GC**: `QThread` objects would be immediately garbage collected after `thread.start()` if not stored. Keeping them in `_active` ensures they live until the work is done.
- **No broker subscriptions**: This plugin does not subscribe to any messaging topics. `stop()` only cleans up threads.
- **`set_busy` guards**: While a thread is running, `set_busy(True)` prevents the user from triggering duplicate operations.
