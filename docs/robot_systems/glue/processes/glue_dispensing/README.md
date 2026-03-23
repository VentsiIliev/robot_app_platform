# Glue Dispensing State Machine

**Package:** `src/robot_systems/glue/processes/glue_dispensing/`

This package implements the internal state machine used by `GlueProcess` to execute one or more glue-dispensing paths. It owns:
- path loading and skipping
- robot motion to the path start
- generator and pump control
- optional dynamic pump-speed adjustment
- pause / resume progress recovery
- final completion, stop, and error cleanup

`GlueProcess._on_start()` creates a `DispensingContext`, builds the machine through `DispensingMachineFactory`, and runs it on a daemon thread.

For development and debugging there is also a manual driver in `manual_debug_runner.py`. It builds the same dispensing machine on top of a fake hardware stack and lets you advance the machine one state at a time.

---

## Package Layout

```text
glue_dispensing/
├── context_ops/
│   ├── cleanup_ops.py
│   ├── motion_ops.py
│   ├── path_ops.py
│   └── pump_thread_ops.py
├── dispensing_config.py
├── dispensing_context.py
├── dispensing_error.py
├── dispensing_path.py
├── dispensing_settings.py
├── dispensing_machine_factory.py
├── dispensing_state.py
├── glue_pump_controller.py
├── i_glue_type_resolver.py
├── manual_debug_runner.py
├── pump_speed_adjuster.py
└── state_handlers/
    ├── startup/
    │   ├── handle_starting.py
    │   ├── handle_loading_path.py
    │   ├── handle_loading_current_path.py
    │   ├── handle_issuing_move_to_first_point.py
    │   └── handle_resuming.py
    ├── motion/
    │   ├── handle_moving_to_first_point.py
    │   ├── handle_sending_path_points.py
    │   └── handle_advancing_path.py
    ├── hardware/
    │   ├── generator_handlers.py
    │   ├── handle_starting_pump_adjustment_thread.py
    │   ├── handle_waiting_for_pump_thread_ready.py
    │   └── pump_handlers.py
    ├── waiting/
    │   ├── handle_routing_path_completion_wait.py
    │   ├── handle_waiting_for_pump_thread.py
    │   └── handle_waiting_for_final_position.py
    └── terminal/
        └── terminal_handlers.py
```

---

## Configuration

`GlueDispensingConfig` controls optional behavior:

| Field | Default | Effect |
|---|---|---|
| `use_segment_settings` | `True` | Segment settings are passed through for pump behavior |
| `use_segment_motion_settings` | `True` | Robot motion uses per-segment `velocity` / `acceleration` when present; otherwise falls back to globals |
| `turn_off_pump_between_paths` | `True` | `TURNING_OFF_PUMP` actually stops the pump between paths |
| `adjust_pump_speed_while_spray` | `True` | Starts the dynamic pump-speed thread |
| `robot_tool` | `0` | Tool index for robot motions |
| `robot_user` | `0` | User frame index for robot motions |
| `global_velocity` | `10.0` | Fallback velocity for robot motion when segment motion settings are disabled or missing |
| `global_acceleration` | `30.0` | Fallback acceleration for robot motion when segment motion settings are disabled or missing |
| `move_to_first_point_poll_s` | `0.02` | Poll interval while waiting for the robot to reach the first point |
| `move_to_first_point_timeout_s` | `30.0` | Timeout for reaching the first point |
| `pump_thread_wait_poll_s` | `0.1` | Poll interval while waiting for the pump adjustment thread to finish |
| `final_position_poll_s` | `0.1` | Poll interval while waiting for the robot to reach the final point |
| `pump_ready_timeout_s` | `5.0` | Timeout for the pump adjustment thread ready event |
| `pump_thread_join_timeout_s` | `2.0` | Join timeout used when stopping or pausing the pump adjustment thread |
| `pump_adjuster_poll_s` | `0.01` | Poll interval inside the dynamic pump-speed adjuster loop |

---

## Context API

All handlers share one `DispensingContext`. Important fields:

| Field | Purpose |
|---|---|
| `stop_event` | hard stop signal |
| `run_allowed` | pause gate |
| `paths` | `List[DispensingPathEntry]` |
| `current_path_index` | active path index |
| `current_point_index` | saved progress inside the active path |
| `current_entry` | typed path entry for the active segment |
| `current_path` | full path or sliced remainder during resume |
| `current_settings` | typed `DispensingSegmentSettings` for the active path |
| `use_segment_motion_settings` | whether robot motion should read per-segment `velocity` / `acceleration` |
| `spray_on` | whether generator / pump should run |
| `is_resuming` | set by `GlueProcess._on_resume()` |
| `paused_from_state` | state that last returned `PAUSED` |
| `motor_started` | whether the pump is currently considered on |
| `generator_started` | whether the generator is currently considered on |
| `pump_thread` | dynamic speed-adjustment thread |
| `pump_ready_event` | readiness event for the pump thread |
| `operation_just_completed` | completion flag used by the outer process |
| `last_error` | latest structured dispensing failure |

Important direct context methods used by the handlers:

| Method | Meaning |
|---|---|
| `pause_from(state)` | set `paused_from_state` |
| `stop_with_progress(path_idx, point_idx)` | save progress before stop/error return |
| `pause_with_progress(state, path_idx, point_idx)` | save progress and record pause origin |
| `get_valid_motor_address_for_current_path()` | returns resolved address or `None` |
| `get_motion_velocity()` | resolves robot velocity from segment settings or global fallback |
| `get_motion_acceleration()` | resolves robot acceleration from segment settings or global fallback |
| `fail(kind, code, state, operation, message, exc=None, recoverable=False)` | records `last_error`, logs, and returns `ERROR` |
| `clear_error()` | clears `last_error` |
| `build_debug_snapshot()` | returns a serializable context summary for manual inspection |

Important helper objects owned by the context:

| Helper | Key responsibilities |
|---|---|
| `context.path_ops` | path loading, resume slicing, path start/end lookup, path progression |
| `context.motion_ops` | reach-start threshold lookup and first-point position checks |
| `context.pump_thread_ops` | thread startup, ready-event creation, interruption handling, progress capture, worker-failure detection |
| `context.cleanup` | best-effort shutdown for robot, pump, and generator |

`DispensingPathEntry` is the internal typed path model:
- `points`
- `settings`
- optional `metadata`

`GlueProcess.set_paths(...)` normalizes legacy raw tuples into `DispensingPathEntry` objects before the machine starts.
Supported input shapes are:
- `(points, settings)`
- `(points, settings, pattern_type)` where `pattern_type` is preserved in `metadata`

`DispensingSegmentSettings` is the internal typed settings model. It exposes named fields for:
- glue type
- motion velocity and acceleration
- `time_between_generator_and_glue`
- reach thresholds
- pump forward parameters
- pump reverse parameters
- dynamic pump-speed coefficients

`time_between_generator_and_glue` is now used at runtime. After `TURNING_ON_GENERATOR` successfully turns the generator on for the active segment, the state handler waits for that configured delay before advancing to `TURNING_ON_PUMP`.

If a raw settings dict is still assigned directly to `context.current_settings`, `DispensingContext.get_segment_settings()` coerces it into `DispensingSegmentSettings` on first use. This keeps older call sites working while the package migrates to the typed model.

### Segment Settings Reference

The table below describes how segment-level settings from a workpiece JSON are handled by the current glue job build and dispensing runtime.

