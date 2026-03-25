# `src/engine/hardware/vacuum_pump/` — Vacuum Pump

Interface contracts for vacuum-pump hardware control. Concrete implementations are provided by robot systems.

---

## Interfaces

### `IVacuumPumpController`

```python
class IVacuumPumpController(ABC):
    def turn_on(self) -> bool: ...
    def turn_off(self) -> bool: ...
```

High-level controller interface. Returns `True` on success, `False` on failure. Consumed by `IDeviceControlService` in the `device_control` application.

### `IVacuumPumpTransport`

```python
class IVacuumPumpTransport(IRegisterTransport):
    """Semantic type alias — constrains injection sites to vacuum-pump-specific transports."""
```

Extends `IRegisterTransport` (from `hardware/communication/`) without adding methods. Acts as a semantic type alias so injection sites are typed to vacuum-pump transports specifically rather than any register transport.

---

## Design Notes

- **Separation of controller and transport** — `IVacuumPumpController` is the application-facing contract; `IVacuumPumpTransport` is the hardware-communication contract. Concrete implementations typically implement the controller by writing to the transport.
- **No engine-level concrete implementation** — all concrete vacuum pump controllers live in `src/robot_systems/<name>/`. The engine provides only the contracts.
