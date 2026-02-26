# `src/engine/process/` — Process Lifecycle

The `process` package defines a **thread-safe, broker-integrated state machine** for any robot application process (e.g., the glue dispensing cycle). It provides the `ProcessState` enum, a typed event payload, a topic namespace, a lifecycle interface, and a ready-to-subclass base implementation.

---

## Package Contents

| File | Key Export | Role |
|------|-----------|------|
| `process_state.py` | `ProcessState`, `ProcessStateEvent`, `ProcessTopics` | Enum, payload dataclass, topic strings |
| `i_process.py` | `IProcess` | Abstract lifecycle contract |
| `base_process.py` | `BaseProcess` | Thread-safe implementation with template hooks |

---

## `ProcessState`

```python
class ProcessState(Enum):
    IDLE    = "idle"
    RUNNING = "running"
    PAUSED  = "paused"
    STOPPED = "stopped"
    ERROR   = "error"
```

---

## `ProcessStateEvent` (frozen dataclass)

Published on every state transition:

```python
@dataclass(frozen=True)
class ProcessStateEvent:
    process_id: str
    state:      ProcessState          # new state
    previous:   ProcessState          # state before transition
    message:    str      = ""         # error message or empty
    timestamp:  datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

---

## `ProcessTopics`

```python
class ProcessTopics:
    @staticmethod
    def state(process_id: str) -> str:
        return f"process/{process_id}/state"   # e.g. "process/glue/state"

    @staticmethod
    def error(process_id: str) -> str:
        return f"process/{process_id}/error"   # reserved for future use
```

| Method | Topic Pattern | Payload | Published By |
|--------|--------------|---------|-------------|
| `state(id)` | `"process/{id}/state"` | `ProcessStateEvent` | `BaseProcess._transition()` |
| `error(id)` | `"process/{id}/error"` | *(reserved)* | *(reserved)* |

> **Note:** `ProcessTopics` lives in `src/engine/process/`, not in `src/shared_contracts/`. Import it from there:
> ```python
> from src.engine.process.process_state import ProcessTopics, ProcessState
> ```

---

## `IProcess` — Lifecycle Contract

```python
class IProcess(ABC):
    @property @abstractmethod
    def process_id(self) -> str: ...

    @property @abstractmethod
    def state(self) -> ProcessState: ...

    @abstractmethod def start(self)        -> None: ...
    @abstractmethod def stop(self)         -> None: ...
    @abstractmethod def pause(self)        -> None: ...
    @abstractmethod def resume(self)       -> None: ...
    @abstractmethod def reset_errors(self) -> None: ...
```

### State Machine

```
              start()
  IDLE ──────────────────► RUNNING
   ▲                       │   │
   │  reset_errors()       │   │ stop()    pause()
   │                  stop()│   ▼           │
  ERROR ◄────────────────── STOPPED ◄──── PAUSED
   ▲        set_error()                      │
   └──────────────────── (any state) ◄───────┘
                                    start() / resume()
                                    from PAUSED → RUNNING
```

| From | `start()` | `stop()` | `pause()` | `resume()` | `reset_errors()` |
|------|-----------|---------|-----------|-----------|-----------------|
| IDLE | → RUNNING | — | — | — | — |
| RUNNING | — | → STOPPED | → PAUSED | — | — |
| PAUSED | → RUNNING | → STOPPED | — | → RUNNING | — |
| STOPPED | → RUNNING | — | — | — | — |
| ERROR | — | — | — | — | → IDLE |

> `set_error()` forces ERROR unconditionally from any state (used for hardware faults).

---

## `BaseProcess` — Thread-Safe Implementation

```python
class BaseProcess(IProcess):
    def __init__(self, process_id: str, messaging: IMessagingService): ...

    # IProcess implementation (all thread-safe via threading.Lock)
    def start(self)        -> None: ...
    def stop(self)         -> None: ...
    def pause(self)        -> None: ...
    def resume(self)       -> None: ...
    def reset_errors(self) -> None: ...

    # Force ERROR from a subclass (e.g. hardware fault)
    def set_error(self, message: str = "") -> None: ...

    # Template hooks — called while the lock is held; must be non-blocking
    def _on_start(self)        -> None: ...
    def _on_stop(self)         -> None: ...
    def _on_pause(self)        -> None: ...
    def _on_resume(self)       -> None: ...
    def _on_reset_errors(self) -> None: ...
