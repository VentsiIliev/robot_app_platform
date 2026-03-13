# Glue Dispensing State Machine

**Package:** `src/robot_systems/glue/processes/glue_dispensing/`  
**Entry point:** `GlueProcess._on_start()` builds a `DispensingContext`, calls `DispensingMachineFactory.build()`, then starts the machine on a daemon thread.

---

## Package Layout

```
glue_dispensing/
├── dispensing_config.py          # GlueDispensingConfig — 3 behaviour flags + robot motion params
├── dispensing_context.py         # DispensingContext — shared mutable state for all handlers
├── dispensing_state.py           # GlueDispensingState enum + GlueDispensingTransitions
├── dispensing_machine_factory.py # Builds ExecutableStateMachine, wires all handlers
├── i_glue_type_resolver.py       # IGlueTypeResolver — maps glue_type str → motor_address int
├── glue_pump_controller.py       # GluePumpController — wraps IMotorService turn_on/turn_off
├── pump_speed_adjuster.py        # Dynamic pump speed thread (adjusts speed mid-path)
└── state_handlers/
    ├── handle_idle.py
    ├── handle_starting.py
    ├── handle_moving_to_first_point.py
    ├── handle_executing_path.py
    ├── handle_pump_initial_boost.py
    ├── handle_starting_pump_adjustment_thread.py
    ├── handle_sending_path_points.py
    ├── handle_wait_for_path_completion.py
    ├── handle_transition_between_paths.py
    ├── handle_paused.py
    ├── handle_stopped.py
    ├── handle_completed.py
    └── handle_error.py
```

---

## Configuration (`GlueDispensingConfig`)

| Field | Default | Effect |
|---|---|---|
| `use_segment_settings` | `True` | Pump uses per-path segment settings dict instead of fallback `GlueSettings` |
| `turn_off_pump_between_paths` | `True` | Pump is stopped in `TRANSITION_BETWEEN_PATHS` before starting the next path |
| `adjust_pump_speed_while_spray` | `True` | Starts the dynamic speed-adjustment thread in `STARTING_PUMP_ADJUSTMENT_THREAD` |
| `robot_tool` | `0` | Tool frame index passed to every robot motion call |
| `robot_user` | `0` | User frame index passed to every robot motion call |
| `global_velocity` | `10.0` | Default velocity for PTP and linear moves |
| `global_acceleration` | `30.0` | Default acceleration for PTP and linear moves |

---

## Context (`DispensingContext`)

All state handlers share a single `DispensingContext` instance. Key fields:

| Field | Type | Purpose |
|---|---|---|
| `stop_event` | `threading.Event` | Set by `GlueProcess._on_stop()` — signals immediate abort |
| `run_allowed` | `threading.Event` | Cleared by `_on_pause()`, set by `_on_resume()` — gates execution |
| `paths` | `List[Tuple[list, dict]]` | `(points_list, settings_dict)` per path, set via `set_paths()` |
| `spray_on` | `bool` | Whether pump and generator should be active |
| `current_path_index` | `int` | Index into `paths` currently being processed |
| `current_point_index` | `int` | Last saved progress point within the current path |
| `current_path` | `list` | Active slice of the current path's point list |
| `current_settings` | `dict` | Settings dict for the current path segment |
| `is_resuming` | `bool` | Set by `_on_resume()`; read by `handle_starting` to route resume logic |
| `paused_from_state` | `GlueDispensingState` | The state that returned `PAUSED` — used to restore correct resume position |
| `motor_started` | `bool` | Tracks whether pump motor is currently running |
| `generator_started` | `bool` | Tracks whether generator is currently running |
| `pump_thread` | `PumpThreadWithResult` | Speed-adjustment thread (None if disabled or spray_off) |
| `pump_ready_event` | `threading.Event` | Signalled by pump thread once initialised |
| `state_machine` | `ExecutableStateMachine` | Back-reference so `handle_idle` can call `stop_execution()` |

---

## States

### `STARTING`
**Handler:** `handle_starting.py`  
**Role:** Entry point for every path iteration and resume routing.

