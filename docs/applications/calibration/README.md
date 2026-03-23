# `src/applications/calibration/` — Calibration

Single-screen workflow for calibrating the camera lens and the robot-to-camera spatial mapping. Delegates camera calibration to `VisionSystem` and robot calibration to the `GlueOperationCoordinator`.

---

## MVC Structure

```
calibration/
├── service/
│   ├── i_calibration_service.py              ← ICalibrationService
│   ├── stub_calibration_service.py           ← In-memory stub (always returns success)
│   └── calibration_application_service.py    ← Bridges vision_service + process_controller + transformer + standalone helpers
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
    def measure_marker_heights(self)       -> tuple[bool, str]: ...
    def generate_area_grid(...)            -> list[tuple[float, float]]: ...
    def verify_area_grid(...)              -> tuple[bool, str, dict]: ...
    def measure_area_grid(...)             -> tuple[bool, str]: ...
    def verify_height_model(self)          -> tuple[bool, str]: ...
    def stop_marker_height_measurement(self)-> None: ...
    def can_measure_marker_heights(self)   -> bool: ...
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
    marker_height_mapping_service: _IMarkerHeightMappingService = None,
)
```

| Method | Delegation |
|--------|-----------|
| `capture_calibration_image()` | `vision_service.capture_calibration_image()` |
| `calibrate_camera()` | `vision_service.calibrate_camera()` |
| `calibrate_robot()` | `process_controller.calibrate()` → returns `(True, "started")` |
| `calibrate_camera_and_robot()` | `calibrate_camera()` first; if success → `process_controller.calibrate()` |
| `calibrate_camera_tcp_offset()` | Requires `is_calibrated() == True`; then runs the dedicated camera-TCP offset calibration service |
| `measure_marker_heights()` | Requires homography + height calibration; runs the standalone ArUco marker height-mapping workflow |
| `generate_area_grid(...)` | Uses the user-defined 4-corner area and `rows/cols` to generate row-major grid points on the image |
| `verify_area_grid(...)` | Sequentially simulates reachability for the generated grid using `robot_service.validate_pose(start, target)` and the same anchor-recovery policy as execution |
| `measure_area_grid(...)` | Runs the standalone area-grid height-mapping workflow over the generated points |
| `verify_height_model()` | Runs 4 interior verification measurements against the saved piecewise triangle height model |
| `stop_calibration()` | `process_controller.stop_calibration()` and stops the camera-TCP offset calibrator if one is active |
| `is_calibrated()` | Checks that both matrix files exist on disk |
| `test_calibration()` | Detects ArUco markers, converts pixels to robot mm via `transformer`, moves robot to each marker |
| `stop_test_calibration()` | Sets `_stop_test = True` to abort an in-progress test |
| `stop_marker_height_measurement()` | Stops the standalone marker-height workflow and requests robot motion stop |
| `can_measure_marker_heights()` | `True` when homography exists and the height measuring service is calibrated |
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
| `transform_to_tcp(x, y)` | Robot TCP | Applying calibrated camera-to-TCP correction directly |

`transform_to_tcp` raises `RuntimeError` if camera-to-TCP offsets were not provided at construction — there is no silent fallback to zero. Those offsets come from `RobotSettings.camera_to_tcp_x_offset` / `camera_to_tcp_y_offset` and are wired in `_build_calibration_application`.

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
  → saves solved `camera_to_tcp_x_offset` / `camera_to_tcp_y_offset` back into `robot_config`

User presses "Test Calibration"
  → service.test_calibration()
  → transformer.reload() picks up latest matrix
  → detect ArUco markers in current frame
  → transformer.transform(px, py) → (x_mm, y_mm)
  → robot.move_ptp to each marker position

User presses "Measure Marker Heights"
  → service.measure_marker_heights()
  → transformer.reload() picks up latest matrix
  → repeatedly detect ArUco markers until all configured `required_ids` are collected (max 50 attempts)
  → cache marker pixels / transformed robot XY by marker ID
  → disable auto-exposure once for the whole measurement session
  → robot.move_ptp to each marker in the configured marker order
  → height_service.measure_at(x_mm, y_mm)
  → save measured samples plus marker IDs as a depth map
  → build a piecewise triangle model when the depth map is later viewed
  → restore auto-exposure when done

After a successful marker-height run
  → controller asks whether to verify the saved model
  → if confirmed, service.verify_height_model()
  → infer 4 interior verification points from the piecewise triangle model
  → height_service.measure_at(x_mm, y_mm) at each inferred point
  → log predicted height, measured height, signed error, mean abs error, max abs error

