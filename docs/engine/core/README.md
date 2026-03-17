# `src/engine/core/` — Messaging System

The `core` package implements the pub/sub and request/response messaging system used across the entire platform. Controllers, services, and hardware monitors communicate exclusively through this layer — they never hold direct references to each other.

---

## Architecture

```
IMessagingService   (abstract interface — the only thing consumers import)
       │
       └── MessagingService   (concrete facade — one instance per app)
                 │
                 └── MessageBroker   (singleton — holds subscriber registry)
```

**Rule:** Code outside `engine/core` must only import and use `IMessagingService`. `MessageBroker` is an internal implementation detail and must not be imported directly anywhere else.

---

## Class Diagram

```
┌─────────────────────────────────────────┐
│         IMessagingService (ABC)         │
│─────────────────────────────────────────│
│ + subscribe(topic, callback)            │
│ + unsubscribe(topic, callback)          │
│ + publish(topic, message)               │
│ + request(topic, message, timeout=1.0)  │
│ + get_subscriber_count(topic) → int     │
│ + get_all_topics() → List[str]          │
│ + clear_topic(topic)                    │
│ + clear_all()                           │
└─────────────────┬───────────────────────┘
                  │
     ┌────────────┴──────────────┐
     │      MessagingService     │
     │───────────────────────────│
     │  _broker: MessageBroker   │
     │  (delegates all calls)    │
     └────────────┬──────────────┘
                  │ creates
     ┌────────────┴──────────────┐
     │       MessageBroker       │
     │ (singleton via __new__)   │
     │───────────────────────────│
     │  _instance: cls           │
     │  subscribers: Dict[str,   │
     │    List[weakref.ref]]     │
     └───────────────────────────┘
```

---

## API Reference

### `IMessagingService`

**File:** `src/engine/core/i_messaging_service.py`

Abstract base class. Always inject and type-hint with this interface.

| Method | Signature | Description |
|--------|-----------|-------------|
| `subscribe` | `(topic: str, callback: Callable) → None` | Register a callback for a topic |
| `unsubscribe` | `(topic: str, callback: Callable) → None` | Manually deregister a callback |
| `publish` | `(topic: str, message: Any) → None` | Fire-and-forget broadcast to all subscribers |
| `request` | `(topic: str, message: Any, timeout: float = 1.0) → Any` | Synchronous call; returns first non-`None` response |
| `get_subscriber_count` | `(topic: str) → int` | Count live subscribers for a topic |
| `get_all_topics` | `() → List[str]` | List all topics with at least one live subscriber |
| `clear_topic` | `(topic: str) → None` | Remove all subscribers for a topic |
| `clear_all` | `() → None` | Remove all subscribers from all topics |

---

### `MessagingService`

**File:** `src/engine/core/messaging_service.py`

Concrete implementation. Created once by `EngineContext.build()` and passed by injection everywhere.

```python
class MessagingService(IMessagingService):
    def __init__(self): ...
```

Internally holds a `MessageBroker` instance and delegates every call to it. Swapping the underlying broker in the future only requires changes here.

---

### `MessageBroker`

**File:** `src/engine/core/message_broker.py`

Singleton. All `MessagingService` instances share the same broker.

```python
class MessageBroker(IMessagingService):
    _instance = None

    def __new__(cls): ...           # singleton guard
    def _init(self): ...            # called once on first instantiation

    def subscribe(self, topic: str, callback: Callable) -> None: ...
    def unsubscribe(self, topic: str, callback: Callable) -> None: ...
    def publish(self, topic: str, message: Any) -> None: ...
    def request(self, topic: str, message: Any, timeout: float = 1.0) -> Any: ...
    def get_subscriber_count(self, topic: str) -> int: ...
    def get_all_topics(self) -> List[str]: ...
    def clear_topic(self, topic: str) -> None: ...
    def clear_all(self) -> None: ...
```

---

## Data Flow

### Publish / Subscribe

```
Publisher                   MessageBroker               Subscriber(s)
    │                            │                           │
    │  publish("robot/state",    │                           │
    │          snapshot)         │                           │
    │──────────────────────────► │                           │
    │                            │  callback(snapshot)       │
    │                            │──────────────────────────►│
    │                            │  callback(snapshot)       │
    │                            │──────────────────────────►│ (2nd subscriber)
```

### Request / Response

```
Caller                      MessageBroker               Handler
  │                              │                          │
  │  request("vision/transform", │                          │
  │          payload)            │                          │
  │─────────────────────────────►│                          │
  │                              │  result = callback(...)  │
  │                              │─────────────────────────►│
  │                              │◄─────────────────────────│
  │◄─────────────────────────────│ (first non-None result)  │
```