| Setting | Status | Actual behavior |
|---|---|---|
| `glue_type` | `Used` | Runtime. Resolves the motor / pump address for the active segment through `DispensingContext.get_valid_motor_address_for_current_path()`. |
| `velocity` | `Used` | Runtime. Robot motion velocity for `move_ptp` to the first point and `execute_trajectory` for the segment. Only used when `GlueDispensingConfig.use_segment_motion_settings=True`; otherwise global motion settings are used. |
| `acceleration` | `Used` | Runtime. Robot motion acceleration for start move and trajectory execution, with the same per-segment vs global fallback behavior as `velocity`. |
| `spraying_height` | `Used` | Build time. Used in `GlueJobBuilderService` to compute the Z coordinate of the robot-space glue path. It does not change anything inside the dispensing state machine after the job has already been built. |
| `rz_angle` | `Used` | Build time. Used in `GlueJobBuilderService` as the robot end-effector rotation for the generated path points. |
| `reach_start_threshold` | `Used` | Runtime. Tolerance for the glue process’s own “wait until the first point is reached” check in `MOVING_TO_FIRST_POINT`. This is the threshold used by the polling logic in `context.motion_ops`, not a controller-level robot tolerance. |
| `reach_end_threshold` | `Used` | Runtime. Tolerance for end-of-segment completion checks. Used when deciding whether the final point has been reached and when starting the dynamic pump-adjustment thread with the correct end threshold. |
| `motor_speed` | `Used` | Runtime. Target steady pump speed for `pump_on()`. |
| `forward_ramp_steps` | `Used` | Runtime. Number of ramp-up steps used during pump start. |
| `initial_ramp_speed` | `Used` | Runtime. Initial startup speed used during pump turn-on. |
| `initial_ramp_speed_duration` | `Used` | Runtime. Duration of the initial pump startup / ramp phase during pump turn-on. |
| `speed_reverse` | `Used` | Runtime. Reverse speed used during `pump_off()` cleanup. |
| `reverse_duration` | `Used` | Runtime. Reverse phase duration used during `pump_off()`. |
| `reverse_ramp_steps` | `Used` | Runtime. Number of reverse ramp steps used during `pump_off()`. |
| `glue_speed_coefficient` | `Used` | Runtime. Dynamic pump-speed coefficient used by `pump_speed_adjuster.py` to convert robot linear velocity into pump-speed correction. |
| `glue_acceleration_coefficient` | `Used` | Runtime. Dynamic pump-speed coefficient used by `pump_speed_adjuster.py` to incorporate robot acceleration into pump-speed correction. |
| `time_between_generator_and_glue` | `Used` | Runtime. After `TURNING_ON_GENERATOR` successfully turns the generator on, the state handler waits this long before advancing to `TURNING_ON_PUMP`. |
| `spray_width` | `Unused` | Stored in segment settings and exposed in editors, but not consumed by the current job builder or dispensing runtime. |
| `fan_speed` | `Unused` | Stored in settings and editor schemas, but the current generator control path does not read or apply it. |
| `generator_timeout` | `Unused` | Present in settings and UI schemas, but not enforced by the current dispensing runtime. |
| `time_before_motion` | `Unused` | Present in settings and UI schemas, but there is currently no explicit dwell between pump-on and robot trajectory motion that uses this value. |
| `time_before_stop` | `Unused` | Present in settings and UI schemas, but the current stop / shutdown flow does not wait on this value before pump or generator shutdown. |
| `adaptive_spacing_mm` | `Unused` | Present in the workpiece segment schema, but the current job builder and dispensing runtime do not read it. |
| `spline_density_multiplier` | `Unused` | Present in the workpiece segment schema, but the current job builder and dispensing runtime do not read it. |
| `smoothing_lambda` | `Unused` | Present in the workpiece segment schema, but the current job builder and dispensing runtime do not read it. |

Notes:
- `Used` means the setting currently affects either job construction or live dispensing behavior.
- `Unused` means the setting may still appear in JSON, editors, or schemas, but changing it does not currently change glue execution behavior.
- Settings marked as build-time only, such as `spraying_height` and `rz_angle`, affect the generated robot path before `GlueProcess` starts; they are not read again by the dispensing machine once the job is loaded.

`last_error` stores a `DispensingErrorInfo` record with:
- `kind`
- `code`
- `state`
- `operation`
- `message`
- `exception_type`
- `path_index`
- `point_index`
- `recoverable`

`build_debug_snapshot()` includes the values most useful during manual stepping:
- path and point indexes
- pause and stop flags
- pump and generator status
- current entry summary
- first and last point of the current path
- typed settings converted to a dict
- structured `last_error`

---

## Factory-Level Default Guards

`DispensingMachineFactory` wraps the simple one-shot handlers with default stop/pause behavior:
- `STOPPED` if `stop_event` is set
- `PAUSED` if `run_allowed` is cleared

This guard behavior is applied centrally in the factory rather than repeated inside every simple handler.

