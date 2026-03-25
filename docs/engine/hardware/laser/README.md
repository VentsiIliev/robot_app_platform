# `src/engine/hardware/laser/` — Laser Control

Minimal interface for hardware laser on/off control. Robot systems provide their own concrete implementation via `RobotSystemHeightMeasuringProvider.build_laser_control()`.

---

## `ILaserControl`

```python
class ILaserControl(ABC):
    def turn_on(self) -> None: ...
    def turn_off(self) -> None: ...
```

Hardware-agnostic contract for activating and deactivating the laser. Consumed by `LaserDetectionService` in `src/engine/robot/height_measuring/`.

The interface is intentionally minimal — no state query, no intensity control — because all known robot systems require only binary on/off.

---

## Design Notes

- **Robot-system-specific implementations** live in `src/robot_systems/<name>/` (e.g. a Modbus register write). The engine never imports a concrete implementation.
- **Injection point** — `RobotSystemHeightMeasuringProvider.build_laser_control()` is the only place this interface is constructed; see `docs/engine/robot/height_measuring/README.md`.
