# `src/applications/broker_debug/` — Broker Debug

Live inspector for the platform's `MessageBroker`. Lets developers see all active topics, spy on message payloads in real time, and publish arbitrary test messages — without modifying production code.

---

## MVC Structure

```
broker_debug/
├── service/
│   ├── i_broker_debug_service.py              ← IBrokerDebugService (7 methods)
│   ├── stub_broker_debug_service.py           ← Dict-backed stub with 5 pre-defined topics
│   └── broker_debug_application_service.py   ← Delegates to IMessagingService; tracks spies
├── model/
│   └── broker_debug_model.py                  ← Thin delegation
├── view/
│   └── broker_debug_view.py                   ← Topic list + message log + publish form
├── controller/
│   └── broker_debug_controller.py             ← Subscribes bridge signals → view updates
└── broker_debug_factory.py
```

---

## `IBrokerDebugService`

```python
class IBrokerDebugService(ABC):
    def get_topics(self) -> List[str]: ...
    def publish(self, topic: str, message: str) -> tuple[bool, str]: ...
    def subscribe(self, topic: str) -> tuple[bool, str]: ...
    def unsubscribe(self, topic: str) -> tuple[bool, str]: ...
    def get_topic_map(self) -> dict: ...
    def get_received_messages(self) -> List[dict]: ...
    def clear_messages(self) -> None: ...
```

---

## `BrokerDebugApplicationService`

Wraps `IMessagingService` directly. Key behaviours:

- `get_topics()` — returns the broker's live topic list (all currently subscribed topics)
- `publish(topic, message)` — calls `messaging.publish(topic, message)`
- `subscribe(topic)` — registers a spy callback that appends `{"topic": t, "payload": p}` to `_received`; tracked in `_spies: dict[str, callable]`
- `unsubscribe(topic)` — removes the spy via `messaging.unsubscribe(topic, spy)`
- `get_topic_map()` — returns the broker's internal `{topic: [subscriber, ...]}` snapshot
- `get_received_messages()` / `clear_messages()` — access the spy buffer

---

## Stub

`StubBrokerDebugService` provides 5 pre-defined topics (`_STUB_TOPICS`) for standalone development. All operations work against an in-memory dict.

---

## Wiring in `GlueRobotSystem`

```python
return WidgetApplication(
    widget_factory=lambda ms: BrokerDebugFactory(ms).build(
        BrokerDebugApplicationService(ms)
    )
)
```

`ApplicationSpec`: `folder_id=3` (Administration), icon `fa5s.project-diagram`.

---

## Design Notes

- **No model-level state**: all state lives in the service (`_spies`, `_received`). The model is a pure pass-through.
- **Spy lifetime**: spy callbacks are plain bound methods stored in `_spies`. They are unregistered on `unsubscribe()`. No lambda risk.
- **Cross-thread**: spy callbacks arrive on the broker's caller thread (potentially a hardware daemon). The controller must use a `_Bridge` with `pyqtSignal` to marshal to the Qt thread.
