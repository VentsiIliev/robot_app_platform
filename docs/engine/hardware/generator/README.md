# `src/engine/hardware/generator/` — Generator Controller

The `generator` package provides a minimal on/off controller for relay-switched generator hardware over any `IRegisterTransport`. It optionally tracks run time and fires a timeout callback when the generator has been on too long.

---

## Package Structure

```
generator/
├── generator_controller.py       ← GeneratorController (IGeneratorController implementation)
├── interfaces/
│   ├── i_generator_controller.py ← IGeneratorController ABC
│   └── i_generator_transport.py  ← IGeneratorTransport (semantic alias of IRegisterTransport)
├── models/
│   ├── generator_config.py       ← GeneratorConfig dataclass
│   └── generator_state.py        ← GeneratorState dataclass
├── modbus/
│   ├── modbus_generator_transport.py ← Modbus RTU transport
│   └── modbus_generator_factory.py   ← build_modbus_generator_controller() factory
└── timer/
    ├── i_generator_timer.py      ← IGeneratorTimer ABC
    └── generator_timer.py        ← GeneratorTimer + NullGeneratorTimer
```

---

## `IGeneratorController`

**File:** `interfaces/i_generator_controller.py`

```python
class IGeneratorController(ABC):
    def turn_on(self)  -> bool: ...         # True on success, False on transport error
    def turn_off(self) -> bool: ...         # True on success, False on transport error
    def get_state(self) -> GeneratorState: ...
```

All methods catch transport exceptions internally — callers receive `False` / an unhealthy `GeneratorState` rather than a raised exception.

---

## `GeneratorConfig`

**File:** `models/generator_config.py`

```python
@dataclass
class GeneratorConfig:
    relay_register:  int   = 9     # write 1 → ON, write 0 → OFF
    state_register:  int   = 10    # read; hardware convention: 0 = ON, 1 = OFF
    timeout_minutes: float = 5.0   # used by GeneratorTimer when a timeout callback is supplied
```

> **Hardware convention:** reading `0` from `state_register` means the generator is ON; reading `1` means OFF. This is the inverse of the relay write value.

---

## `GeneratorState`

**File:** `models/generator_state.py`

```python
@dataclass
class GeneratorState:
    is_on:                bool            = False
    is_healthy:           bool            = False   # False if a transport error occurred
    communication_errors: List[str]       = []
    elapsed_seconds:      Optional[float] = None    # None if timer not active

    @property
    def has_errors(self) -> bool: ...
```

`is_healthy` is `True` only when the state register was read successfully. A transport failure sets `is_healthy=False` and populates `communication_errors`.

---

## `GeneratorController`

**File:** `generator_controller.py`

```python
class GeneratorController(IGeneratorController):
    def __init__(
        self,
        transport: IGeneratorTransport,
        config:    GeneratorConfig = None,    # defaults to GeneratorConfig()
        timer:     IGeneratorTimer = None,    # defaults to NullGeneratorTimer (no tracking)
    ) -> None: ...
```

- `turn_on()` — writes `1` to `relay_register`, calls `timer.start()`.
- `turn_off()` — writes `0` to `relay_register`, calls `timer.stop()`.
- `get_state()` — reads `state_register`; maps `0 → is_on=True`, anything else → `is_on=False`.

---

## Timer

**File:** `timer/generator_timer.py`

Two implementations of `IGeneratorTimer`:

| Class | Behaviour |
|-------|-----------|
| `GeneratorTimer` | Background daemon thread; fires `on_timeout` callback when `timeout_minutes` elapses |
| `NullGeneratorTimer` | No-op; `elapsed_seconds` always returns `None` |

```python
class IGeneratorTimer(ABC):
    def start(self) -> None: ...
    def stop(self)  -> None: ...
    @property
    def elapsed_seconds(self) -> Optional[float]: ...
```

`GeneratorTimer` polls every 5 seconds. `stop()` signals the thread to exit and joins with a 2-second timeout. The timer is only activated when an `on_timeout` callback is provided to the factory.

---

## Factory

**File:** `modbus/modbus_generator_factory.py`

```python
def build_modbus_generator_controller(
    modbus_config:    ModbusConfig,
    generator_config: GeneratorConfig              = None,  # uses defaults if omitted
    on_timeout:       Optional[Callable[[], None]] = None,  # activates timer if provided
) -> IGeneratorController: ...
```

- If `on_timeout` is `None` → `NullGeneratorTimer` is used (no background thread).
- If `on_timeout` is provided → a `GeneratorTimer` is created with `timeout_minutes` from `generator_config`.

```python
# Without timeout tracking
ctrl = build_modbus_generator_controller(modbus_config)

# With timeout (e.g., auto-stop after 5 minutes)
def _on_generator_timeout() -> None:
    messaging.publish(GeneratorTopics.TIMEOUT, None)

ctrl = build_modbus_generator_controller(
    modbus_config=cfg,
    generator_config=GeneratorConfig(timeout_minutes=5.0),
    on_timeout=_on_generator_timeout,
)
```

---

## `IGeneratorTransport`

**File:** `interfaces/i_generator_transport.py`

A semantic type alias — extends `IRegisterTransport` without adding new methods. It exists solely to constrain injection sites to generator-specific transports and improve readability.

---

## Design Notes

- **No state published to broker** — `GeneratorController` does not depend on `IMessagingService`. If you need to broadcast state changes, wrap calls in a robot-system service that holds both `IGeneratorController` and `IMessagingService`.
- **Transport exceptions never propagate** — `turn_on()` / `turn_off()` / `get_state()` all catch exceptions and return safe values. Callers should check the return value or inspect `GeneratorState.is_healthy`.
- **Robot-system owns config** — register addresses and timeout are specific to the hardware board; do not rely on the `GeneratorConfig` defaults being correct for your board.
