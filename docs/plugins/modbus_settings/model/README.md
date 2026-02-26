# `src/plugins/modbus_settings/model/` — Modbus Settings Model

---

## Classes

### `ModbusSettingsModel`

**File:** `modbus_settings_model.py`

```python
class ModbusSettingsModel(IPluginModel):
    def __init__(
        self,
        settings_service: IModbusSettingsService,
        action_service:   IModbusActionService,
    ): ...

    def load(self) -> ModbusConfig: ...
    def save(self, flat: dict) -> None: ...
    def detect_ports(self) -> List[str]: ...
    def test_connection(self) -> bool: ...
    def config_from_flat(self, flat: dict) -> ModbusConfig: ...
```

Holds `_config: Optional[ModbusConfig]` in memory after `load()`. Delegates I/O to the two service interfaces. Contains zero Qt imports.

| Method | Behaviour |
|--------|-----------|
| `load()` | Calls `settings_service.load_config()`, caches in `_config`, returns it |
| `save(flat)` | Converts flat dict → `ModbusConfig` via mapper, calls `settings_service.save_config(config)`, updates cache |
| `detect_ports()` | Delegates to `action_service.detect_ports()` → `List[str]` |
| `test_connection()` | Builds `ModbusConfig` from current flat state, calls `action_service.test_connection(config)` → `bool` |
| `config_from_flat(flat)` | Calls `ModbusSettingsMapper.from_flat_dict(flat, self._config)` without saving |

---

### `ModbusSettingsMapper`

**File:** `mapper.py`

```python
class ModbusSettingsMapper:
    @staticmethod
    def to_flat_dict(config: ModbusConfig) -> dict: ...

    @staticmethod
    def from_flat_dict(flat: dict, base: ModbusConfig) -> ModbusConfig: ...
```

Converts between `ModbusConfig` and a flat `dict` of string-keyed form values. `from_flat_dict` applies type coercions (e.g., `int(flat["baud_rate"])`) and falls back to `base` values for any missing key.

---

## Design Notes

- **Model holds two services**: Unlike the blueprint model which holds one, `ModbusSettingsModel` requires both `IModbusSettingsService` (persistence) and `IModbusActionService` (hardware) because both are needed for its five public methods.
- **`config_from_flat` does not save**: It is a helper for the controller to build a config for `test_connection()` without persisting it — the user may want to test before saving.
