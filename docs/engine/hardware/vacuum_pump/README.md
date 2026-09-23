# `src/engine/hardware/vacuum_pump/` — Vacuum Pump

Interface contracts for vacuum-pump hardware control. Concrete implementations are provided by robot systems.

---

## Interfaces

### `IVacuumPumpController`

```python
class IVacuumPumpController(ABC):
    def turn_on(self) -> bool: ...
    def turn_off(self) -> bool: ...
    def turn_off_nonblocking(self) -> bool: ...
```

High-level controller interface. Returns `True` on success, `False` on failure. Consumed by `IDeviceControlService` in the `device_control` application.

`turn_off()` waits for the configured blow-off pulse to finish.
`turn_off_nonblocking()` returns after vacuum is disabled and blow-off is
activated; supporting controllers close the blow-off valve in the background.
Calling `turn_on()` or `close()` safely cancels a pending background pulse.

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