User draws a 4-corner area in the camera view
  → uses the built-in editable area overlay in `CameraView`
  → corners are stored in normalized image coordinates

User sets "Rows" / "Cols" and presses "Generate Grid"
  → service.generate_area_grid(corners_norm, rows, cols)
  → grid points are generated row-major:
    - left to right within each row
    - top row to bottom row
  → overlay points are drawn on the camera image

User presses "Verify Grid"
  → controller regenerates the current row-major grid and keeps it drawn on the preview
  → controller starts a background worker so the UI stays responsive
  → "Verify Grid" changes to "Verifying Grid..." while the worker runs
  → service.verify_area_grid(corners_norm, rows, cols)
  → if remote safety walls are currently enabled, they are disabled for the verification run and restored afterward
  → for each point, the service simulates the planned execution order:
    - try `current_simulated_state -> target`
    - if that fails, try `current_simulated_state -> anchor`
    - if anchor is reachable, try `anchor -> target`
  → after each point, the preview updates immediately:
    - green = reachable
    - red = unreachable
    - orange = not checked yet
  → results are classified as:
    - direct
    - via anchor
    - unreachable
  → unreachable grid points are redrawn in red on the camera overlay
  → the log reports the direct / via-anchor / unreachable totals and lists any non-direct points

User presses "Measure Area Grid"
  → service.measure_area_grid(corners_norm, rows, cols)
  → transformer.reload() picks up latest matrix
  → each grid point is transformed through the homography
  → height service opens one measurement session for the full run
  → if remote safety walls are currently enabled, they are disabled for this run and restored in `finally`
  → if a grid point is unreachable:
    - try recovery through point `0` of the grid (`r1c1`)
    - retry once
    - if still unreachable, skip it and continue
  → save measured samples plus grid metadata (`point_labels`, `grid_rows`, `grid_cols`)

After a successful area-grid run
  → controller enables "View Depth Map"
  → controller asks whether to verify the saved model
  → if confirmed, service.verify_height_model()
  → for area-grid data, 4 verification points are built from interior cell centers
  → predicted/measured/error report is logged the same way as marker verification

User presses "View Depth Map"
  → opens `DepthMapDialog`
  → marker-tagged data is rendered as a piecewise triangle surface
  → area-grid data is rendered as a generic depth map with saved point labels

## Calibration UI Layout

- Left side:
  - large camera preview
  - area-grid controls directly below the preview
  - generated grid overlay, with unreachable precheck points shown in red after "Verify Grid"
- Right side:
  - capture
  - calibration actions
  - test / marker-height actions
  - log

This keeps the area-selection and grid-generation controls next to the image they affect.
```

---

## Wiring in `GlueRobotSystem`

```python
vision_service = robot_system.get_optional_service(CommonServiceID.VISION)
transformer = (
    HomographyTransformer(vision_service.camera_to_robot_matrix_path)
    if vision_service is not None else None
)
camera_tcp_offset_calibrator = CameraTcpOffsetCalibrationService(...)
marker_height_mapping_service = ArucoMarkerHeightMappingService(...)
service = CalibrationApplicationService(
    vision_service     = vision_service,
    process_controller = robot_system.coordinator,
    robot_service      = robot_system.get_optional_service(CommonServiceID.ROBOT),
    height_service     = robot_system.get_optional_service(ServiceID.HEIGHT_MEASURING),
    robot_config       = robot_system._robot_config,
    calib_config       = robot_system._robot_calibration,
    transformer        = transformer,
    camera_tcp_offset_calibrator = camera_tcp_offset_calibrator,
    marker_height_mapping_service = marker_height_mapping_service,
)
return WidgetApplication(widget_factory=lambda ms: CalibrationFactory(ms, jog_service).build(service))
```

`ApplicationSpec`: `folder_id=2` (Service), icon `fa5s.crosshairs`.

---

## Related

- Engine-level robot calibration pipeline: [`docs/engine/robot/calibration/README.md`](../../engine/robot/calibration/README.md)
- `ICoordinateTransformer` / `HomographyTransformer`: [`docs/engine/core/README.md`](../../engine/core/README.md) · [`docs/engine/vision/README.md`](../../engine/vision/README.md)
- `GlueOperationCoordinator.calibrate()` / `stop_calibration()` — in `src/robot_systems/glue/processes/glue_operation_coordinator.py`