**Normal flow:**
1. Guard: if `stop_event` set → `STOPPED`; if `run_allowed` clear → `PAUSED`
2. If `is_resuming=True` → delegate to `_handle_resume()` (see Resume section)
3. If `current_path_index >= len(paths)` → `COMPLETED`
4. Load `path, settings = paths[current_path_index]`
5. If path is empty → increment `current_path_index`, return `STARTING` (skip loop)
6. Set `context.current_path`, `context.current_settings`, `context.current_point_index = 0`
7. Issue a non-blocking `robot_service.move_ptp()` to `path[0]`
8. → `MOVING_TO_FIRST_POINT`

**Resume routing** (`_handle_resume`):
- `paused_from == TRANSITION_BETWEEN_PATHS` or `MOVING_TO_FIRST_POINT` → re-issue `move_ptp` to first point → `MOVING_TO_FIRST_POINT`
- `paused_from` in execution states (`EXECUTING_PATH`, `PUMP_INITIAL_BOOST`, `STARTING_PUMP_ADJUSTMENT_THREAD`, `SENDING_PATH_POINTS`, `WAIT_FOR_PATH_COMPLETION`):
  - If `current_point_index >= len(path)` → advance to next path, return `STARTING`
  - Otherwise slice path from saved index: `current_path = path[current_point_index:]` → `EXECUTING_PATH`
- Fallback → re-issue `move_ptp` → `MOVING_TO_FIRST_POINT`

---

### `MOVING_TO_FIRST_POINT`
**Handler:** `handle_moving_to_first_point.py`  
**Role:** Waits for the robot to physically arrive at the first point of the current path.

**Flow:**
1. Validate `current_settings` and `current_path` exist (→ `ERROR` if not)
2. Read `REACH_START_THRESHOLD` from segment settings (default `1.0` mm)
3. Poll `robot_service.get_current_position()` every 20 ms
4. On each tick: check `stop_event` (→ `STOPPED`) and `run_allowed` (→ `PAUSED`, sets `paused_from_state`)
5. When Euclidean distance to `path[0]` < threshold → set `current_point_index = 0` → `EXECUTING_PATH`
6. After 30 s without arrival → `ERROR`

---

### `EXECUTING_PATH`
**Handler:** `handle_executing_path.py`  
**Role:** Thin routing state. Turns on the generator once per dispensing run, then proceeds to pump startup.

**Flow:**
1. Guard: `stop_event` → `STOPPED`; `!run_allowed` → `PAUSED`
2. If `spray_on=True` and `generator_started=False` and `generator is not None` → call `generator.turn_on()`, set `generator_started = True`
3. → `PUMP_INITIAL_BOOST`

> The generator is turned on here (not in `STARTING`) so that it only activates once the robot has arrived at the correct position.

---

### `PUMP_INITIAL_BOOST`
**Handler:** `handle_pump_initial_boost.py`  
**Role:** Starts the glue pump motor with ramp-up parameters.

**Flow:**
1. Guard: `stop_event` → `STOPPED`; `!run_allowed` → `PAUSED`
2. If `spray_on=False` or `motor_started=True` → skip, → `STARTING_PUMP_ADJUSTMENT_THREAD`
3. Resolve `motor_address` via `context.get_motor_address_for_current_path()` (uses `IGlueTypeResolver`)  
   If `-1` → `ERROR`
4. Call `pump_controller.pump_on(motor_address, current_settings)`  
   Reads `MOTOR_SPEED`, `FORWARD_RAMP_STEPS`, `INITIAL_RAMP_SPEED`, `INITIAL_RAMP_SPEED_DURATION` from segment settings  
   If fails → `ERROR`
5. Set `motor_started = True` → `STARTING_PUMP_ADJUSTMENT_THREAD`

---

### `STARTING_PUMP_ADJUSTMENT_THREAD`
**Handler:** `handle_starting_pump_adjustment_thread.py`  
**Role:** Launches the background thread that dynamically adjusts pump speed to match robot velocity throughout the path.

**Flow:**
1. Guard: `stop_event` → `STOPPED`; `!run_allowed` → `PAUSED`
2. Reset `pump_thread = None`, create new `pump_ready_event`
3. If `adjust_pump_speed_while_spray=True` AND `spray_on=True` AND `motor_service is not None`:
   - Resolve `motor_address` (warning + skip if `-1`)
   - Read `REACH_END_THRESHOLD` from settings
   - Start `PumpThreadWithResult` daemon (from `pump_speed_adjuster.py`)
   - Wait up to 5 s on `pump_ready_event` → `ERROR` if timeout
