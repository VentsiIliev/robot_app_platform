# `src/plugins/modbus_settings/` — Modbus Settings Plugin

The `modbus_settings` plugin provides a GUI for configuring the Modbus RTU serial connection (port, baud rate, etc.), detecting available serial ports, and testing whether the current configuration can connect successfully. It follows the standard plugin MVC pattern with an additional `IModbusActionService` for hardware actions that are separate from settings persistence.

---

## Architecture

```
ModbusSettingsPlugin(IPlugin)
  └─ ModbusSettingsFactory(PluginFactory).build(settings_service, action_service)
       ├─ ModbusSettingsModel          ← load/save config, detect ports, test connection
       ├─ ModbusSettingsView           ← form + port list + connection status
       └─ ModbusSettingsController     ← QThread+_Worker for blocking calls
```

Two service interfaces are injected:

```
IModbusSettingsService   ← persistence: load_config / save_config
IModbusActionService     ← hardware: detect_ports / test_connection
```

---

## Class Summary

| Class | Role |
|-------|------|
| `ModbusSettingsPlugin(IPlugin)` | Bootstrap entry point; constructs both services and factory |
| `ModbusSettingsFactory(PluginFactory)` | Overrides `build()` to accept two services |
| `IModbusSettingsService` | ABC: `load_config() → ModbusConfig`, `save_config(config)` |
| `ModbusSettingsPluginService` | Wraps `ISettingsService`; key `"modbus_config"` |
| `StubModbusSettingsService` | In-memory `ModbusConfig` |
| `StubModbusActionService` | Returns hardcoded port list; `test_connection` always returns `True` |
| `ModbusSettingsModel` | `load/save/detect_ports/test_connection/config_from_flat` |
| `ModbusSettingsMapper` | `to_flat_dict / from_flat_dict` with type coercions |
| `ModbusSettingsView` | Form with signals: `save_requested / detect_ports_requested / test_connection_requested` |
| `ModbusSettingsController` | `QThread + _Worker` for blocking detect/test calls |

---

## Data Flow

### Save settings

```
User clicks Save
  → ModbusSettingsView.save_requested.emit(values_dict)
  → ModbusSettingsController._on_save(values)
  → ModbusSettingsModel.save(flat)
       └─ ModbusSettingsMapper.from_flat_dict(flat, current_config)
       └─ IModbusSettingsService.save_config(updated_config)
```

### Detect ports (blocking, off-thread)

```
User clicks Detect Ports
  → ModbusSettingsView.detect_ports_requested.emit()
  → ModbusSettingsController._on_detect_ports()
  → view.set_busy(True)
  → QThread + _Worker dispatch
       └─ ModbusSettingsModel.detect_ports()
            └─ IModbusActionService.detect_ports() → List[str]
  → (on thread finish) view.set_detected_ports(ports)
                         view.set_busy(False)
```

### Test connection (blocking, off-thread)

```
User clicks Test
  → ModbusSettingsView.test_connection_requested.emit()
  → ModbusSettingsController._on_test_connection()
  → view.set_busy(True)
  → QThread + _Worker dispatch
       └─ ModbusSettingsModel.test_connection(config)
            └─ IModbusActionService.test_connection(config) → bool
  → (on thread finish) view.set_connection_result(ok)
                         view.set_busy(False)
```

---

## Usage Example

```python
from src.plugins.modbus_settings.modbus_settings_factory import ModbusSettingsFactory
from src.plugins.modbus_settings.service.stub_modbus_settings_service import StubModbusSettingsService
from src.plugins.modbus_settings.service.stub_modbus_action_service import StubModbusActionService

widget = ModbusSettingsFactory().build(
    StubModbusSettingsService(),
    StubModbusActionService(),
)
```

Or run standalone:

```bash
python src/plugins/modbus_settings/example_usage.py
```

---

## Design Notes

- **Two service interfaces**: Settings persistence (`IModbusSettingsService`) and hardware actions (`IModbusActionService`) are deliberately separate. This allows unit-testing persistence without hardware stubs, and vice versa.
- **`ModbusSettingsFactory` overrides `build()`**: The base `PluginFactory.build()` accepts `*args`. `ModbusSettingsFactory` unpacks two positional services and passes them through to `_create_model`.
- **Blocking calls on `QThread`**: `detect_ports` and `test_connection` call `pyserial` which may block for several seconds. `ModbusSettingsController` dispatches each call in a `QThread + _Worker` pair tracked in `_active: List[Tuple[QThread, _Worker]]`. Threads are removed from `_active` on finish and cleaned up in `stop()`.

→ Subpackages: [service/](service/README.md) · [model/](model/README.md) · [view/](view/README.md) · [controller/](controller/README.md)
