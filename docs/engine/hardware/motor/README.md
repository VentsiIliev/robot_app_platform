# `src/engine/hardware/motor/` — Motor Service

The `motor` package provides a communication-agnostic motor controller service. It knows nothing about Modbus, serial ports, or board firmware — all of that is injected via interfaces.

---

## Package Structure

```
motor/
├── motor_service.py          ← MotorService (IMotorService implementation)
├── utils.py                  ← split_into_16bit helper
├── mock_runner.py            ← manual smoke-test runner (no hardware required)
├── interfaces/
│   ├── i_motor_service.py    ← IMotorService(IHealthCheckable) — ABC
│   ├── i_motor_transport.py  ← IMotorTransport — ABC
│   └── i_motor_error_decoder.py ← IMotorErrorDecoder — ABC
├── models/
│   ├── motor_config.py       ← MotorConfig dataclass (register map + topology)
│   └── motor_state.py        ← MotorState, MotorsSnapshot
├── modbus/
│   ├── modbus_motor_transport.py  ← ModbusMotorTransport(ModbusRegisterTransport, IMotorTransport)
│   └── modbus_motor_factory.py    ← build_modbus_motor_service()
└── health/
    └── motor_health_checker.py    ← MotorHealthChecker
```

---

## `IMotorService`

**File:** `interfaces/i_motor_service.py`

Extends `IHealthCheckable`. All methods are communication-agnostic.

```python
class IMotorService(IHealthCheckable):
    def is_healthy(self) -> bool: ...                                      # serial connected?
    def open(self) -> None: ...                                            # persistent connection
    def close(self) -> None: ...
    def turn_on(self, motor_address, speed, ramp_steps,
                initial_ramp_speed, initial_ramp_speed_duration) -> bool: ...
    def turn_off(self, motor_address, speed_reverse,
                 reverse_duration, ramp_steps) -> bool: ...
    def set_speed(self, motor_address: int, speed: int) -> bool: ...
    def health_check(self, motor_address: int) -> MotorState: ...
    def health_check_all(self, motor_addresses: List[int]) -> MotorsSnapshot: ...
    def health_check_all_configured(self) -> MotorsSnapshot: ...
```

### Health check distinction

| Method | I/O | Use case |
|--------|-----|----------|
| `is_healthy()` | None — connection state only | `ProcessRequirements` pre-run check |
| `health_check(addr)` | Register reads | Single motor diagnostics |
| `health_check_all(addrs)` | Register reads | Targeted subset query |
| `health_check_all_configured()` | Register reads | All motors in `MotorConfig.motor_addresses` |

---

## `MotorConfig`

**File:** `models/motor_config.py`

All register addresses are board firmware specific — **no defaults are provided**. Instantiate with explicit values in the robot system that owns the hardware.

```python
@dataclass
class MotorConfig:
    # Required — board firmware specific
    health_check_trigger_register: int
    motor_error_count_register:    int
    motor_error_registers_start:   int

    # Required — motor topology
    motor_addresses: List[int]   # e.g. [0, 2, 4, 6] for 4 motors

    # Optional — timing
    health_check_delay_s: float = 0.1
    ramp_step_delay_s:    float = 0.001

    # Optional — error code filtering (empty = no per-motor filtering)
    address_to_error_prefix: Dict[int, int] = field(default_factory=dict)
```

`motor_addresses` is the canonical motor count — `len(motor_addresses)` is the number of motors. A single-motor board uses `[0]`; a 4-motor board uses `[0, 2, 4, 6]`.

`address_to_error_prefix` maps a motor address to the leading digit of its error codes (e.g. `{0: 1}` means motor 0 owns errors `11`, `12`, `13`, `14`). Leave empty if the board does not use prefixed error codes.

---

## `IMotorErrorDecoder`

**File:** `interfaces/i_motor_error_decoder.py`

```python
class IMotorErrorDecoder(ABC):
    def decode(self, error_code: int) -> str: ...
```

Maps board firmware integer error codes to human-readable strings. **Implement in the robot system that owns the board** — not in the hardware layer. If no decoder is injected, `MotorHealthChecker` logs a `WARNING` and falls back to raw integer codes.

---

## `MotorService`

**File:** `motor_service.py`

```python
class MotorService(IMotorService):
    def __init__(
        self,
        transport:     IMotorTransport,
        config:        MotorConfig,
        error_decoder: Optional[IMotorErrorDecoder] = None,
    ) -> None: ...

    @property
    def motor_addresses(self) -> List[int]: ...
```

- `open()` / `close()` catch all transport exceptions — a failed connection logs `ERROR` but does not raise. The service stays alive with `is_healthy() == False`.
- `_ramp()` — internal; writes incremental speed values leading up to the target. Steps and initial speed are configured per call.

---

## Factory

**File:** `modbus/modbus_motor_factory.py`

```python
def build_modbus_motor_service(
    modbus_config:  ModbusConfig,
    motor_config:   MotorConfig,                      # required — no default
    error_decoder:  Optional[IMotorErrorDecoder] = None,
) -> IMotorService: ...
```

`motor_config` is **required** — there is no generic default. Every caller must supply the register map and motor topology for their specific board.

---

## `MotorHealthChecker`

**File:** `health/motor_health_checker.py`

Performs health-check cycles using board-level register reads:

1. Write `1` to `health_check_trigger_register` (triggers board self-check)
2. Wait `health_check_delay_s`
3. Read `motor_error_count_register`
4. If non-zero: read `error_count` values starting at `motor_error_registers_start`
5. Filter by `address_to_error_prefix` to find errors relevant to the queried motor
6. Decode via `IMotorErrorDecoder` and log as `WARNING`

Transport exceptions are caught; `MotorState.communication_errors` is populated instead of raising.

---

## Mock Runner

**File:** `mock_runner.py`

Standalone smoke-test script. No hardware required.

```bash
python src/engine/hardware/motor/mock_runner.y_pixels
```

Scenarios: `turn_on/off`, `persistent_connection`, `health_check_healthy`, `health_check_with_errors`, `health_check_all`, `transport_failure`.

---

## Design Notes

- **No board-specific knowledge** — register addresses, motor counts, and error tables all live in the robot system, not here.
- **Robot-system settings can own the register map** — for the glue system, `src/robot_systems/glue/settings/device_control.py` persists board registers and motor topology in `hardware/motors.json`, then `build_motor_service()` maps that into `MotorConfig`.
- **`IHealthCheckable` integration** — `MotorService` is automatically registered in `ServiceHealthRegistry` by `BaseRobotSystem._build_health_registry()`. No manual wiring needed.
- **Error decoder placement** — `ModbusMotorErrorDecoder` and `ModbusMotorErrorCode` live in `src/robot_systems/glue/motor/`, not here. The glue system owns the board firmware knowledge.