4. If conditions not met → `pump_thread` stays `None` (silent fallback to position-poll in WAIT)
5. → `SENDING_PATH_POINTS`

---

### `SENDING_PATH_POINTS`
**Handler:** `handle_sending_path_points.py`  
**Role:** Streams all move commands for the current path to the robot controller.

**Flow:**
1. Iterate over `current_path` from `current_point_index`
2. Before each point: check `stop_event` (→ `STOPPED` + `save_progress`) and `run_allowed` (→ `PAUSED` + `save_progress` + `paused_from_state`)
3. Call `robot_service.move_linear(point, tool, user, velocity, acceleration, blendR=1.0, wait_to_reach=False)` — **non-blocking**
4. If `move_linear` returns `False` → `ERROR` + `save_progress`
5. After all points sent → `WAIT_FOR_PATH_COMPLETION`

> All moves are non-blocking (`blendR=1.0`). The robot queues them and executes them in a smooth continuous sweep. Actual completion is tracked in `WAIT_FOR_PATH_COMPLETION`.

---

### `WAIT_FOR_PATH_COMPLETION`
**Handler:** `handle_wait_for_path_completion.py`  
**Role:** Blocks until the robot has physically finished executing the current path.

**Two modes depending on whether a pump thread exists:**

**Mode A — pump thread active** (`pump_thread is not None`):
1. Poll `pump_thread.is_alive()` every 100 ms
2. On `stop_event` → join thread (2 s timeout), capture progress from `pump_thread.result`, → `STOPPED`
3. On `!run_allowed` → join thread, capture progress, set `paused_from_state`, → `PAUSED`
4. Thread exits naturally → capture `pump_thread.result = (success, final_point_index)`, update `current_point_index` → `TRANSITION_BETWEEN_PATHS`

**Mode B — no pump thread** (`spray_on=False` or adjustment disabled):
1. Poll `robot_service.get_current_position()` every 100 ms against `REACH_END_THRESHOLD` of `current_path[-1]`
2. Responds to `stop_event` → `STOPPED` and `!run_allowed` → `PAUSED`
3. Robot within threshold → `TRANSITION_BETWEEN_PATHS`

> `pump_thread.result` is a `(success: bool, progress_index: int)` tuple written by `PumpThreadWithResult` before it exits. This is the canonical source of progress for resume after `WAIT_FOR_PATH_COMPLETION` pause.

---

### `TRANSITION_BETWEEN_PATHS`
**Handler:** `handle_transition_between_paths.py`  
**Role:** Cleans up after one path completes and prepares index state for the next.

**Flow:**
1. Guard: `stop_event` → `STOPPED`; `!run_allowed` → `PAUSED`
2. If `turn_off_pump_between_paths=True` AND `motor_started=True` AND `spray_on=True`:
   - Resolve `motor_address` (→ `ERROR` if `-1`)
   - Call `pump_controller.pump_off(motor_address, current_settings)` — reads `SPEED_REVERSE`, `REVERSE_DURATION`, `REVERSE_RAMP_STEPS`
   - Set `motor_started = False`
3. Increment `current_path_index`, reset `current_point_index = 0`
4. If `current_path_index >= len(paths)` → `COMPLETED`
5. Otherwise → `STARTING` (begin next path)

> Note: when `turn_off_pump_between_paths=False`, the pump stays running across the inter-path PTP move in `STARTING`. The generator is **not** turned off between paths — only at `COMPLETED`/`STOPPED`/`ERROR`.

---

### `PAUSED`
**Handler:** `handle_paused.py`  
**Role:** Blocking wait state. Holds the machine thread while the operator has paused the process.

**Flow:**
1. Loop: call `run_allowed.wait(timeout=0.05)`
2. On each timeout tick: check `stop_event` → `STOPPED`
3. When `run_allowed.wait()` returns `True` (event set by `_on_resume()`) → `STARTING`

**What `GlueProcess._on_pause()` does before this state is entered:**
- Calls `robot_service.stop_motion()` immediately (always, regardless of context)
- Clears `run_allowed`
- Calls `pump_controller.pump_off()` if motor was running
- Calls `generator.turn_off()` if generator was running

**What `GlueProcess._on_resume()` does to exit this state:**
- Sets `context.is_resuming = True`
- Sets `run_allowed` — this wakes the `handle_paused` loop

