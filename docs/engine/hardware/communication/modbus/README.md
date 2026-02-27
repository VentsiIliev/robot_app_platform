# `src/engine/hardware/communication/modbus/` — Modbus

This package provides the configuration model and action service for Modbus RTU communication over serial ports. It handles port discovery and connection testing; application-specific read/write operations are left to higher-level code.

---

## Class Diagram

```
ISettingsSerializer[ModbusConfig]
         │
         └── ModbusConfigSerializer
                   │ serializes ↕
               ModbusConfig           ← dataclass, settings model

IModbusActionService (ABC)
         │
         └── ModbusActionService      ← concrete implementation
```

---

## API Reference

### `ModbusConfig`

**File:** `modbus.py`

Dataclass holding all parameters for a Modbus RTU connection.

```python
@dataclass
class ModbusConfig:
    port: str = 'COM5'
    baudrate: int = 115200
    bytesize: int = 8
    stopbits: int = 1
    parity: str = 'N'
    timeout: float = 0.01
    slave_address: int = 10
    max_retries: int = 30
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `from_dict` | `(data: Dict) → ModbusConfig` | Deserialize from JSON dict |
| `to_dict` | `() → Dict` | Serialize to JSON dict |
| `update_field` | `(field: str, value: Any) → None` | Update a single field by name; raises `ValueError` for unknown fields |

---

### `ModbusConfigSerializer`

**File:** `modbus.py`

Implements `ISettingsSerializer[ModbusConfig]` for JSON persistence.

| Property/Method | Description |
|----------------|-------------|
| `settings_type` | `"modbus_config"` |
| `get_default()` | Returns `ModbusConfig()` with all defaults |
| `to_dict(settings)` | Delegates to `settings.to_dict()` |
| `from_dict(data)` | Delegates to `ModbusConfig.from_dict(data)` |

---

### `IModbusActionService`

**File:** `i_modbus_action_service.py`

Abstract interface for Modbus port operations.

```python
class IModbusActionService(ABC):
    def detect_ports(self) -> List[str]: ...
    def test_connection(self, config: ModbusConfig) -> bool: ...
```

| Method | Returns | Description |
|--------|---------|-------------|
| `detect_ports()` | `List[str]` | Returns available serial port device names (e.g., `["/dev/ttyUSB0"]`) |
| `test_connection(config)` | `bool` | Opens a serial connection with the given config; `True` on success |

---

### `ModbusActionService`

**File:** `modbus_action_service.py`

Concrete implementation using `pyserial`.

```python
class ModbusActionService(IModbusActionService):
    def __init__(self): ...
    def detect_ports(self) -> List[str]: ...
    def test_connection(self, config: ModbusConfig) -> bool: ...
```

- `detect_ports()` calls `serial.tools.list_ports.comports()`. Returns `[]` on failure.
- `test_connection()` opens a `serial.Serial` context manager with the provided config parameters. Returns `False` on any exception.

---

## Data Flow

```
ModbusSettingsApplication
    │
    │  detect_ports()
    │─────────────────────────────► ModbusActionService
    │                                      │
    │                                      │  serial.tools.list_ports.comports()
    │                                      │
    │◄─────────────────────────────────────│  List[str]
    │
    │  test_connection(config)
    │─────────────────────────────► ModbusActionService
    │                                      │
    │                                      │  serial.Serial(port, baudrate, …)
    │                                      │
    │◄─────────────────────────────────────│  bool
```

---

## Usage Example

```python
from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.communication.modbus.modbus_action_service import ModbusActionService

service = ModbusActionService()

# Discover ports
ports = service.detect_ports()   # e.g., ["/dev/ttyUSB0", "/dev/ttyUSB1"]

# Test a specific config
config = ModbusConfig(port="/dev/ttyUSB0", baudrate=115200)
ok = service.test_connection(config)
print("Connected:", ok)
```

---

## Design Notes

- **`pyserial` is a soft dependency** — `detect_ports()` and `test_connection()` each import `serial` inside the function body, so the rest of the platform loads without it installed.
- **No persistent connection** — `test_connection` opens and immediately closes the port. Persistent sessions are managed by application-level Modbus libraries.
- **`ModbusConfigSerializer.settings_type = "modbus_config"`** — this string is the key used when registering the serializer in `SettingsSpec` and retrieving it via `settings_service.get("modbus_config")`.
