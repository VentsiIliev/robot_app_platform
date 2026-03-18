# `src/engine/robot/calibration/` — Robot Calibration

Engine-level service for robot-to-camera spatial calibration. Moves the robot through a structured ArUco-marker grid, records robot positions and corresponding camera pixel coordinates, and computes the homography (image-to-robot mapping matrix) that allows the vision system to express workpiece positions in robot space.

The package also contains a separate camera-TCP offset calibration routine. That routine assumes the homography already exists, repeatedly centers one configured ArUco marker under the camera, samples several wrist `rz` rotations, solves the rotating local XY offset between the camera center and the real robot TCP, and saves the result back into `RobotSettings.tcp_x_offset` / `tcp_y_offset`.

---

## Package Structure

```
src/engine/robot/calibration/
├── camera_tcp_offset_calibration_service.py ← Standalone camera-center → TCP XY offset calibration
├── i_robot_calibration_service.py         ← IRobotCalibrationService ABC
├── robot_calibration_service.py           ← Concrete implementation (runs pipeline)
└── robot_calibration/
    ├── RobotCalibrationContext.py          ← All mutable state for one calibration run
    ├── robot_calibration_pipeline.py      ← Assembles + runs the ExecutableStateMachine
    ├── config_helpers.py                  ← RobotCalibrationConfig, AdaptiveMovementConfig, RobotCalibrationEventsConfig
    ├── CalibrationVision.py               ← Camera helper (frame capture + ArUco detection wrappers)
    ├── robot_controller.py                ← CalibrationRobotController (moves robot to target positions)
    ├── metrics.py                         ← Alignment error calculation utilities
    ├── visualizer.py                      ← Optional live debug overlay
    ├── debug.py                           ← DebugDraw helper
    ├── logging.py                         ← Log summary + completion message builders
    └── states/
        ├── robot_calibration_states.py    ← RobotCalibrationStates enum + transition rules
        ├── initializing.py
        ├── axis_mapping.py
        ├── looking_for_chessboard_handler.py
        ├── chessboard_found_handler.py
        ├── looking_for_aruco_markers_handler.py
        ├── all_aruco_found_handler.py
        ├── compute_offsets_handler.py
        ├── remaining_handlers.py          ← align_robot, iterate_alignment, done, error
        ├── handle_height_sample_state.py
        └── state_result.py
```

---

## `IRobotCalibrationService`

```python
class IRobotCalibrationService(ABC):
    def run_calibration(self)  -> tuple[bool, str]: ...
    def stop_calibration(self) -> None: ...
    def is_calibrated(self)    -> bool: ...
    def get_status(self)       -> str: ...
```

---

## `RobotCalibrationService`

The concrete implementation. Constructed with three config objects:

```python
RobotCalibrationService(
    config:          RobotCalibrationConfig,
    adaptive_config: AdaptiveMovementConfig          = None,
    events_config:   RobotCalibrationEventsConfig    = None,
)
```

`run_calibration()` builds a `RefactoredRobotCalibrationPipeline`, calls `pipeline.run()` (blocking), and returns `(success, message)`. Log messages from the calibration package are forwarded to the broker via a `_BrokerLogHandler` if `events_config` is provided.

`stop_calibration()` calls `pipeline.calibration_state_machine.stop_execution()` and `robot_service.stop_motion()`.

---

## `CameraTcpOffsetCalibrationService`

Standalone calibration service for solving the XY offset between the camera optical center and the robot TCP.

High-level flow:

1. Reload the homography from `vision_service.camera_to_robot_matrix_path`
2. Move to calibration position
3. Detect one configured ArUco marker and transform its center to robot XY with the homography
4. Move to that center at the configured approach pose
5. Repeat for several `rz` samples:
   - rotate to the next sample angle
   - detect the same marker again
   - transform its detected center with the homography
   - compare the transformed camera-center point to the current robot XY
   - back-rotate that world correction into the reference tool frame
6. Average the local XY corrections and save them into `RobotSettings.tcp_x_offset` / `tcp_y_offset`

Operational details:

- Uses the raw homography result, not `transform_to_tcp()`
- Temporarily disables `draw_contours` on the vision system while the routine runs
- Restores `draw_contours` afterward only if it had been enabled before the run
- Uses blocking robot moves with pose convergence enabled, so each sample waits for both XYZ and wrist orientation to settle before the next marker measurement is taken
- Supports stop requests by setting an internal `threading.Event` and calling `robot_service.stop_motion()`

