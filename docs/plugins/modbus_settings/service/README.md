# `src/plugins/modbus_settings/service/` — Modbus Settings Services

This package contains two service interfaces and their implementations: one for settings persistence and one for hardware actions.

---

## Interfaces

### `IModbusSettingsService`

**File:** `i_modbus_settings_service.py`

```python
class IModbusSettingsService(ABC):
    @abstractmethod
    def load_config(self) -> ModbusConfig: ...

    @abstractmethod
    def save_config(self, config: ModbusConfig) -> None: ...
```

The persistence boundary. `ModbusConfig` is defined in `src/engine/hardware/communication/modbus/modbus.py`.

---

### `IModbusActionService`

**File:** `src/engine/hardware/communication/modbus/i_modbus_action_service.py`

```python
class IModbusActionService(ABC):
    @abstractmethod
    def detect_ports(self) -> List[str]: ...

    @abstractmethod
    def test_connection(self, config: ModbusConfig) -> bool: ...
```

The hardware-action boundary. `detect_ports` scans the system for available serial ports. `test_connection` attempts to open the port with the given config and returns whether it succeeded.

---

## Implementations

### `ModbusSettingsPluginService`

**File:** `modbus_settings_plugin_service.py`

```python
class ModbusSettingsPluginService(IModbusSettingsService):
    def __init__(self, settings_service: ISettingsService): ...
    def load_config(self) -> ModbusConfig:
        return self._settings.get("modbus_config")
    def save_config(self, config: ModbusConfig) -> None:
        self._settings.save("modbus_config", config)
```

The only file in this plugin allowed to import `ISettingsService`. Uses the settings key `"modbus_config"`.

---

### `StubModbusSettingsService`

**File:** `stub_modbus_settings_service.py`

In-memory implementation. Initializes with a default `ModbusConfig` and stores updates in `_config`. Used by `example_usage.py` and unit tests.

---

### `StubModbusActionService`

**File:** `stub_modbus_action_service.py`

```python
class StubModbusActionService(IModbusActionService):
    def detect_ports(self) -> List[str]:
        return ["/dev/ttyUSB0", "/dev/ttyUSB1", "COM3", "COM4"]
    def test_connection(self, config: ModbusConfig) -> bool:
        return True
```

Returns hardcoded ports and always reports connection success. Used for standalone development without hardware.

---

## Design Notes

- **Two interfaces, not one**: The plugin needs two distinct capabilities — persistence and hardware detection. Merging them would force stubs to implement unrelated methods. Keeping them separate allows either to be substituted independently.
- **`IModbusActionService` lives in the engine layer**: It is defined in `src/engine/hardware/communication/modbus/`, making it available to both the plugin and any engine-level code that needs to test connectivity without a GUI.
