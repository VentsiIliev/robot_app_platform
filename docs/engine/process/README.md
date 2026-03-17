# `src/engine/process/` — Process Lifecycle

The `process` package defines a **thread-safe, broker-integrated state machine** for any robot application process (e.g., the glue dispensing cycle). It provides a lifecycle interface and a ready-to-subclass base implementation.

> **`ProcessState`, `ProcessStateEvent`, and `ProcessTopics` have moved to `src/shared_contracts/events/process_events.py`.**
> Import them from there — not from `engine/process/`.

---

## Package Contents

| File | Key Export | Role |
|------|-----------|------|
| `i_process.py` | `IProcess` | Abstract lifecycle contract |
| `base_process.py` | `BaseProcess` | Thread-safe implementation with template hooks |
| `executable_state_machine.py` | `ExecutableStateMachine` | Small handler-driven state machine used by long-running process internals such as glue dispensing |
| `process_requirements.py` | `ProcessRequirements` | Declares which services must be available before a process can start |
| `process_sequence.py` | `ProcessSequence` | Executes a list of `IProcess` objects in order, auto-advancing on each stop |

---

## `ExecutableStateMachine` — Handler-Driven Internal Flow

`ExecutableStateMachine` is a lower-level helper than `BaseProcess`. It is used when one process needs its own internal state graph with many sub-states and explicit transition rules.

Current main user:
- `src/robot_systems/glue/processes/glue_dispensing/`

Core API:

```python
machine = (
    ExecutableStateMachineBuilder()
    .with_initial_state(MyState.START)
    .with_transition_rules(rules)
    .with_state_registry(registry)
    .with_context(context)
    .build()
)
```

Important methods:

| Method | Meaning |
|---|---|
| `reset()` | restore the machine to its initial state and clear step/snapshot metadata |
| `step()` | execute exactly one state handler and advance once |
| `start_execution(delay=0.0)` | reset, then run continuously until stop/error/invalid transition |
| `stop_execution()` | stop looped execution and set `context.stop_event` if present |
| `get_snapshot()` | return `StateMachineSnapshot` with current state, last transition, and last machine-level error |

`step()` is the main API used for manual process driving and state-machine debugging.

`StateMachineSnapshot` exposes:
- `initial_state`
- `current_state`
- `is_running`
- `step_count`
- `last_state`
- `last_next_state`
- `last_error`

This makes it possible to build interactive debugging tools without forking the machine logic.

---

## `ProcessState`, `ProcessStateEvent`, `ProcessTopics`

These types now live in `src/shared_contracts/events/process_events.py`. See [`docs/shared_contracts/events/README.md`](../../../docs/shared_contracts/events/README.md) for the full reference.

```python
# Correct import path:
from src.shared_contracts.events.process_events import ProcessState, ProcessStateEvent, ProcessTopics
```

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
    def __init__(
        self,
        process_id:      str,
        messaging:       IMessagingService,
        system_manager:  Optional[ISystemManager]        = None,
        requirements:    Optional[ProcessRequirements]   = None,
        service_checker: Optional[Callable[[str], bool]] = None,
    ): ...

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
from src.shared_contracts.events.process_events import ProcessTopics, ProcessStateEvent

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

---

## `ProcessSequence` — Ordered Process Chain

`ProcessSequence` composes multiple `IProcess` instances into a pipeline. Each process runs to completion (STOPPED) before the next is started automatically via broker subscription.

```python
class ProcessSequence:
    def __init__(
        self,
        processes: List[IProcess],   # must be non-empty
        messaging: IMessagingService,
    ) -> None: ...

    def start(self)        -> None: ...   # fresh start, or resume if current is PAUSED
    def stop(self)         -> None: ...   # stops current process; cancels pending advance
    def pause(self)        -> None: ...   # delegates to current process
    def reset_errors(self) -> None: ...   # delegates; clears current; resets index
```

### Auto-Advance Flow

```
ProcessSequence.start()
  → subscribes to ProcessTopics.state(processes[0].process_id)
  → processes[0].start()

When processes[0] publishes ProcessStateEvent(state=STOPPED):
  → _on_current_stopped() fires
  → unsubscribes from processes[0] topic
  → subscribes to processes[1] topic
  → processes[1].start()
  ... repeats until last process stops

When last process stops:
  → _current = None, _current_index = 0  (sequence complete)
```

### Resume Semantics

`start()` detects whether the current process is PAUSED:

```python
def start(self) -> None:
    with self._lock:
        if self._current is not None and self._current.state == ProcessState.PAUSED:
            process = self._current          # resume — index unchanged, no re-subscribe
        else:
            self._unsubscribe_current()
            self._current_index = 0
            self._current = self._processes[0]
            self._subscribe_current()
            process = self._current
    process.start()
```

This lets `GlueOperationCoordinator.start()` and `GlueOperationCoordinator.resume()` both call `sequence.start()` without needing to track pause state externally.

### Usage Example

```python
from src.engine.process.process_sequence import ProcessSequence

# Two-step sequence: pick_and_place → glue
sequence = ProcessSequence(
    processes = [pick_and_place_process, glue_process],
    messaging = messaging_service,
)

sequence.start()   # starts pick_and_place; when it stops, glue starts automatically
sequence.pause()   # pauses pick_and_place (or glue, whichever is active)
sequence.start()   # resumes the paused process (does not restart from index 0)
sequence.stop()    # stops current process; cancels pending auto-advance
```

### Design Notes

- **Broker-driven chaining**: the advance is triggered by a published `ProcessStateEvent` — the same event that updates the dashboard. No polling or separate thread needed.
- **Bound method subscription**: `_on_current_stopped` is a bound method kept alive by `self`. No lambda risk. The subscription is unsubscribed before advancing to avoid double-firing.
- **Thread-safe index management**: `_lock` guards `_current`, `_current_index`, and the subscribe/unsubscribe pair so concurrent stop/advance calls cannot corrupt state.
- **`GlueOperationCoordinator` uses one sequence per mode**: `SPRAY_ONLY` → `[GlueProcess]`, `PICK_AND_SPRAY` → `[PickAndPlaceProcess, GlueProcess]`. Adding a mode means adding one entry to the sequences dict — no logic changes in the runner.
