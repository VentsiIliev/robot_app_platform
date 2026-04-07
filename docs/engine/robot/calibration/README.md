# `src/engine/robot/calibration/` — Robot Calibration

Engine-level service for robot-to-camera spatial calibration. Moves the robot through a structured ArUco-marker grid, records robot positions and corresponding camera pixel coordinates, and computes the homography (image-to-robot mapping matrix) that allows the vision system to express workpiece positions in robot space.

The package also contains a separate camera-TCP offset calibration routine. That routine assumes the homography already exists, repeatedly centers one configured ArUco marker under the camera, samples several wrist `rz` rotations, solves the rotating local XY offset between the camera center and the real robot TCP, and saves the result back into `RobotSettings.camera_to_tcp_x_offset` / `camera_to_tcp_y_offset`.

The main robot-calibration package has also been refactored into clearer seams:

- state orchestration in the pipeline and per-state handler modules
- dataset/model construction in `model_fitting.py`
- report/artifact generation in `calibration_report.py`
- centralized failure handling in `states/error_handling.py`
- swappable overlay rendering in `overlay_renderer.py`
- live window / display-thread handling in `live_feed.py`

It also contains two standalone post-calibration surface-mapping routines:

- ArUco marker height mapping
- user-defined area-grid height mapping

Both are intended for use after homography calibration is already complete: they transform image-space reference points into robot XY with the computed homography, move the robot to each point, trigger the height-measuring service, and save the collected `[x, y, height_mm]` samples as a depth map.

The main robot calibration pipeline can now also capture camera-TCP offset samples while it is already iteratively centering ArUco markers. This avoids relying on a homography at a mismatched Z plane: after a marker is aligned, the pipeline moves to one reference pose at `approach_rz`, then rotates through the configured `rz` sample angles, re-centers the same marker using the existing iterative alignment loop, accumulates local XY offset samples, and saves the solved TCP offset at the end of the run if the sample spread is acceptable.

Important sampling rule:
- the reference pose is a baseline only and is not used as a solved TCP-offset sample
- `iterations = N` means `reference pose + N rotated captures`
- final mean/std checks only use rotated samples where `sample_rz != reference_rz`

This in-main-calibration capture is best-effort:
- it only runs on up to `max_markers_for_tcp_capture` successfully calibrated markers
- if one marker fails to produce TCP-offset samples, the calibration logs a warning and continues with the next marker instead of failing the whole robot calibration

Important math rule:
- `world_dx/world_dy` are the robot XY corrections needed to bring the camera center back over the fixed marker after a wrist rotation
- the saved camera-relative-to-TCP offset is solved from the rigid-body relation `t_world = (R_ref - R_sample) * c_local`
- the local offset is therefore not obtained by simply inverse-rotating the measured world correction

---

## Package Structure

```
src/engine/robot/calibration/
├── aruco_marker_height_mapping_service.py  ← Standalone ArUco marker / area-grid → height-map workflow
├── camera_tcp_offset_calibration_service.py ← Standalone camera-center → TCP XY offset calibration
├── i_robot_calibration_service.py         ← IRobotCalibrationService ABC
├── robot_calibration_service.py           ← Concrete implementation (runs pipeline)
└── robot_calibration/
    ├── RobotCalibrationContext.py          ← All mutable state for one calibration run
    ├── robot_calibration_pipeline.py      ← Assembles + runs the ExecutableStateMachine
    ├── model_fitting.py                   ← Builds partitioned calibration datasets + model inputs
    ├── calibration_report.py              ← Builds report payloads and saves calibration artifacts
    ├── config_helpers.py                  ← RobotCalibrationConfig, AdaptiveMovementConfig, RobotCalibrationEventsConfig
    ├── CalibrationVision.py               ← Camera helper (frame capture + ArUco detection wrappers)
    ├── robot_controller.py                ← CalibrationRobotController (moves robot to target positions)
    ├── metrics.py                         ← Alignment error calculation utilities
    ├── tcp_offset_capture.py              ← Main-calibration TCP-offset capture/solve helper
    ├── overlay.py                         ← Overlay compatibility wrappers
    ├── overlay_renderer.py                ← Renderer seam: OpenCV / no-op / future UI renderer
    ├── live_feed.py                       ← Live visualization queue + display thread
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
        ├── align_robot.py
        ├── iterate_alignment.py
        ├── tcp_offset_state.py
        ├── terminal_states.py
        ├── fallback_targets.py
        ├── error_handling.py
        ├── handle_height_sample_state.py
        └── state_result.py
```

### Current calibration-model split

The final calibration solve is intentionally partitioned:

