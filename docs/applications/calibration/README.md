# `src/applications/calibration/` — Calibration

Single-screen workflow for calibrating the camera lens and the robot-to-camera spatial mapping. Delegates camera calibration to `VisionSystem` and robot calibration to the `GlueOperationCoordinator`.

---

## MVC Structure

```
calibration/
├── service/
│   ├── i_calibration_service.py              ← ICalibrationService (5 methods)
│   ├── stub_calibration_service.py           ← In-memory stub (always returns success)
│   └── calibration_application_service.py   ← Bridges vision_service + process_controller
├── model/
│   └── calibration_model.py                  ← Thin delegation to ICalibrationService
├── view/
│   └── calibration_view.py                   ← Buttons + status display
├── controller/
│   └── calibration_controller.py             ← Wires button signals → model methods
└── calibration_factory.py
```

---

## `ICalibrationService`

```python
class ICalibrationService(ABC):
    def capture_calibration_image(self)    -> tuple[bool, str]: ...
    def calibrate_camera(self)             -> tuple[bool, str]: ...
    def calibrate_robot(self)              -> tuple[bool, str]: ...
    def calibrate_camera_and_robot(self)   -> tuple[bool, str]: ...
    def stop_calibration(self)             -> None: ...
```

All `tuple[bool, str]` returns carry `(success, message)`.

---

## `CalibrationApplicationService`

```python
CalibrationApplicationService(
    vision_service:      IVisionService,       # camera calibration ops
    process_controller:  _IProcessController,  # robot calibration (coordinator.calibrate / stop_calibration)
)
```

| Method | Delegation |
|--------|-----------|
| `capture_calibration_image()` | `vision_service.capture_calibration_image()` |
| `calibrate_camera()` | `vision_service.calibrate_camera()` |
| `calibrate_robot()` | `process_controller.calibrate()` → returns `(True, "started")` |
| `calibrate_camera_and_robot()` | `calibrate_camera()` first; if success → `process_controller.calibrate()` |
| `stop_calibration()` | `process_controller.stop_calibration()` |

---

## Calibration Workflow

```
User presses "Capture"
  → controller._on_capture()
  → model.capture_calibration_image()
  → vision_service.captureCalibrationImage()
  → returns (success, message) → displayed in status label

User presses "Calibrate Camera"
  → vision_service.calibrateCamera()
  → updates cameraMatrix, cameraDist, perspectiveMatrix in VisionSystem

User presses "Calibrate Robot"
  → coordinator.calibrate()
  → starts RobotCalibrationProcess (see engine/robot/calibration/)
  → publishes process state events — controller subscribes via broker
```

---

## Wiring in `GlueRobotSystem`

```python
service = CalibrationApplicationService(
    vision_service    = robot_system.get_optional_service(ServiceID.VISION),
    process_controller = robot_system.coordinator,
)
return WidgetApplication(widget_factory=lambda ms: CalibrationFactory(ms).build(service))
```

`ApplicationSpec`: `folder_id=2` (Service), icon `fa5s.crosshairs`.

---

## Related

- Engine-level robot calibration pipeline: [`docs/engine/robot/calibration/README.md`](../../engine/robot/calibration/README.md)
- `GlueOperationCoordinator.calibrate()` / `stop_calibration()` — in `src/robot_systems/glue/processes/glue_operation_coordinator.py`