---

### `STOPPED`
**Handler:** `handle_stopped.py`  
**Role:** Cleanup after an operator stop. Ensures all hardware is safely off.

**Flow:**
1. Call `robot_service.stop_motion()`
2. If `motor_started` → `pump_controller.pump_off()`, set `motor_started = False`
3. If `generator_started` → `generator.turn_off()`, set `generator_started = False`
4. → `IDLE`

> `GlueProcess._on_stop()` also stops hardware immediately (before the machine thread reaches this state), so these calls are a safe second pass that handles any race condition.

---

### `COMPLETED`
**Handler:** `handle_completed.py`  
**Role:** Normal end of all paths. Shuts down hardware gracefully.

**Flow:**
1. If `motor_started` → `pump_controller.pump_off()`, set `motor_started = False`
2. If `generator_started` → `generator.turn_off()`, set `generator_started = False`
3. Set `context.operation_just_completed = True`
4. → `IDLE`

---

### `ERROR`
**Handler:** `handle_error.py`  
**Role:** Catches unrecoverable faults. Stops all hardware and logs an error.

**Flow:**
1. Call `robot_service.stop_motion()`
2. If `generator_started` → `generator.turn_off()`, set `generator_started = False`
3. If `motor_started` → `pump_controller.pump_off()`, set `motor_started = False`
4. → `IDLE`

---

### `IDLE`
**Handler:** `handle_idle.py`  
**Role:** Terminal state. Signals the machine loop to exit.

**Flow:**
1. Call `context.state_machine.stop_execution()` — sets `_running = False` on the `ExecutableStateMachine`
2. Return `IDLE` (loop condition already false; return value is never consumed)

---

## State Transition Table

| From state | Allowed next states |
|---|---|
| `IDLE` | `IDLE` *, `STARTING`, `ERROR` |
| `STARTING` | `STARTING`, `MOVING_TO_FIRST_POINT`, `EXECUTING_PATH`, `COMPLETED`, `PAUSED`, `STOPPED`, `ERROR` |
| `MOVING_TO_FIRST_POINT` | `EXECUTING_PATH`, `PAUSED`, `STOPPED`, `COMPLETED`, `ERROR` |
| `EXECUTING_PATH` | `PUMP_INITIAL_BOOST`, `PAUSED`, `STOPPED`, `COMPLETED`, `ERROR` |
| `PUMP_INITIAL_BOOST` | `STARTING_PUMP_ADJUSTMENT_THREAD`, `PAUSED`, `STOPPED`, `ERROR` |
| `STARTING_PUMP_ADJUSTMENT_THREAD` | `SENDING_PATH_POINTS`, `PAUSED`, `STOPPED`, `ERROR` |
| `SENDING_PATH_POINTS` | `WAIT_FOR_PATH_COMPLETION`, `PAUSED`, `STOPPED`, `ERROR` |
| `WAIT_FOR_PATH_COMPLETION` | `TRANSITION_BETWEEN_PATHS`, `COMPLETED`, `PAUSED`, `STOPPED`, `ERROR` |
| `TRANSITION_BETWEEN_PATHS` | `STARTING`, `COMPLETED`, `PAUSED`, `STOPPED`, `ERROR` |
| `PAUSED` | `PAUSED` *, `STARTING`, `STOPPED`, `COMPLETED`, `IDLE`, `ERROR` |
| `STOPPED` | `COMPLETED`, `IDLE`, `ERROR` |
| `COMPLETED` | `IDLE`, `ERROR` |
| `ERROR` | `ERROR` *, `IDLE` |

\* Self-loop used by the `ExecutableStateMachine` transition guard (handler returns own state during `stop_execution()` or blocking wait).

---

## Execution Flows

### Normal (all paths, spray on)

```
STARTING
  │  load path[0], move_ptp to first point
  ▼
MOVING_TO_FIRST_POINT
  │  poll position until within REACH_START_THRESHOLD
  ▼
EXECUTING_PATH
  │  turn on generator
  ▼
PUMP_INITIAL_BOOST
  │  turn on pump motor with ramp
  ▼
STARTING_PUMP_ADJUSTMENT_THREAD
  │  start speed-adjustment daemon thread
  ▼
SENDING_PATH_POINTS
  │  stream move_linear() for all points (non-blocking)
  ▼
WAIT_FOR_PATH_COMPLETION
  │  wait for pump thread (or position poll) to signal path done
  ▼
TRANSITION_BETWEEN_PATHS
  │  [turn off pump]  increment path index
  │
  ├── more paths? ──▶ STARTING  (repeat from top for next path)
  │
  └── last path  ──▶ COMPLETED
                       │  turn off pump + generator
                       ▼
                     IDLE  ──▶ stop_execution()
```

