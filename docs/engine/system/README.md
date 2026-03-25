# `src/engine/system/` — System Manager

The `system` package provides a single-process exclusivity lock for the robot platform. It prevents two independent processes from running concurrently when the robot can only serve one operation at a time.

---

## Package Structure

```
system/
├── i_system_manager.py   ← ISystemManager ABC
├── system_manager.py     ← SystemManager (thread-safe implementation)
└── system_state.py       ← SystemBusyState, SystemStateEvent, SystemTopics
```

---

## `ISystemManager`

**File:** `i_system_manager.py`

```python
class ISystemManager(ABC):
    @property
    def is_busy(self) -> bool: ...                      # True if any process holds the lock
    @property
    def active_process_id(self) -> Optional[str]: ...   # ID of the current owner, or None
    @property
    def state(self) -> SystemBusyState: ...             # IDLE or BUSY

    def acquire(self, process_id: str) -> bool: ...     # Try to claim the lock
    def release(self, process_id: str) -> None: ...     # Release the lock
```

### Acquire / Release semantics

| Condition | `acquire()` returns |
|-----------|---------------------|
| System idle | `True` — lock granted |
| Same `process_id` already owns the lock | `True` — idempotent re-entry |
| Different `process_id` currently owns the lock | `False` — rejected |

`release()` is a no-op if the caller does not own the lock. It never raises.

---

## `SystemManager`

**File:** `system_manager.py`

Concrete thread-safe implementation. Publishes a `SystemStateEvent` on every successful acquire or release.

```python
class SystemManager(ISystemManager):
    def __init__(self, messaging: IMessagingService) -> None: ...
```

All reads and writes to `_active` are protected by a `threading.Lock`.

---

## State Model

**File:** `system_state.py`

```python
class SystemBusyState(Enum):
    IDLE = "idle"
    BUSY = "busy"

@dataclass(frozen=True)
class SystemStateEvent:
    state:          SystemBusyState
    active_process: Optional[str]   # None when IDLE
    message:        str             # optional human-readable context
    timestamp:      datetime        # UTC, auto-set on creation

class SystemTopics:
    STATE = "vision_service/state"  # broker topic for SystemStateEvent
```

> **Note:** `SystemTopics.STATE` is currently set to `"vision_service/state"`. This is the literal topic string registered in the broker — subscribers must use this exact string.

---

## Usage Pattern

```python
# Typical usage inside a process start handler
def _on_start(self) -> None:
    if not self._system_manager.acquire(self._process_id):
        raise RuntimeError("System is busy")

def _on_stop(self) -> None:
    self._system_manager.release(self._process_id)
```

### Subscribing to state changes

```python
def load(self) -> None:
    self._messaging.subscribe(SystemTopics.STATE, self._on_system_state)

def _on_system_state(self, event: SystemStateEvent) -> None:
    self._view.set_busy(event.state == SystemBusyState.BUSY)

def stop(self) -> None:
    self._messaging.unsubscribe(SystemTopics.STATE, self._on_system_state)
```

---

## Design Notes

- **Single lock, not a queue** — rejected callers must decide whether to retry or surface an error to the user; the system manager does not queue waiters.
- **Re-entrant for same owner** — a process can call `acquire()` multiple times with the same `process_id` without deadlocking.
- **No timeout** — the lock is held until `release()` is explicitly called. Processes must ensure `release()` runs in their `_on_stop` hook even if work fails.
- **Injected everywhere as `ISystemManager`** — never import `SystemManager` directly in application code.