1. base homography is fit from `homography_marker_ids` only
2. residual / TPS correction is fit from `residual_marker_ids` only
3. validation metrics are computed from `validation_marker_ids` only

This separation now lives in `model_fitting.py` and is reported through `calibration_report.py`, so swapping model implementations no longer requires changing the state-machine code.

### Visualization split

Live visualization is now separated into two layers:

- `overlay_renderer.py`: draws semantic calibration status onto a frame
- `live_feed.py`: publishes frames, manages the display queue, and owns the OpenCV window thread

This makes it possible to keep the calibration pipeline unchanged while later wiring the same overlay/status data into the Calibration application UI instead of an OpenCV window.

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

`run_calibration()` refreshes the live `robot_calibration` and `robot_config` values from `SettingsService`, builds a `RefactoredRobotCalibrationPipeline`, calls `pipeline.run()` (blocking), and returns `(success, message)`. This means changing calibration settings in the UI affects the next calibration run immediately without restarting the application. Log messages from the calibration package are forwarded to the broker via a `_BrokerLogHandler` if `events_config` is provided.

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
   - solve the rigid-body equation `t_world = (R_ref - R_sample) * c_local` for the fixed local offset
6. Average the local XY corrections and save them into `RobotSettings.camera_to_tcp_x_offset` / `camera_to_tcp_y_offset`

Operational details:

- Uses the raw homography result, not `transform_to_tcp()`
- Temporarily disables `draw_contours` on the vision system while the routine runs
- Restores `draw_contours` afterward only if it had been enabled before the run
- Uses blocking robot moves with pose convergence enabled, so each sample waits for both XYZ and wrist orientation to settle before the next marker measurement is taken
- Supports stop requests by setting an internal `threading.Event` and calling `robot_service.stop_motion()`

Main-pipeline TCP-offset logging:

- each accepted rotated sample is logged immediately as:
  - `Captured TCP offset sample: marker=... sample=... reference_rz=... sample_rz=... world=(..., ...) local=(..., ...)`
- when the main robot calibration finishes, the pipeline now emits one consolidated summary block containing:
  - every raw sample used in the final solve
  - per-sample `marker`, `sample_index`, `reference_rz`, `sample_rz`
  - per-sample `world=(dx, dy)` and solved `local=(dx, dy)`
  - grouped mean/std by `sample_rz`
  - final aggregate mean/std that is validated and then saved into `RobotSettings`

---

## `ArucoMarkerHeightMappingService`

Standalone post-calibration workflow for building a depth map from either:

- visible ArUco markers
- a user-defined quadrilateral area subdivided into a regular grid

High-level flow:

Marker mode flow:

1. Reload the homography from `vision_service.camera_to_robot_matrix_path`
2. Capture/detect until all configured `required_ids` are collected (up to 50 attempts)
3. Convert each selected marker point to robot XY with `transformer.transform(px, py)`
4. Move the robot to each marker at the configured calibration `z_target`
5. Call `height_measuring_service.measure_at(x_mm, y_mm)`
6. Store the measured sample as `[measured_x, measured_y, height_mm]`
7. Save all collected samples through `height_measuring_service.save_height_map(...)`, including marker IDs
8. Optionally verify the saved model by inferring 4 interior points and re-measuring them

Area-grid mode flow:

1. Receive 4 normalized image-space corner points plus `rows` / `cols`
2. Normalize corner order to `top-left, top-right, bottom-right, bottom-left`
3. Generate bilinearly interpolated grid points in row-major order
4. Convert each grid point from normalized image coordinates to pixels
5. Transform each pixel point to robot XY with `transformer.transform(px, py)`
6. Move/measure each grid point and save the reached samples
7. Save the depth map with grid metadata:
   - `point_labels`
   - `grid_rows`
   - `grid_cols`

Area-grid precheck flow:

1. Generate the same row-major grid from the 4 selected corners
2. Build target robot poses using the saved laser-calibration measurement pose for `z/rx/ry/rz`
3. Simulate the real execution order without moving the robot by calling:
   - `robot_service.validate_pose(start_state, target_state)`
4. If remote safety walls are enabled, disable them for the full precheck and restore them at the end
5. For each point:
   - try `current_simulated_state -> target`
   - if that fails, try `current_simulated_state -> anchor`
   - then `anchor -> target`
6. Classify each point as:
   - direct
   - via anchor
   - unreachable
7. Stream the classification back to the Calibration UI after each point so the grid updates live:
   - green = reachable
   - red = unreachable
   - orange = pending

Important separation:

- this workflow is standalone and can be triggered from the Calibration application after homography calibration is complete
- the optional `run_height_measurement` step in the main robot-calibration pipeline remains unchanged and still runs inside the state machine when enabled

Exposure handling:

- the standalone workflow now opens one height-measurement session for the full run
- auto-exposure is disabled once before the first marker measurement
- per-marker `measure_at(...)` calls reuse that session without toggling exposure again
- auto-exposure is restored once when the workflow finishes or is stopped

Safety-wall handling for area-grid mode:

- if `robot_service.are_safety_walls_enabled()` returns `True`
- the workflow calls `robot_service.disable_safety_walls()` before the grid run
- `robot_service.enable_safety_walls()` is called in `finally`
- marker mode does not change safety-wall state

Precheck semantics:

- area-grid precheck is simulation only
- it does not move the robot
- it mirrors the execution policy, but real execution still plans from the live robot state when each move is actually sent

Marker collection and ordering:

- unlike the earlier one-shot version, the standalone workflow now keeps detecting markers until all configured `required_ids` are collected or a 50-attempt limit is reached
- once collected, marker reference pixels and transformed robot XY points are cached by marker ID
- measurement then runs in the configured marker order (`required_ids`)

Area-grid ordering:

- generated points are measured in row-major order
- left to right within each row
- top row to bottom row
- labels are persisted as `r1c1`, `r1c2`, ...

Area-grid reachability verification:

- the Calibration UI exposes a dedicated `Verify Grid` action after grid generation
- verification runs in a background worker so the UI stays responsive
- the preview keeps the generated grid visible and recolors unreachable points in red
- this precheck is intended to warn the operator before starting a long measurement run so the area/grid can be adjusted

Saved model and verification:

- the saved depth map now stores both measured points and their marker IDs
- the Calibration depth-map dialog uses those marker IDs to build a piecewise triangle surface instead of generic cubic interpolation when the expected board layout is available
- after a successful standalone measurement run, the Calibration UI can prompt the user to run verification
- marker verification infers 4 interior test points from the piecewise triangle model
- area-grid verification infers 4 interior cell-center points from the saved grid
- both then measure the true heights there and log a consolidated error report with:
  - predicted height
  - measured height
  - signed error
  - mean absolute error
  - max absolute error

Unreachable-point policy:

- marker mode is strict:
  - move failure aborts the run
- area-grid mode is tolerant:
  - failed point → try recovery via the first grid point
  - retry once
  - if still unreachable, skip and continue
  - final report includes reached / unreached totals

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
                    → CAPTURE_TCP_OFFSET
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
| TCP offset capture | `camera_tcp_offset_config`, `camera_tcp_offset_samples` |
| Chessboard | `bottom_left_chessboard_corner_px`, `chessboard_center_px` |
| Result | `image_to_robot_mapping` (the computed homography matrix) |
| Z-axis | `Z_current`, `Z_target`, `ppm_scale` |
| Persistence | `settings_service`, `robot_config`, `robot_config_key` |
| Stop control | `stop_event: threading.Event` |

`context.reset()` returns the context to its initial state without creating a new object — used for retries.

---

## Usage in `GlueRobotSystem`

```python
from src.engine.robot.calibration.service_builders import build_robot_system_calibration_service
from src.robot_systems.glue.calibration.provider import GlueRobotSystemCalibrationProvider

robot_system._calibration_provider = GlueRobotSystemCalibrationProvider(robot_system)
calibration_service = build_robot_system_calibration_service(robot_system)
# → RobotCalibrationService(
#       config=RobotCalibrationConfig(vision, robot, navigation, ...),
#       adaptive_config=AdaptiveMovementConfig(...),
#       events_config=RobotCalibrationEventsConfig(broker, RobotCalibrationTopics.*),
#   )
```

The service builder is now generic. The robot system only provides a concrete
`RobotSystemCalibrationProvider` implementation for the system-specific
calibration move and then reuses the shared builder for the common assembly.

The service is stored as `robot_system._calibration_service` and exposed
through `GlueOperationCoordinator.calibrate()` / `stop_calibration()`.

This is the recommended pattern for future robot systems:

- keep the calibration workflow and settings assembly in the shared engine
  builder
- implement a robot-system provider only for the part that varies per system:
  the calibration-navigation adapter
- keep robot-system-specific side effects, such as glue's camera-area switch,
  explicit in the provider instead of hiding them inside shared navigation

---

## Related

- Application-level calibration UI: [`docs/applications/calibration/README.md`](../../../applications/calibration/README.md)
- `ExecutableStateMachine`: `src/engine/process/executable_state_machine.py`
