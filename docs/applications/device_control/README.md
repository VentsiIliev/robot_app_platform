# `src/applications/device_control/` — Device Control

Manual on/off control panel for all hardware devices connected to the glue robot: laser, vacuum pump, glue pump motors, and generator. Devices are shown as enabled/disabled based on availability reported by the service; each button press runs the underlying operation on a background thread via `BackgroundWorker`.

---

## MVC Structure

```
device_control/
├── service/
│   ├── i_device_control_service.py              ← IDeviceControlService (12 methods)
│   ├── device_control_application_service.py   ← Wraps motor, laser, vacuum, generator services
│   └── stub_device_control_service.py          ← All operations return True; no hardware
├── model/
│   └── device_control_model.py                 ← Thin delegation
├── view/
│   └── device_control_view.py                  ← Button panel per device type
├── controller/
│   └── device_control_controller.py            ← BackgroundWorker for each action
├── device_control_factory.py
└── example_usage.py
```

---

## `IDeviceControlService`

```python
@dataclass
class MotorEntry:
    name:    str
    address: int

class IDeviceControlService(ABC):
    # Availability (synchronous — no I/O)
    def is_laser_available(self) -> bool: ...
    def is_vacuum_pump_available(self) -> bool: ...
    def is_motor_available(self) -> bool: ...
    def is_generator_available(self) -> bool: ...

    # Device enumeration
    def get_motors(self) -> List[MotorEntry]: ...

    # Health (does board I/O — call from background thread)
    def get_motor_health_snapshot(self) -> Dict[int, bool]:
        """Returns {address: is_healthy} for every configured motor."""

    # Control (synchronous hardware calls)
    def laser_on(self) -> None: ...
    def laser_off(self) -> None: ...
    def vacuum_pump_on(self) -> bool: ...
    def vacuum_pump_off(self) -> bool: ...
    def motor_on(self, address: int) -> bool: ...
    def motor_off(self, address: int) -> bool: ...
    def generator_on(self) -> bool: ...
    def generator_off(self) -> bool: ...
```

---

## `DeviceControlController`

Extends both `IApplicationController` and `BackgroundWorker`. Every button click dispatches the corresponding service call to a `QThread + _Worker` via `_run_in_thread()`, so hardware I/O never blocks the Qt thread.

### `load()` sequence

1. Call `get_motors()` → `view.setup_motors(motors)` — creates per-motor on/off buttons
2. Call `is_*_available()` for each device type → `view.set_device_available(key, flag)` — shows/hides buttons
3. If motors available → `get_motor_health_snapshot()` on background thread → `view.set_device_available(f"motor_{addr}", healthy)` for each motor

### `stop()`

Calls `_stop_threads()` from `BackgroundWorker` to join any in-flight threads.

### Device key conventions used with `set_device_available()` / `set_device_active()`

| Key | Device |
|-----|--------|
| `"laser"` | Laser |
| `"vacuum_pump"` | Vacuum pump |
| `"generator"` | Generator |
| `"motor_{address}"` | Individual motor (e.g. `"motor_0"`, `"motor_2"`) |

---

## Design Notes

- **No broker subscriptions** — this application does not subscribe to any broker topics; it is purely command-oriented.
- **`BackgroundWorker` pattern** — all hardware calls (`laser_on`, `motor_on`, `get_motor_health_snapshot`) run on `QThread + _Worker`. Results are returned to the Qt thread via `on_done` callbacks.
- **Availability vs active state** — `set_device_available(key, False)` disables buttons. `set_device_active(key, True/False)` reflects the current on/off state after a completed operation.
- **Motor health on `load()`** — Motor health registers require board I/O. The health check runs once at startup to set the initial enabled state of motor buttons. It does not poll continuously.