### Pause → Resume

```
[any active state]
  │  handler checks !run_allowed → sets paused_from_state → returns PAUSED
  │
  │  GlueProcess._on_pause():
  │    stop_motion()  |  pump_off()  |  generator.turn_off()  |  run_allowed.clear()
  ▼
PAUSED
  │  blocks on run_allowed.wait(0.05) loop
  │
  │  GlueProcess._on_resume():
  │    is_resuming = True  |  run_allowed.set()
  ▼
STARTING  (is_resuming = True)
  │  _handle_resume() checks paused_from_state:
  │
  ├── TRANSITION_BETWEEN_PATHS / MOVING_TO_FIRST_POINT
  │     → move_ptp to first point → MOVING_TO_FIRST_POINT
  │
  ├── EXECUTING_PATH / PUMP_INITIAL_BOOST / STARTING_PUMP_ADJ / SENDING_PATH_POINTS / WAIT_FOR_PATH_COMPLETION
  │     → slice path from current_point_index
  │     → EXECUTING_PATH  (pump + generator restart from scratch)
  │
  └── fallback → move_ptp to first point → MOVING_TO_FIRST_POINT
```

### Stop

```
[any active state]
  │  handler checks stop_event → returns STOPPED
  │
  │  GlueProcess._on_stop():
  │    stop_event.set()  |  run_allowed.set()  (unblocks PAUSED)
  │    stop_motion()  |  pump_off()  |  generator.turn_off()
  ▼
STOPPED
  │  second-pass hardware cleanup (idempotent)
  ▼
IDLE  ──▶ stop_execution()
```

### Error

```
[any active state]
  │  handler returns ERROR (e.g. invalid motor_address, move_linear=False, thread timeout)
  ▼
ERROR
  │  stop_motion()  |  generator.turn_off()  |  pump_off()
  ▼
IDLE  ──▶ stop_execution()
```

---

## Key Settings Keys Used

All read from the segment `settings` dict (`GlueSettingKey` enum values):

| Key | Used in state | Purpose |
|---|---|---|
| `reach_start_threshold` | `MOVING_TO_FIRST_POINT` | Max distance (mm) to accept robot as "at start" |
| `reach_end_threshold` | `STARTING_PUMP_ADJ_THREAD`, `WAIT_FOR_PATH_COMPLETION` | Max distance to accept robot as "at end" |
| `motor_speed` | `PUMP_INITIAL_BOOST` | Pump target speed |
| `forward_ramp_steps` | `PUMP_INITIAL_BOOST` | Number of speed steps during ramp-up |
| `initial_ramp_speed` | `PUMP_INITIAL_BOOST` | Starting speed before ramp |
| `initial_ramp_speed_duration` | `PUMP_INITIAL_BOOST` | Duration (s) at initial ramp speed |
| `speed_reverse` | `TRANSITION_BETWEEN_PATHS` | Reverse speed during pump turn-off |
| `reverse_duration` | `TRANSITION_BETWEEN_PATHS` | Duration (s) of reverse on turn-off |
| `reverse_ramp_steps` | `TRANSITION_BETWEEN_PATHS` | Ramp steps during pump turn-off |
| `glue_type` | (via `DispensingContext`) | Resolved to motor_address by `IGlueTypeResolver` |

---

## Threading Model

| Thread | Role |
|---|---|
| **Caller thread** (`BaseProcess` lock) | Calls `_on_start/pause/resume/stop` — must be fast, non-blocking |
| **Machine thread** (`GlueDispensingMachine` daemon) | Runs `ExecutableStateMachine.start_execution()` — all state handlers execute here |
| **Pump thread** (`PumpSpeedAdjuster` daemon) | Reads robot position/velocity, calls `motor_service.set_speed()` continuously during path execution |

`stop_event` and `run_allowed` are `threading.Event` objects — safe for cross-thread signalling without locks.

