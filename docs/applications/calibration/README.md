# `src/applications/calibration/` — Calibration

Single-screen workflow for calibrating the camera lens and the robot-to-camera spatial mapping. Delegates camera calibration to `VisionSystem` and robot calibration to the `GlueOperationCoordinator`.

---

## MVC Structure

```
calibration/
├── service/
│   ├── i_calibration_service.py              ← ICalibrationService (10 methods)
│   ├── stub_calibration_service.py           ← In-memory stub (always returns success)
│   └── calibration_application_service.py   ← Bridges vision_service + process_controller + transformer + camera TCP offset calibrator
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
    def calibrate_camera_tcp_offset(self)  -> tuple[bool, str]: ...
    def stop_calibration(self)             -> None: ...
    def is_calibrated(self)                -> bool: ...
    def test_calibration(self)             -> tuple[bool, str]: ...
    def stop_test_calibration(self)        -> None: ...
    def get_height_calibration_data(self)  -> any: ...
```

All `tuple[bool, str]` returns carry `(success, message)`.

---

## `CalibrationApplicationService`

```python
CalibrationApplicationService(
    vision_service:      IVisionService,                 # camera calibration ops
    process_controller:  _IProcessController,            # robot calibration (coordinator.calibrate / stop_calibration)
    robot_service:       _IRobotService   = None,        # move_ptp during test
    height_service:      _IHeightService  = None,
    robot_config:        _IRobotConfig    = None,
    calib_config:        _ICalibConfig    = None,
    transformer:         ICoordinateTransformer = None,  # pixel → robot mm
    camera_tcp_offset_calibrator: _ICameraTcpOffsetCalibrator = None,
)
```

| Method | Delegation |
|--------|-----------|
| `capture_calibration_image()` | `vision_service.capture_calibration_image()` |
| `calibrate_camera()` | `vision_service.calibrate_camera()` |
| `calibrate_robot()` | `process_controller.calibrate()` → returns `(True, "started")` |
| `calibrate_camera_and_robot()` | `calibrate_camera()` first; if success → `process_controller.calibrate()` |
| `calibrate_camera_tcp_offset()` | Requires `is_calibrated() == True`; then runs the dedicated camera-TCP offset calibration service |
| `stop_calibration()` | `process_controller.stop_calibration()` and stops the camera-TCP offset calibrator if one is active |
| `is_calibrated()` | Checks that both matrix files exist on disk |
| `test_calibration()` | Detects ArUco markers, converts pixels to robot mm via `transformer`, moves robot to each marker |
| `stop_test_calibration()` | Sets `_stop_test = True` to abort an in-progress test |
| `get_height_calibration_data()` | Delegates to `height_service` |

### `test_calibration` pixel-to-robot conversion

The service accepts an `ICoordinateTransformer` at construction. On each `test_calibration()` call:

1. `transformer.reload()` is called so a freshly written matrix (just produced by robot calibration) is picked up without restarting.
2. If `transformer is None` or `not transformer.is_available()`, returns `(False, "System not calibrated — run calibration first")`.
3. For each detected ArUco marker, `transformer.transform(px, py)` converts the top-left corner pixel to `(x_mm, y_mm)` in robot frame (camera-center coordinates).

**`transform` vs `transform_to_tcp`**

| Method | Result frame | When to use |
|--------|-------------|-------------|
| `transform(x, y)` | Camera optical center | Verifying the homography mapping itself |
| `transform_to_tcp(x, y)` | Tool tip (TCP) | Moving the active tool to a detected point (e.g. glue dispensing) |

`transform_to_tcp` raises `RuntimeError` if TCP offsets were not provided at construction — there is no silent fallback to zero. TCP offsets come from `RobotSettings.tcp_x_offset` / `tcp_y_offset` and are wired in `_build_calibration_application`.

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

User presses "Calibrate Camera TCP Offset"
  → service.calibrate_camera_tcp_offset()
  → requires existing camera + robot calibration files
  → runs the dedicated camera-to-TCP offset calibration routine
  → saves solved `tcp_x_offset` / `tcp_y_offset` back into `robot_config`

User presses "Test Calibration"
  → service.test_calibration()
  → transformer.reload() picks up latest matrix
  → detect ArUco markers in current frame
  → transformer.transform(px, py) → (x_mm, y_mm)
  → robot.move_ptp to each marker position
```

---

## Wiring in `GlueRobotSystem`

```python
vision_service = robot_system.get_optional_service(ServiceID.VISION)
transformer = (
    HomographyTransformer(vision_service.camera_to_robot_matrix_path)
    if vision_service is not None else None
)
camera_tcp_offset_calibrator = CameraTcpOffsetCalibrationService(...)
service = CalibrationApplicationService(
    vision_service     = vision_service,
    process_controller = robot_system.coordinator,
    robot_service      = robot_system.get_optional_service(ServiceID.ROBOT),
    height_service     = robot_system.get_optional_service(ServiceID.HEIGHT_MEASURING),
    robot_config       = robot_system._robot_config,
    calib_config       = robot_system._robot_calibration,
    transformer        = transformer,
    camera_tcp_offset_calibrator = camera_tcp_offset_calibrator,
)
return WidgetApplication(widget_factory=lambda ms: CalibrationFactory(ms, jog_service).build(service))
```

`ApplicationSpec`: `folder_id=2` (Service), icon `fa5s.crosshairs`.

---

## Related

- Engine-level robot calibration pipeline: [`docs/engine/robot/calibration/README.md`](../../engine/robot/calibration/README.md)
- `ICoordinateTransformer` / `HomographyTransformer`: [`docs/engine/core/README.md`](../../engine/core/README.md) · [`docs/engine/vision/README.md`](../../engine/vision/README.md)
- `GlueOperationCoordinator.calibrate()` / `stop_calibration()` — in `src/robot_systems/glue/processes/glue_operation_coordinator.py`