States currently using factory-level default guards:
- `STARTING`
- `LOADING_PATH`
- `LOADING_CURRENT_PATH`
- `ISSUING_MOVE_TO_FIRST_POINT`
- `TURNING_ON_GENERATOR`
- `TURNING_ON_PUMP`
- `STARTING_PUMP_ADJUSTMENT_THREAD`
- `WAITING_FOR_PUMP_THREAD_READY`
- `ROUTING_PATH_COMPLETION_WAIT`
- `TURNING_OFF_PUMP`
- `ADVANCING_PATH`
- `RESUMING`

Loop states still keep inline stop/pause handling because they need custom interruption behavior:
- `MOVING_TO_FIRST_POINT`
- `SENDING_PATH_POINTS`
- `WAITING_FOR_PUMP_THREAD`
- `WAITING_FOR_FINAL_POSITION`

---

## States

There are 22 states:

```text
IDLE
STARTING
LOADING_PATH
LOADING_CURRENT_PATH
ISSUING_MOVE_TO_FIRST_POINT
MOVING_TO_FIRST_POINT
TURNING_ON_GENERATOR
TURNING_ON_PUMP
STARTING_PUMP_ADJUSTMENT_THREAD
WAITING_FOR_PUMP_THREAD_READY
SENDING_PATH_POINTS
ROUTING_PATH_COMPLETION_WAIT
WAITING_FOR_PUMP_THREAD
WAITING_FOR_FINAL_POSITION
TURNING_OFF_PUMP
ADVANCING_PATH
TURNING_OFF_GENERATOR
RESUMING
PAUSED
STOPPED
COMPLETED
ERROR
```

---

## Manual Driver

`manual_debug_runner.py` provides an interactive CLI for development and test debugging.

Run it with:

```bash
python src/robot_systems/glue/processes/glue_dispensing/manual_debug_runner.y_pixels
```

Useful flags:

```bash
python src/robot_systems/glue/processes/glue_dispensing/manual_debug_runner.y_pixels --spray-on --adjust-pump
```

The driver uses:
- the real `DispensingMachineFactory`
- the real state handlers
- fake robot, motor, and generator services
- `ExecutableStateMachine.step()` for manual advancement

The CLI prints a combined snapshot with:
- machine state
- last transition
- machine-level error
- current context summary
- fake robot position and queued commands
- fake motor and generator command history

Supported commands:
- `show`
- `step [n]`
- `start-point`
- `end-point`
- `pos x y z [rx ry rz]`
- `motion vel acc`
- `pause`
- `resume`
- `stop`
- `clear-stop`
- `reset`
- `quit`

Typical workflow:
1. `step` through `STARTING`, `LOADING_PATH`, and `LOADING_CURRENT_PATH`
2. use `show` to inspect `current_path`, `current_settings`, and indexes
3. use `start-point` or `pos ...` to move the fake robot into the reach threshold
4. `step` again to drive the wait states
5. use `end-point` to complete final-position waits

This is intended for handler debugging, transition debugging, and quick experimentation without running the full application shell.

## Actual Handler Paths

This section describes the real runtime branches returned by the handlers.

### `STARTING`
- `STOPPED` if `stop_event` is set
- `PAUSED` if `run_allowed` is cleared
- `RESUMING` if `is_resuming=True` and the context has valid paths
- `LOADING_PATH` otherwise

### `LOADING_PATH`
- `STOPPED` if `stop_event` is set
- `PAUSED` if `run_allowed` is cleared
- `COMPLETED` if there are no remaining paths
- `LOADING_PATH` if the current path is empty and gets skipped
- `LOADING_CURRENT_PATH` for a non-empty path

### `LOADING_CURRENT_PATH`
- `STOPPED` if `stop_event` is set
- `PAUSED` if `run_allowed` is cleared
- `ISSUING_MOVE_TO_FIRST_POINT` after `context.path_ops.restart_current_path()`

### `ISSUING_MOVE_TO_FIRST_POINT`
- `STOPPED` if `stop_event` is set
- `PAUSED` if `run_allowed` is cleared
- `ERROR` if `move_ptp(...)` raises or returns `False`
- `MOVING_TO_FIRST_POINT` on successful non-blocking PTP issue

