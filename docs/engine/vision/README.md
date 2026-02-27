# `src/engine/vision/` — Vision Service

The `vision` package is a placeholder for future computer-vision capabilities. Currently it contains a minimal `VisionService` stub that only initializes a logger.

---

## Current State

**File:** `vision_service.py`

```python
class VisionService:
    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._logger.info("Vision service initialized")
```

No public methods are implemented. The class exists to reserve the module location and allow `ServiceSpec` declarations without blocking platform startup.

---

## Intended Role

When implemented, `VisionService` is expected to:

1. Interface with one or more cameras (USB, GigE, or IP cameras)
2. Expose a request/response API over the messaging bus for coordinate transformations (vision → robot space)
3. Publish detection results to topics under `vision/` namespace (see `src/shared_contracts/events/vision_events.py`)

The `request` pattern in `IMessagingService` is designed for this use case:

```python
# Planned usage (not yet implemented):
result = messaging.request("vision/transformToCamera", {"x": dx, "y": dy})
```

---

## Adding Vision Capabilities

1. Add the vision interface to `src/engine/robot/interfaces/` or a new `vision/interfaces/` module
2. Implement `VisionService` with the actual camera and processing logic
3. Register topics in `src/shared_contracts/events/vision_events.py`
4. Add `ServiceSpec(IVisionService, required=False)` to the robot system

---

## Design Note

`VisionService` is declared with `required=False` in robot system service specs, so its absence (or failure to initialize) does not prevent the platform from starting.
