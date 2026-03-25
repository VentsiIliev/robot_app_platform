# `src/robot_systems/glue/processes/` — Glue Processes Overview

The glue robot system runs four `BaseProcess` subclasses, all coordinated by `GlueOperationCoordinator`. Each process acquires the `ISystemManager` lock on start and releases it on stop/error.

---

## Process Summary

| Process | Class | `ProcessID` | Docs |
|---------|-------|-------------|------|
| Glue dispensing | `GlueProcess` | `GLUE` | [glue_dispensing/](glue_dispensing/README.md) |
| Pick-and-place | `PickAndPlaceProcess` | `PICK_AND_PLACE` | [pick_and_place/](pick_and_place/README.md) |
| Calibration | `RobotCalibrationProcess` | `ROBOT_CALIBRATION` | see below |
| Nozzle cleaning | `CleanProcess` | `CLEAN` | see below |

---

## `GlueOperationCoordinator`

**File:** `glue_operation_coordinator.py`

Owns all four processes and routes `start / stop / pause / resume / clean / reset_errors` to the correct process depending on the active operation mode.

```python
class GlueOperationCoordinator:
    def start(self) -> None: ...      # delegates to active mode sequence
    def stop(self) -> None: ...
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def clean(self) -> None: ...      # starts CleanProcess
    def reset_errors(self) -> None: ...
    def set_mode(self, mode: GlueOperationMode) -> None: ...
```

### Operation modes

```python
class GlueOperationMode(Enum):
    SPRAY_ONLY      = "spray_only"       # GlueProcess only
    PICK_AND_SPRAY  = "pick_and_spray"   # PickAndPlaceProcess → GlueProcess (ProcessSequence)
```

In `PICK_AND_SPRAY` mode a `ProcessSequence` chains the two processes with a `_prepare_glue_after_pick()` hook that runs between pick-and-place completion and glue start — this hook moves the robot to the spray position and loads the glue job.

---

## `RobotCalibrationProcess`

**File:** `robot_calibration_process.py`

Runs `IRobotCalibrationService.run_calibration()` on a background daemon thread.

```python
class RobotCalibrationProcess(BaseProcess):
    def __init__(
        self,
        calibration_service: IRobotCalibrationService,
        messaging:           IMessagingService,
        system_manager:      Optional[ISystemManager] = None,
        requirements:        Optional[ProcessRequirements] = None,
        service_checker:     Optional[Callable[[str], bool]] = None,
    ) -> None: ...
```

### Lifecycle

| Event | Behaviour |
|-------|-----------|
| `_on_start()` | Spawns daemon thread; calls `calibration_service.run_calibration()` |
| `_on_stop()` | Sets `_stopping = True`; calls `calibration_service.stop_calibration()` — does NOT join thread (lock is held) |
| `_on_pause()` | No-op — calibration cannot be meaningfully paused |
| `_on_resume()` | No-op |
| Thread success | Calls `self.stop()` → STOPPED |
| Thread failure | Calls `self.set_error(msg)` → ERROR |

### Thread / lock safety note

`_on_stop()` signals `stop_calibration()` but deliberately does **not** join the thread, because `_on_stop()` is called while the `BaseProcess` lock is held. The background thread calls `stop()` or `set_error()` which also need to acquire the lock — joining inside `_on_stop()` would deadlock.

---

## `CleanProcess`

**File:** `clean_process.py`

Simulates a nozzle cleaning cycle using a `threading.Timer`. In production the simulation timer would be replaced by actual movement/dispensing commands.

```python
class CleanProcess(BaseProcess):
    def __init__(
        self,
        robot_service:         IRobotService,
        messaging:             IMessagingService,
        system_manager:        Optional[ISystemManager] = None,
        requirements:          Optional[ProcessRequirements] = None,
        service_checker:       Optional[Callable[[str], bool]] = None,
        simulation_duration_s: float = 2.0,
    ) -> None: ...
```

### Lifecycle

| Event | Behaviour |
|-------|-----------|
| `_on_start()` | Starts a daemon `threading.Timer(simulation_duration_s)` |
| Timer fires | Calls `self.stop()` → STOPPED |
| `_on_pause()` | Cancels the timer |
| `_on_resume()` | Restarts the timer for the full duration |
| `_on_stop()` | Cancels the timer |
| `_on_reset_errors()` | Cancels the timer |

The `simulation_duration_s` parameter (default `2.0 s`) lets tests configure a very short duration without touching real hardware.

---

## Common Patterns

All four processes follow the same wiring conventions inherited from `BaseProcess`:

- Acquire `ISystemManager` lock on start, release on stop/error.
- Check `ProcessRequirements` (service health) before allowing transition to RUNNING.
- Long-running work executes on a daemon thread; hooks must be non-blocking.
- `set_error(msg)` transitions to ERROR; `reset_errors()` returns to IDLE.