```

### `_TRANSITIONS` Table

```python
_TRANSITIONS = {
    ProcessState.IDLE:    frozenset({ProcessState.RUNNING}),
    ProcessState.RUNNING: frozenset({ProcessState.PAUSED, ProcessState.STOPPED, ProcessState.ERROR}),
    ProcessState.PAUSED:  frozenset({ProcessState.RUNNING, ProcessState.STOPPED, ProcessState.ERROR}),
    ProcessState.STOPPED: frozenset({ProcessState.RUNNING, ProcessState.IDLE}),
    ProcessState.ERROR:   frozenset({ProcessState.IDLE}),
}
```

### `_transition()` Internals

```
_transition(target, action, message="")
  1. Check _TRANSITIONS[current] — if target not allowed: log warning and return
  2. Save previous = _state; set _state = target
  3. Call action() (the _on_* hook)
     ├─ If action() raises:
     │     _state = ERROR
     │     _publish(ERROR, previous, str(exc))
     │     return
     └─ If success:
           _publish(target, previous, message)
```

### `start()` Special Case

`start()` serves double duty — it handles both fresh starts and resumes:

```python
def start(self) -> None:
    with self._lock:
        if self._state == ProcessState.PAUSED:
            self._transition(ProcessState.RUNNING, self._on_resume)
        else:
            self._transition(ProcessState.RUNNING, self._on_start)
```

This lets the dashboard controller connect a single "Start" button to `model.start()` without needing to track pause state separately.

---

## Data Flow

```
User action (e.g. "Start" button)
  → GlueDashboardController._on_start()
  → GlueDashboardModel.start()
  → GlueDashboardService.start()   ← subclass implements IProcess
  → BaseProcess.start()
  → _transition(RUNNING, _on_start)
  → _on_start()                    ← subclass app logic here
  → _publish(RUNNING, IDLE)
  → messaging.publish("process/glue/state", ProcessStateEvent(...))

Subscriber (dashboard controller):
  → GlueDashboardController._subscribe():
       ProcessTopics.state("glue") → bridge.process_state.emit(event.state.value)
  → _on_process_state_str("running")
  → _apply_button_state("running")  ← enables Stop/Pause, disables Start
```

---

## Usage Example

```python
from src.engine.process.base_process import BaseProcess
from src.engine.process.process_state import ProcessTopics, ProcessStateEvent

class GlueProcess(BaseProcess):
    def __init__(self, robot_service, messaging):
        super().__init__("glue", messaging)
        self._robot = robot_service

    def _on_start(self) -> None:
        self._robot.enable_robot()   # non-blocking — must return quickly

    def _on_stop(self) -> None:
        self._robot.disable_robot()

    def _on_pause(self) -> None:
        self._robot.pause()

    def _on_resume(self) -> None:
        self._robot.resume()

    def _on_reset_errors(self) -> None:
        self._robot.reset_errors()

# Subscribe to state changes:
messaging.subscribe(ProcessTopics.state("glue"), lambda e: print(e.state.value))

process = GlueProcess(robot_service, messaging)
process.start()   # → _on_start() → publishes ProcessStateEvent(state=RUNNING)
```

---

## Design Notes

- **Lock held during hooks**: `_on_*` hooks are called while `self._lock` is held. They must be non-blocking. Long-running operations (robot moves, I/O) should be dispatched to a separate thread and not performed inside the hook.
- **Hook error → ERROR state**: If any `_on_*` hook raises, the state machine transitions to `ERROR` and publishes the exception message. This prevents the state machine from being stuck in an inconsistent intermediate state.
- **`set_error()` bypasses `_TRANSITIONS`**: It directly sets the state to ERROR regardless of current state. Use this from external observers (e.g., a hardware monitor thread that detects a fault).
- **`start()` handles resume**: Callers never need to check `state == PAUSED` before calling `start()` — the base class handles it. This simplifies button wiring in controllers.
- **No Qt dependency**: `BaseProcess` and `IProcess` are pure Python. They can be tested without a `QApplication`.
