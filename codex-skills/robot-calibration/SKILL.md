---
name: robot-calibration
description: Use when working on this repository's robot calibration pipeline under src/engine/robot/calibration/, especially to debug iterative alignment, marker detection instability, PPM scaling, target planning, or calibration runtime. Also use when a user provides robot calibration logs and wants root-cause analysis, tuning suggestions, or code changes in the calibration state machine.
---

# Robot Calibration

This skill is for the robot calibration stack in this repository. Use it when the task involves:

- tracing the calibration flow end to end
- debugging `ALIGN_ROBOT` or `ITERATE_ALIGNMENT`
- tuning convergence speed, retries, target thresholds, or PPM refinement
- diagnosing marker loss, bad board filtering, or unstable ChArUco/ArUco detection
- changing calibration settings, fallback behavior, or target planning
- interpreting long robot calibration logs from production runs

Current behavior to remember before debugging:

- iterative alignment now uses bounded same-marker recovery rather than open-ended retry loops
- strict post-settle verification is still a real gate, but repeated failures should now trigger nearby-marker fallback instead of burning minutes on one target
- ArUco detection is running on corrected frames and uses a tuned `cv2.aruco.DetectorParameters()` preset for small markers

## Start Here

Read these files first:

- `src/engine/robot/calibration/robot_calibration_service.py`
- `src/engine/robot/calibration/robot_calibration/robot_calibration_pipeline.py`
- `src/engine/robot/calibration/robot_calibration/RobotCalibrationContext.py`
- `src/engine/robot/calibration/robot_calibration/states/align_robot.py`
- `src/engine/robot/calibration/robot_calibration/states/iterate_alignment.py`

Then load [references/calibration-map.md](references/calibration-map.md) for the file map, state flow, tuning knobs, and debugging checklist.

## Workflow

1. Confirm the user’s failure mode.
   Typical buckets:
   - too many iterative alignment steps
   - markers remain in FOV but detection becomes intermittent
   - first move lands too far away
   - runtime is too long because retries or replacements burn time
   - model quality is poor because target selection or offsets are wrong

2. Trace the state-machine path actually involved.
   Usually:
   - `INITIALIZING`
   - `AXIS_MAPPING`
   - `LOOKING_FOR_CHESSBOARD` / ChArUco detection
   - `LOOKING_FOR_ARUCO_MARKERS`
   - `COMPUTE_OFFSETS`
   - `ALIGN_ROBOT`
   - `ITERATE_ALIGNMENT`
   - `CAPTURE_TCP_OFFSET` / `SAMPLE_HEIGHT` / `DONE`

3. Distinguish geometry errors from detection errors.
   - Geometry errors: wrong `ppm`, bad axis mapping, wrong marker offsets, wrong initial move scaling.
   - Detection errors: marker stays in frame but `detect_specific_marker()` fails, board filtering rejects IDs, strict re-verification fails, or one marker repeatedly enters bounded recovery / fallback.

4. Check whether the problem is in initial align or iterative align.
   - Initial move policy lives in `states/align_robot.py` and `states/compute_offsets_handler.py`.
   - Fine convergence policy lives in `states/iterate_alignment.py` and `robot_controller.py`.

5. When changing code:
   - prefer narrow fixes inside the state that owns the behavior
   - keep `ALIGN_ROBOT` and `ITERATE_ALIGNMENT` responsibilities separate
   - preserve fallback-target behavior unless the task explicitly changes it
   - add or update focused tests in `tests/engine/robot/calibration/`

## Practical Rules

- If the marker is still in FOV but not detected, do not blame motion scale first. Treat it as detection instability or over-aggressive filtering until proven otherwise.
- If the first correction is consistently too large or too small, inspect `compute_offsets_handler.py`, `ppm_scale`, and `ppm_utils.py`.
- If runtime explodes, inspect:
  - `progress.max_iterations`
  - marker-not-found retry loops
  - strict verification loops
  - bounded same-marker recovery limits
  - fallback/replacement behavior
  - target counts in the calibration plan
- If convergence oscillates near the center, inspect:
  - `robot_controller.py`
  - derivative damping
  - axis deadband
  - overshoot sign-flip damping
  - near-target gain
- If users mention “it should converge in 3 to 5 iterations”, look at:
  - first-step gain
  - near-target damping policy
  - per-marker retry budget
  - whether repeated “same iteration” logs are hidden retry passes rather than real geometric iterations

## Logs

When analyzing logs, classify each repeated line:

- `Marker X offsets...`
  This is a successful detection and a usable correction.
- `PPM refined ...`
  Scale update worked; it only addresses move-size error.
- `Marker X not found in any of N frames...`
  Fresh frames were captured, but detection failed during that retry pass.
- `Strict post-settle verification failed...`
  The marker was nearly aligned but the final gate rejected acceptance.
- `Replacing calibration target ...`
  Runtime is now dominated by retry/fallback behavior rather than normal convergence.

Interpret repeated logs carefully:

- repeated `iteration 12` / `13` lines do not necessarily mean the algorithm is stuck in one geometric correction step; they can be bounded retry passes after the iteration counter was intentionally preserved
- if the marker was already near threshold and then vanishes, focus on verification policy and fallback behavior before changing motion gain
- if many other IDs remain visible while the target alone drops out, treat it as per-marker visibility instability rather than a global camera failure

## Validation

Prefer focused tests:

- `python -m unittest tests.engine.robot.calibration.test_calibration_state_handlers -v`
- `python -m unittest tests.engine.robot.calibration.test_robot_calibration_controller -v`
- `python -m unittest tests.engine.robot.calibration.test_compute_offsets_handler -v`
- `python -m unittest tests.engine.robot.calibration.test_calibration_vision -v`

Use log-guided reasoning when hardware is unavailable, but say clearly when a conclusion is inferred from code and logs rather than from a live run.

## Don’t Do This

- Do not mix generic computer-vision advice with this stack’s actual failure points without checking the state handlers.
- Do not propose changes in unrelated application layers; calibration behavior is concentrated in `src/engine/robot/calibration/robot_calibration/`.
- Do not assume more retries are better. In this codebase, excessive retries often turn intermittent detection into long runtime without improving sample quality.
- Do not treat detector retries as detector-quality fixes. Extra frames can hide intermittency, but the real root cause is usually visibility stability, verification policy, threshold choice, or marker placement near the image edge.
