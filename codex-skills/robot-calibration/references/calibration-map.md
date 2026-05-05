# Calibration Map

## Main Entry Points

- `src/engine/robot/calibration/robot_calibration_service.py`
  Service wrapper. Handles runtime settings refresh, auto-brightness locking, safety walls, and pipeline startup/shutdown.
- `src/engine/robot/calibration/robot_calibration/robot_calibration_pipeline.py`
  Builds the context and state machine, wires handlers, and runs the calibration flow.
- `src/engine/robot/calibration/robot_calibration/RobotCalibrationContext.py`
  Shared mutable context. Holds config, progress, timing, artifacts, and helper methods like `wait_for_frame()`.

## Most Important States

- `states/align_robot.py`
  Computes the coarse move from calibration pose to target marker pose. Resets `iteration_count` and hands off to iterative alignment.
- `states/iterate_alignment.py`
  Fine alignment loop. Captures fresh frames, detects the current marker, optionally refines `ppm`, computes robot correction, applies movement, waits for stabilization, and accepts, retries, or falls back when bounded recovery is exhausted.
- `states/compute_offsets_handler.py`
  Converts marker pixel locations into mm offsets relative to the image center. This is where target-height scaling can matter.
- `states/looking_for_aruco_markers_handler.py`
  Builds the target set used for calibration and stores averaged reference pixels.
- `states/fallback_targets.py`
  Nearby-marker replacement logic when a marker is unreachable or repeatedly fails.

## Vision Components

- `CalibrationVision.py`
  Marker and board detection. If markers are “in FOV but not found”, inspect this file and its filtering behavior first.
- `src/engine/vision/implementation/VisionSystem/services/aruco_detection_service.py`
  Builds `cv2.aruco.ArucoDetector` with the current small-marker tuning. Use this file for detector-parameter changes rather than guessing from generic OpenCV defaults.
- `ppm_utils.py`
  Online `ppm` refinement, probe storage, and adaptive stability wait.

## Motion Components

- `robot_controller.py`
  Adaptive iterative move sizing, derivative damping, deadband behavior, overshoot damping, and initial align compensation.
- `config_helpers.py`
  Defines `AdaptiveMovementConfig`, including:
  - `target_error_mm`
  - `iterative_gain`
  - `near_target_gain`
  - `axis_deadband_mm`
  - `axis_flip_scale_min`
  - `initial_align_y_scale`
  - `initial_align_approach_z`

## Common Failure Patterns

### 1. Too many iterative steps

Check:

- `context.max_iterations` in `RobotCalibrationContext.py`
- recovery or fallback logic in `iterate_alignment.py`
- `iterative_gain` and `near_target_gain`
- whether many iterations are actually “marker not found” retries

### 2. Marker stays in frame but detection fails

Check:

- `CalibrationVision.detect_specific_marker()`
- `aruco_detection_service.py` detector parameters and corrected-frame inputs
- out-of-board ID filtering and dictionary selection
- whether strict re-verification is too brittle
- whether close-range pose causes unstable decoding
- whether the marker is now hitting bounded retry / fallback limits rather than a raw detector crash

### 3. First move lands too far off

Check:

- `compute_offsets_handler.py`
- `ppm_scale`
- initial align mapping in `align_robot.py`
- `initial_align_y_scale`

### 4. Runtime is too long

Check:

- number of selected targets
- per-marker retry budget
- bounded same-marker recovery limits
- marker-not-found waits
- strict verification behavior
- fallback-target churn

## Log-Reading Checklist

When a user pastes a calibration log:

1. Find the first `ALIGN_ROBOT` target pose for the bad marker.
2. Count how many iterations were actual detections versus “not found”.
   Repeated logs with the same iteration number may be retry passes, not fresh geometric iterations.
3. Note whether `PPM refined` lines trend toward stability.
4. Check whether failure happened because:
   - error stayed large
   - marker vanished intermittently
   - strict verification rejected a nearly-good alignment
   - bounded retry logic escalated to fallback
   - movement failed
5. Look for fallback replacement lines to see whether runtime is dominated by recovery policy.

## Test Files

- `tests/engine/robot/calibration/test_calibration_state_handlers.py`
- `tests/engine/robot/calibration/test_robot_calibration_controller.py`
- `tests/engine/robot/calibration/test_compute_offsets_handler.py`
- `tests/engine/robot/calibration/test_calibration_vision.py`

## Recommended First Commands

```bash
rg -n "ALIGN_ROBOT|ITERATE_ALIGNMENT|detect_specific_marker|ppm" src/engine/robot/calibration/robot_calibration -S
python -m unittest tests.engine.robot.calibration.test_calibration_state_handlers -v
python -m unittest tests.engine.robot.calibration.test_robot_calibration_controller -v
```
