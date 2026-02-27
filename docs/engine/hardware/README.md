# `src/engine/hardware/` — Hardware Overview

The `hardware` package provides drivers and service abstractions for physical I/O devices connected to the robot platform. All hardware modules publish events through `IMessagingService` rather than exposing direct callbacks to consumers.

---

## Subpackages

```
hardware/
├── communication/
│   └── modbus/         ← Serial port detection and Modbus connection testing
└── weight/
    ├── interfaces/     ← ICellTransport, ICellCalibrator, IWeightCellService
    ├── http/           ← HTTP-based transport implementation
    ├── weight_cell_service.py
    └── config.py
```

---

## Subsystem Overview

### Modbus (`communication/modbus/`)

Handles **serial port enumeration** and **connection testing** for Modbus RTU devices (e.g., the dispenser controller). It does not handle continuous data exchange — that is application-specific.

→ See [communication/modbus/README.md](communication/modbus/README.md)

### Weight Cells (`weight/`)

Manages one or more weight measurement cells. Each cell runs an independent daemon thread that:
1. Connects to the cell via a pluggable transport (currently HTTP)
2. Continuously reads weight values and publishes them to the messaging bus
3. Auto-reconnects after errors

→ See [weight/README.md](weight/README.md)

---

## Integration Pattern

Hardware services are optional. They are declared in `BaseRobotSystem.services` with `required=False`. If a hardware device is unavailable at startup, the platform continues running — applications that depend on the service are simply not loaded.

```python
# In GlueRobotSystem:
services = [
    ServiceSpec(IWeightCellService, required=False),
    ...
]
```