---

## `ICoordinateTransformer`

**File:** `src/engine/core/i_coordinate_transformer.py`

Platform-level interface for 2D point transformations (canonical use: camera pixels → robot mm via homography). Decouples callers from NumPy and the matrix file format.

```python
class ICoordinateTransformer(ABC):
    def transform(self, x: float, y: float) -> Tuple[float, float]: ...
    def transform_to_tcp(self, x: float, y: float) -> Tuple[float, float]: ...
    def inverse_transform(self, x: float, y: float) -> Tuple[float, float]: ...
    def is_available(self) -> bool: ...
    def reload(self) -> bool: ...
```

| Method | Description |
|--------|-------------|
| `transform(x, y)` | Convert pixel to robot mm relative to **camera center**. Raises `RuntimeError` if matrix not loaded. |
| `transform_to_tcp(x, y)` | Same as `transform`, then adds TCP offset (camera → tool tip). Raises `RuntimeError` if matrix not loaded **or** if no TCP offsets were provided at construction. |
| `inverse_transform(x, y)` | Convert robot/output coordinates back into image space. Used for overlays and diagnostics that need to project live robot positions onto a captured image. |
| `is_available()` | `True` if the transformation matrix is loaded and usable. |
| `reload()` | Re-read the matrix from its source. Returns `True` if now available. Call after a calibration run writes a new matrix file. |

**Rule:** Inject `ICoordinateTransformer`; never instantiate `HomographyTransformer` inside a service. The concrete type lives in `src/engine/vision/homography_transformer.py` and is created in the wiring layer.

---

## Pub/Sub Topics Reference

Topics are defined as class constants in `src/shared_contracts/events/`.

| Topic | Class | Published By | Payload Type |
|-------|-------|-------------|--------------|
| `robot/state` | `RobotTopics.STATE` | `RobotStatePublisher` | `RobotStateSnapshot` |
| `robot/position` | `RobotTopics.POSITION` | `RobotStatePublisher` | `List[float]` (x,y,z,rx,ry,rz) |
| `robot/velocity` | `RobotTopics.VELOCITY` | `RobotStatePublisher` | `float` |
| `robot/acceleration` | `RobotTopics.ACCELERATION` | `RobotStatePublisher` | `float` |
| `weight/cell/{id}/state` | `WeightTopics.state(id)` | `WeightCellService` | `CellStateEvent` |
| `weight/cell/{id}/reading` | `WeightTopics.reading(id)` | `WeightCellService` | `WeightReading` |
| `weight/cell/all/reading` | `WeightTopics.all_readings()` | `WeightCellService` | `WeightReading` |

---

## Usage Example

```python
from src.engine.core.messaging_service import MessagingService
from src.engine.core.i_messaging_service import IMessagingService

# Startup: create once
messaging: IMessagingService = MessagingService()

# Publisher side
messaging.publish("robot/state", snapshot)

# Subscriber side — always use a named bound method, never a lambda
class MyController:
    def __init__(self, messaging: IMessagingService):
        messaging.subscribe("robot/state", self._on_state)   # bound method ✓

    def _on_state(self, snapshot) -> None:
        print(snapshot.position)

# Request / response
result = messaging.request("vision/transform", {"x": 10, "y": 20})
```

---

## Design Notes

### Singleton Pattern
`MessageBroker` uses `__new__` to ensure a single instance. Every `MessagingService` constructed anywhere in the app shares the same underlying subscriber registry. This is intentional — it allows decoupled components to communicate without being explicitly connected.

### Weak References
Subscribers are stored as `weakref.WeakMethod` (for bound methods) or `weakref.ref` (for plain functions). When the subscriber object is garbage-collected (e.g., a widget is destroyed), the dead reference is silently removed on the next `publish` or `subscribe` call. This prevents memory leaks in long-running Qt applications.

### Critical: Never Use Lambdas as Callbacks
```python
# WRONG — PyQt6 immediately GC's the lambda; callback is silently lost
messaging.subscribe("robot/state", lambda msg: self.update(msg))

# CORRECT — named bound method keeps a strong reference through the object
messaging.subscribe("robot/state", self._on_robot_state)
```

### Error Isolation
`publish` catches exceptions thrown by individual subscribers and logs them without aborting the broadcast. A broken subscriber never prevents other subscribers from receiving the message.

### `request` Semantics
- Calls subscribers in registration order
- Returns the **first non-`None`** result
- Returns `None` if no subscriber responds
- The `timeout` parameter is accepted for API compatibility but is not currently enforced (all calls are synchronous)