### `MOVING_TO_FIRST_POINT`
- `ERROR` if `current_settings` or `current_path` is missing
- `STOPPED` if `stop_event` is set while polling
- `PAUSED` if `run_allowed` is cleared while polling
- `TURNING_ON_GENERATOR` once the robot reaches the first point within `REACH_START_THRESHOLD`
- `ERROR` on timeout after 30 seconds

### `TURNING_ON_GENERATOR`
- `STOPPED` if `stop_event` is set
- `PAUSED` if `run_allowed` is cleared
- `TURNING_ON_PUMP` if spray is off, generator is already on, or generator start succeeds
- `ERROR` if `generator.turn_on()` raises

### `TURNING_ON_PUMP`
- `STOPPED` if `stop_event` is set
- `PAUSED` if `run_allowed` is cleared
- `STARTING_PUMP_ADJUSTMENT_THREAD` if spray is off or the motor is already started
- `ERROR` if the motor address cannot be resolved
- `ERROR` if `pump_controller.pump_on(...)` returns `False`
- `STARTING_PUMP_ADJUSTMENT_THREAD` after successful pump start

### `STARTING_PUMP_ADJUSTMENT_THREAD`
- `STOPPED` if `stop_event` is set
- `PAUSED` if `run_allowed` is cleared
- `SENDING_PATH_POINTS` if dynamic adjustment is disabled, spray is off, or `motor_service` is missing
- `SENDING_PATH_POINTS` if motor address resolution fails; this is treated as a warning and adjustment is skipped
- `ERROR` if thread startup raises
- `WAITING_FOR_PUMP_THREAD_READY` after successful thread startup

### `WAITING_FOR_PUMP_THREAD_READY`
- `STOPPED` if `stop_event` is set
- `PAUSED` if `run_allowed` is cleared
- `SENDING_PATH_POINTS` if `pump_thread is None`
- `ERROR` if `pump_ready_event` is missing
- `ERROR` if readiness times out after 5 seconds
- `SENDING_PATH_POINTS` once the ready event is set

### `SENDING_PATH_POINTS`
- `STOPPED` after saving progress if stop is requested during queueing
- `PAUSED` after saving progress if pause is requested during queueing
- `ERROR` after saving progress if `move_linear(...)` raises
- `ERROR` after saving progress if `move_linear(...)` returns `False`
- `ROUTING_PATH_COMPLETION_WAIT` after all points are queued

### `ROUTING_PATH_COMPLETION_WAIT`
- `STOPPED` if `stop_event` is set
- `PAUSED` if `run_allowed` is cleared
- `WAITING_FOR_PUMP_THREAD` if a pump thread exists
- `WAITING_FOR_FINAL_POSITION` otherwise

### `WAITING_FOR_PUMP_THREAD`
- `STOPPED` after joining the thread, capturing progress, and clearing `pump_thread`
- `PAUSED` after joining the thread, capturing progress, clearing `pump_thread`, and recording pause origin
- `ERROR` if the worker thread completed with an exception result
- `TURNING_OFF_PUMP` after natural thread completion and progress capture
- `ERROR` if the wait loop raises unexpectedly

### `WAITING_FOR_FINAL_POSITION`
- `TURNING_OFF_PUMP` immediately if `current_path` is missing
- `STOPPED` if `stop_event` is set while polling
- `PAUSED` if `run_allowed` is cleared while polling
- `TURNING_OFF_PUMP` once the robot reaches the final point within `REACH_END_THRESHOLD`

### `TURNING_OFF_PUMP`
- `STOPPED` if `stop_event` is set
- `PAUSED` if `run_allowed` is cleared
- `ERROR` if the pump should be stopped between paths and the motor address cannot be resolved
- `ERROR` if `pump_controller.pump_off(...)` returns `False`
- `ADVANCING_PATH` if pump shutdown succeeds
- `ADVANCING_PATH` as a no-op if `turn_off_pump_between_paths=False`, spray is off, or the motor is already off

### `ADVANCING_PATH`
- `STOPPED` if `stop_event` is set
- `PAUSED` if `run_allowed` is cleared
- `COMPLETED` if advancing exhausts all paths
- `STARTING` if another path remains

