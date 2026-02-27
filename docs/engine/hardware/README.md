# `src/engine/hardware/` — Hardware Overview

The `hardware` package provides drivers and service abstractions for physical I/O devices connected to the robot platform. All hardware modules publish events through `IMessagingService` rather than exposing direct callbacks to consumers.

---

## Subpackages

```
hardware/
├── communication/
│   └── modbus/         ← Serial port detection, Modbus connection testing, register transport
├── motor/              ← Motor controller service (IMotorService, MotorConfig, health checker)
├── weight/
│   ├── interfaces/     ← ICellTransport, ICellCalibrator, IWeightCellService
│   ├── http/           ← HTTP-based transport implementation
│   ├── weight_cell_service.py
│   └── config.py
└── generator/          ← Generator controller service
```

---

## Subsystem Overview

### Modbus (`communication/modbus/`)

Handles **serial port enumeration**, **connection testing**, and the shared **`ModbusRegisterTransport`** used by motor and generator transports. `ModbusExceptionType` classifies all transport-level errors including `SerialException`.

→ See [communication/modbus/README.md](communication/modbus/README.md)

### Motor (`motor/`)

Manages motor controller boards over any `IMotorTransport`. Provides `IMotorService` (extends `IHealthCheckable`), `MotorConfig` (register map + motor topology), `MotorHealthChecker`, and a Modbus RTU factory.

- `is_healthy()` — serial connection state (fast, no I/O)
- `health_check(addr)` — per-motor board error query (does I/O)
- `health_check_all_configured()` — all motors declared in `MotorConfig.motor_addresses`

Error code decoding is **not** part of this layer — inject an `IMotorErrorDecoder` from the robot system that owns the board.

→ See [motor/README.md](motor/README.md)

### Weight Cells (`weight/`)

Manages one or more weight measurement cells. Each cell runs an independent daemon thread that connects via HTTP, reads weight values, and publishes them to the messaging bus. Auto-reconnects after errors.

→ See [weight/README.md](weight/README.md)

---

## Integration Pattern

Hardware services are registered via `ServiceSpec` in `BaseRobotSystem.services` with a `builder` function. If a hardware device is unavailable at startup, the platform continues running — `is_healthy()` returns `False` and the health registry tracks it.

```python
# In GlueRobotSystem:
services = [
    ServiceSpec(
        name         = "motor",
        service_type = IMotorService,
        required     = True,
        description  = "Glue pump motor service",
        builder      = _build_motor_service,
    ),
    ServiceSpec(
        name         = "weight",
        service_type = IWeightCellService,
        required     = True,
        builder      = _build_weight_cell_service,
    ),
]
```