# `src/robot_systems/glue/motor/` — Glue Motor Error Handling

This package provides the board-firmware-specific error codes and error decoder for the Modbus motor controller used in the glue robot. It implements the `IMotorErrorDecoder` interface from the engine hardware layer.

---

## Package Structure

```
motor/
├── glue_motor_error_codes.py   ← GlueMotorErrorCode enum (16 codes)
└── glue_motor_error_decoder.py ← GlueMotorErrorDecoder (IMotorErrorDecoder)
```

---

## `GlueMotorErrorCode`

**File:** `glue_motor_error_codes.py`

Board-firmware error codes reported by the glue motor controller. The code scheme uses a 2-digit format: the tens digit identifies the motor (1–4) and the units digit identifies the error type.

```python
class GlueMotorErrorCode(Enum):
    MOTOR_1_MISSING              = 11
    MOTOR_2_MISSING              = 21
    MOTOR_3_MISSING              = 31
    MOTOR_4_MISSING              = 41
    MOTOR_1_SHORT                = 12
    MOTOR_2_SHORT                = 22
    MOTOR_3_SHORT                = 32
    MOTOR_4_SHORT                = 42
    MOTOR_1_DRIVER_OVERHEAT      = 13
    MOTOR_2_DRIVER_OVERHEAT      = 23
    MOTOR_3_DRIVER_OVERHEAT      = 33
    MOTOR_4_DRIVER_OVERHEAT      = 43
    MOTOR_1_DRIVER_COMMUNICATION = 14
    MOTOR_2_DRIVER_COMMUNICATION = 24
    MOTOR_3_DRIVER_COMMUNICATION = 34
    MOTOR_4_DRIVER_COMMUNICATION = 44
```

### Error type digit reference

| Units digit | Meaning |
|-------------|---------|
| `1` | Motor missing (not detected on bus) |
| `2` | Short circuit |
| `3` | Driver overheat |
| `4` | Driver communication error |

### Methods

```python
def description(self) -> str: ...
# Returns human-readable string, e.g. "Motor 1 short circuit"

@classmethod
def from_code(cls, code: int) -> GlueMotorErrorCode | None: ...
# Returns None for unknown codes rather than raising ValueError
```

---

## `GlueMotorErrorDecoder`

**File:** `glue_motor_error_decoder.py`

Implements `IMotorErrorDecoder` (engine hardware interface). Converts raw integer error codes from Modbus register reads into human-readable strings.

```python
class GlueMotorErrorDecoder(IMotorErrorDecoder):
    def decode(self, error_code: int) -> str: ...
    # Returns description() for known codes, or "unknown error code {n}" for anything else
```

### Wiring

Injected into `build_modbus_motor_service()` during `GlueRobotSystem.on_start()`:

```python
motor_service = build_modbus_motor_service(
    modbus_config=modbus_config,
    motor_config=motor_config,
    error_decoder=GlueMotorErrorDecoder(),
)
```

Without a decoder, `MotorHealthChecker` logs raw integer codes. With this decoder it logs the firmware-specific human-readable descriptions.

---

## Design Notes

- **Board-specific knowledge stays in the robot system** — `GlueMotorErrorCode` and `GlueMotorErrorDecoder` live here, not in `src/engine/hardware/motor/`. The engine motor layer intentionally has no knowledge of any particular board's firmware error table.
- **`address_to_error_prefix` mapping** — The `GlueMotorConfig` in `src/robot_systems/glue/settings/device_control.py` declares an `address_to_error_prefix` dict (e.g., `{0: 1}` for motor address 0 owning errors `11–14`). `MotorHealthChecker` uses this to attribute each error code to the correct motor address.