### `RESUMING`
- `STOPPED` if `stop_event` is set
- `PAUSED` if `run_allowed` is cleared
- `COMPLETED` if no paths remain
- `ISSUING_MOVE_TO_FIRST_POINT` when resuming from `ADVANCING_PATH`, `TURNING_OFF_PUMP`, or `MOVING_TO_FIRST_POINT`
- `STARTING` when resuming from an execution state and saved progress is already past the path end
- `TURNING_ON_GENERATOR` when resuming from an execution state with remaining points
- `ISSUING_MOVE_TO_FIRST_POINT` for the fallback branch

Execution states treated as resumable mid-path work:
- `TURNING_ON_GENERATOR`
- `TURNING_ON_PUMP`
- `STARTING_PUMP_ADJUSTMENT_THREAD`
- `WAITING_FOR_PUMP_THREAD_READY`
- `SENDING_PATH_POINTS`
- `ROUTING_PATH_COMPLETION_WAIT`
- `WAITING_FOR_PUMP_THREAD`
- `WAITING_FOR_FINAL_POSITION`

### `PAUSED`
- `STOPPED` if a stop is requested while waiting
- `STARTING` once `run_allowed` is set again

### `COMPLETED`
- `TURNING_OFF_GENERATOR` after final pump cleanup

### `TURNING_OFF_GENERATOR`
- `ERROR` if generator shutdown raises
- `IDLE` after generator shutdown and `operation_just_completed=True`

### `STOPPED`
- `IDLE` after cleanup:
  - stop robot motion
  - stop pump if running
  - stop generator if running

### `ERROR`
- `IDLE` after cleanup:
  - stop robot motion
  - stop generator if running
  - stop pump if running
- when `last_error` exists, the handler logs the failing operation, state, path index, and point index before cleanup

### `IDLE`
- `IDLE` after calling `state_machine.stop_execution()`

---

## Error Handling Model

Dispensing failures now use one shared reporting path:

- a handler detects a failure
- it calls `context.fail(...)`
- `context.fail(...)` stores `last_error` and returns `ERROR`
- `handle_error()` performs best-effort shutdown and routes to `IDLE`

This makes the machine keep one structured error record for the latest failure.

The structured typing is split in two parts:
- `DispensingErrorKind`: broad category such as `MOTION`, `PUMP`, `GENERATOR`, `THREAD`, `CONFIG`, `STATE`, `TIMEOUT`
- `DispensingErrorCode`: stable specific identifier such as `MOVE_TO_FIRST_POINT_FAILED` or `PUMP_THREAD_READY_TIMEOUT`

Current policy:
- all machine-entering dispensing failures are treated as non-recoverable, so `last_error.recoverable` is currently `False`
- cleanup failures during `STOPPED`, `ERROR`, `_on_pause()`, and `_on_stop()` remain best-effort and are only logged

Failure detail propagation includes:
- direct handler exceptions such as `move_ptp`, generator start/stop, and pump-thread startup
- logical command failures such as `pump_on(...) == False` and `pump_off(...) == False`
- worker-thread exceptions raised inside `pump_speed_adjuster.py`

Current machine-level codes used in this package:
- `MISSING_CURRENT_PATH`
- `MOVE_TO_FIRST_POINT_FAILED`
- `MOVE_TO_FIRST_POINT_TIMEOUT`
- `MOVE_LINEAR_FAILED`
- `INVALID_MOTOR_ADDRESS`
- `PUMP_ON_FAILED`
- `PUMP_OFF_FAILED`
- `GENERATOR_START_FAILED`
- `GENERATOR_STOP_FAILED`
- `PUMP_THREAD_START_FAILED`
- `PUMP_THREAD_READY_MISSING`
- `PUMP_THREAD_READY_TIMEOUT`
- `PUMP_THREAD_WAIT_FAILED`
- `PUMP_THREAD_EXECUTION_FAILED`

---

## Declared Transition Rules

`GlueDispensingTransitions.get_rules()` defines the allowed next states. This table is broader than the actual handler branches in a few places, but it is the authoritative machine-level guard.