---

## Configuration

### `RobotCalibrationConfig`

Core wiring — passed to every state handler via `RobotCalibrationContext`:

```python
RobotCalibrationConfig(
    vision_service:           IVisionService,
    robot_service:            IRobotService,
    navigation_service:       NavigationService,
    height_measuring_service: ...,
    required_ids:             set,         # ArUco marker IDs to find
    z_target:                 float,       # target Z height in mm
    robot_tool:               int,
    robot_user:               int,
    axis_mapping_config:      ...,         # optional axis direction config
    debug:                    bool = False,
    step_by_step:             bool = False,
    live_visualization:       bool = False,
)
```

### `AdaptiveMovementConfig`

PD-controller parameters for iterative alignment:

| Field | Role |
|-------|------|
| `min_step_mm` | Minimum robot move per iteration |
| `max_step_mm` | Maximum robot move per iteration |
| `target_error_mm` | Alignment success threshold |
| `max_error_ref` | Error at which `max_step_mm` is applied |
| `k` | Proportional gain |
| `derivative_scaling` | Derivative term weight |

### `RobotCalibrationEventsConfig`

Optional broker integration for live status:

```python
RobotCalibrationEventsConfig(
    broker,
    calibration_start_topic,
    calibration_stop_topic,
    calibration_image_topic,
    calibration_log_topic,    # log records forwarded here
)
```

---

## State Machine

`RefactoredRobotCalibrationPipeline` builds an `ExecutableStateMachine` from `RobotCalibrationStates` + `RobotCalibrationTransitionRules`.

### States

```
INITIALIZING
  → AXIS_MAPPING
    → LOOKING_FOR_CHESSBOARD
      → CHESSBOARD_FOUND
        → ALIGN_TO_CHESSBOARD_CENTER
          → LOOKING_FOR_ARUCO_MARKERS
            → ALL_ARUCO_FOUND
              → COMPUTE_OFFSETS
                → ALIGN_ROBOT
                  → ITERATE_ALIGNMENT ──┐
                    → DONE             │ (per-marker loop)
                    → ALIGN_ROBOT ◄────┘
                    → SAMPLE_HEIGHT
                      → DONE
ERROR (reachable from any state)
  → INITIALIZING (full reset)
```

### State Handlers

Each state is a plain function `handle_<state>_state(context: RobotCalibrationContext) -> StateResult`. All robot motion and vision operations are performed inside these functions. The `ExecutableStateMachine` calls the current state's handler and transitions based on the returned `StateResult.next_state`.

---

## `RobotCalibrationContext`

Holds all mutable state for a single calibration run. Key fields:

| Group | Fields |
|-------|--------|
| Robot positions | `robot_positions_for_calibration: dict` |
| Camera points | `camera_points_for_homography: dict` |
| Iteration tracking | `iteration_count`, `max_iterations` |
| ArUco progress | `current_marker_id`, `required_ids`, `markers_offsets_mm` |
| Chessboard | `bottom_left_chessboard_corner_px`, `chessboard_center_px` |
| Result | `image_to_robot_mapping` (the computed homography matrix) |
| Z-axis | `Z_current`, `Z_target`, `ppm_scale` |
| Stop control | `stop_event: threading.Event` |

`context.reset()` returns the context to its initial state without creating a new object — used for retries.

---

## Usage in `GlueRobotSystem`

```python
from src.robot_systems.glue.service_builders import _build_calibration_service

calibration_service = _build_calibration_service(robot_system)
# → RobotCalibrationService(
#       config=RobotCalibrationConfig(vision, robot, navigation, ...),
#       adaptive_config=AdaptiveMovementConfig(...),
#       events_config=RobotCalibrationEventsConfig(broker, RobotCalibrationTopics.*),
#   )
```

The service is stored as `robot_system._calibration_service` and exposed through `GlueOperationCoordinator.calibrate()` / `stop_calibration()`.

---

## Related

- Application-level calibration UI: [`docs/applications/calibration/README.md`](../../../applications/calibration/README.md)
- `ExecutableStateMachine`: `src/engine/process/executable_state_machine.py`
