# `src/plugins/modbus_settings/view/` — Modbus Settings View

---

## `ModbusSettingsView`

**File:** `modbus_settings_view.py`

```python
class ModbusSettingsView(IPluginView):
    save_requested             = pyqtSignal(dict)
    detect_ports_requested     = pyqtSignal()
    test_connection_requested  = pyqtSignal()
```

Pure Qt widget. Renders a settings form for Modbus configuration, a port detection button, and a connection test button. Contains zero business logic.

### Outbound Signals

| Signal | Emitted when |
|--------|-------------|
| `save_requested(dict)` | User clicks Save |
| `detect_ports_requested()` | User clicks Detect Ports |
| `test_connection_requested()` | User clicks Test Connection |

### Inbound Setters

| Method | Effect |
|--------|--------|
| `load_config(config: ModbusConfig)` | Populates all form fields from `config` |
| `get_values() → dict` | Returns current form field values as a flat dict |
| `set_detected_ports(ports: List[str])` | Populates the port dropdown with detected serial ports |
| `set_connection_result(ok: bool)` | Shows success / failure indicator |
| `set_busy(busy: bool)` | Disables / enables the detect and test buttons |

---

## `modbus_settings_schema.py`

Defines the field schema for the settings form — groups of labeled fields with their types, labels, and validation rules. Consumed by the platform's `SettingsView` component to auto-build the form UI.

---

## Design Notes

- **`set_busy(True)`** is called before any blocking action (`detect_ports_requested`, `test_connection_requested`). The controller sets it back to `False` after the worker thread finishes.
- The view has no knowledge of threads or services — it only emits signals and accepts data through setters.