| From | Allowed next states |
|---|---|
| `IDLE` | `IDLE`, `STARTING`, `ERROR` |
| `STARTING` | `LOADING_PATH`, `RESUMING`, `PAUSED`, `STOPPED`, `ERROR` |
| `LOADING_PATH` | `LOADING_PATH`, `LOADING_CURRENT_PATH`, `COMPLETED`, `PAUSED`, `STOPPED`, `ERROR` |
| `LOADING_CURRENT_PATH` | `ISSUING_MOVE_TO_FIRST_POINT`, `PAUSED`, `STOPPED`, `ERROR` |
| `ISSUING_MOVE_TO_FIRST_POINT` | `MOVING_TO_FIRST_POINT`, `PAUSED`, `STOPPED`, `ERROR` |
| `MOVING_TO_FIRST_POINT` | `TURNING_ON_GENERATOR`, `PAUSED`, `STOPPED`, `COMPLETED`, `ERROR` |
| `TURNING_ON_GENERATOR` | `TURNING_ON_PUMP`, `PAUSED`, `STOPPED`, `COMPLETED`, `ERROR` |
| `TURNING_ON_PUMP` | `STARTING_PUMP_ADJUSTMENT_THREAD`, `PAUSED`, `STOPPED`, `ERROR` |
| `STARTING_PUMP_ADJUSTMENT_THREAD` | `WAITING_FOR_PUMP_THREAD_READY`, `SENDING_PATH_POINTS`, `PAUSED`, `STOPPED`, `ERROR` |
| `WAITING_FOR_PUMP_THREAD_READY` | `SENDING_PATH_POINTS`, `PAUSED`, `STOPPED`, `ERROR` |
| `SENDING_PATH_POINTS` | `ROUTING_PATH_COMPLETION_WAIT`, `PAUSED`, `STOPPED`, `ERROR` |
| `ROUTING_PATH_COMPLETION_WAIT` | `WAITING_FOR_PUMP_THREAD`, `WAITING_FOR_FINAL_POSITION`, `PAUSED`, `STOPPED`, `ERROR` |
| `WAITING_FOR_PUMP_THREAD` | `TURNING_OFF_PUMP`, `PAUSED`, `STOPPED`, `ERROR` |
| `WAITING_FOR_FINAL_POSITION` | `TURNING_OFF_PUMP`, `COMPLETED`, `PAUSED`, `STOPPED`, `ERROR` |
| `TURNING_OFF_PUMP` | `ADVANCING_PATH`, `PAUSED`, `STOPPED`, `ERROR` |
| `ADVANCING_PATH` | `STARTING`, `COMPLETED`, `PAUSED`, `STOPPED`, `ERROR` |
| `TURNING_OFF_GENERATOR` | `IDLE`, `ERROR` |
| `RESUMING` | `MOVING_TO_FIRST_POINT`, `TURNING_ON_GENERATOR`, `STARTING`, `COMPLETED`, `PAUSED`, `STOPPED`, `ERROR` |
| `PAUSED` | `PAUSED`, `STARTING`, `STOPPED`, `COMPLETED`, `IDLE`, `ERROR` |
| `STOPPED` | `COMPLETED`, `IDLE`, `ERROR` |
| `COMPLETED` | `TURNING_OFF_GENERATOR`, `ERROR` |
| `ERROR` | `ERROR`, `IDLE` |

---

## End-to-End Paths

### Normal path, spray off

```text
STARTING
→ LOADING_PATH
→ LOADING_CURRENT_PATH
→ ISSUING_MOVE_TO_FIRST_POINT
→ MOVING_TO_FIRST_POINT
→ TURNING_ON_GENERATOR      # no-op, because spray is off
→ TURNING_ON_PUMP           # no-op, because spray is off
→ STARTING_PUMP_ADJUSTMENT_THREAD   # no-op
→ SENDING_PATH_POINTS
→ ROUTING_PATH_COMPLETION_WAIT
→ WAITING_FOR_FINAL_POSITION
→ TURNING_OFF_PUMP          # usually no-op
→ ADVANCING_PATH
  ├─→ STARTING              # more paths
  └─→ COMPLETED
       → TURNING_OFF_GENERATOR
       → IDLE
```

### Normal path, spray on, dynamic pump adjustment enabled

```text
STARTING
→ LOADING_PATH
→ LOADING_CURRENT_PATH
→ ISSUING_MOVE_TO_FIRST_POINT
→ MOVING_TO_FIRST_POINT
→ TURNING_ON_GENERATOR
→ TURNING_ON_PUMP
→ STARTING_PUMP_ADJUSTMENT_THREAD
→ WAITING_FOR_PUMP_THREAD_READY
→ SENDING_PATH_POINTS
→ ROUTING_PATH_COMPLETION_WAIT
→ WAITING_FOR_PUMP_THREAD
→ TURNING_OFF_PUMP
→ ADVANCING_PATH
  ├─→ STARTING
  └─→ COMPLETED
       → TURNING_OFF_GENERATOR
       → IDLE
```

### Spray on, adjustment requested but skipped

This happens when:
- `motor_service is None`, or
- motor address resolution returns `None`

Flow:

```text
... TURNING_ON_PUMP
→ STARTING_PUMP_ADJUSTMENT_THREAD
→ SENDING_PATH_POINTS
→ ROUTING_PATH_COMPLETION_WAIT
→ WAITING_FOR_FINAL_POSITION
```

### Empty path skip

```text
STARTING
→ LOADING_PATH
→ LOADING_PATH   # self-loop for each empty path skipped
→ LOADING_CURRENT_PATH
→ ISSUING_MOVE_TO_FIRST_POINT   # first non-empty path
```

If all remaining paths are empty:

```text
STARTING
→ LOADING_PATH
→ LOADING_PATH   # skip
→ ...            # skip again
→ COMPLETED
→ TURNING_OFF_GENERATOR
→ IDLE
```

### Pause / resume paths

Pause can happen in any handler that checks `run_allowed`.

Common pattern:

```text
... running state ...
→ PAUSED
→ STARTING
→ RESUMING
```

Resume branches:
- pre-execution pause:
  - `RESUMING → ISSUING_MOVE_TO_FIRST_POINT`
- mid-execution pause with remaining progress:
  - `RESUMING → TURNING_ON_GENERATOR`
- mid-execution pause after path end was already reached:
  - `RESUMING → STARTING`
- resume when no paths remain:
  - `RESUMING → COMPLETED`

### Stop paths

Possible stop routes:
- immediate guard-based stop:
  - `STARTING/LOADING_PATH/ISSUING_MOVE_TO_FIRST_POINT/TURNING_ON_GENERATOR/TURNING_ON_PUMP/STARTING_PUMP_ADJUSTMENT_THREAD/WAITING_FOR_PUMP_THREAD_READY/ROUTING_PATH_COMPLETION_WAIT/ADVANCING_PATH → STOPPED`
- polling/loop stop:
  - `MOVING_TO_FIRST_POINT/SENDING_PATH_POINTS/WAITING_FOR_PUMP_THREAD/WAITING_FOR_FINAL_POSITION/PAUSED → STOPPED`

All stop routes converge to:

```text
STOPPED
→ IDLE
```

### Error paths

Possible error sources include:
- failed `move_ptp`
- missing `current_path` / `current_settings`
- timeout while reaching first point
- generator start exception
- invalid motor address in pump-on or pump-off path
- `pump_on` failure
- `pump_off` failure during normal path transition
- pump adjustment thread startup failure
- missing pump ready event
- pump ready timeout
- `move_linear` exception or failure
- unexpected wait-thread exception
- worker-thread exception raised inside `pump_speed_adjuster.py`
- generator shutdown exception in `TURNING_OFF_GENERATOR`

All error routes converge to:

```text
ERROR
→ IDLE
```

---

## Notes

- `GlueProcess._on_pause()` and `_on_stop()` now use the same best-effort cleanup path as the terminal handlers when a dispensing context exists. The state handlers still act as a second, race-safe cleanup pass.
- The main polling and timeout values are now config-backed through `GlueDispensingConfig`, so tuning wait behavior no longer requires editing handler modules.
- `WAITING_FOR_PUMP_THREAD` is the canonical source of progress capture during dynamic pump adjustment, because the thread result can carry both progress and a worker exception.
- `COMPLETED` only performs final pump cleanup. The completion flag is set in `TURNING_OFF_GENERATOR`, not earlier.
- `GlueProcess.reset_errors()` clears both the outer `ProcessState.ERROR` and `DispensingContext.last_error` when a dispensing context exists.
