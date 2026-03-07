# Fix Plan: Stop Calibration Button Has No Effect

## Root Cause

The stop signal chain from button click to the state machine is **fully intact**.
The failure happens inside the state machine: `ExecutableStateMachine.stop_execution()`
sets `self._running = False` and `context.stop_event.set()`, but the main loop only
checks `while self._running:` **between** state executions — never during them.

Several handlers contain blocking loops that ignore `stop_event`, keeping the current
state alive indefinitely and preventing the outer loop from ever checking `_running`.

---

## Files to Change

All three files are in:
`src/engine/robot/calibration/robot_calibration/states/`

---

### 1. `looking_for_chessboard_handler.py`

**Line 29 — frame-wait loop**

```python
# BEFORE
while chessboard_frame is None:
    chessboard_frame = context.vision_service.get_latest_frame()

# AFTER
while chessboard_frame is None:
    if context.stop_event.is_set():
        return RobotCalibrationStates.ERROR
    chessboard_frame = context.vision_service.get_latest_frame()
```

---

### 2. `looking_for_aruco_markers_handler.py`

**Line 39 — frame-wait loop**

```python
# BEFORE
while all_aruco_detection_frame is None:
    _logger.debug("Waiting for frame for ArUco detection...")
    all_aruco_detection_frame = context.vision_service.get_latest_frame()

# AFTER
while all_aruco_detection_frame is None:
    if context.stop_event.is_set():
        return RobotCalibrationStates.ERROR
    _logger.debug("Waiting for frame for ArUco detection...")
    all_aruco_detection_frame = context.vision_service.get_latest_frame()
```

---

### 3. `remaining_handlers.py` — 4 locations

**3a. `handle_align_robot_state` — entry guard (new line before line 30)**

```python
# ADD at top of handle_align_robot_state, before any work
if context.stop_event.is_set():
    return RobotCalibrationStates.ERROR
```

**3b. `handle_align_robot_state` — `time.sleep(1)` at line 100**

```python
# BEFORE
if result:
    time.sleep(1)
    return RobotCalibrationStates.ITERATE_ALIGNMENT

# AFTER
if result:
    if context.stop_event.wait(timeout=1.0):
        return RobotCalibrationStates.ERROR
    return RobotCalibrationStates.ITERATE_ALIGNMENT
```

**3c. `handle_iterate_alignment_state` — frame-wait loop at line 133**

```python
# BEFORE
while iteration_image is None:
    iteration_image = context.vision_service.get_latest_frame()

# AFTER
while iteration_image is None:
    if context.stop_event.is_set():
        return RobotCalibrationStates.ERROR
    iteration_image = context.vision_service.get_latest_frame()
```

**3d. `handle_iterate_alignment_state` — stability wait at line 215**

```python
# BEFORE
stability_start = time.time()
time.sleep(context.fast_iteration_wait)

# AFTER
stability_start = time.time()
if context.stop_event.wait(timeout=context.fast_iteration_wait):
    return RobotCalibrationStates.ERROR
```

---

## Why `ERROR` is the Right Return Value

- `ERROR` is a valid transition from **every** state in `RobotCalibrationTransitionRules`
- `stop_execution()` already set `self._running = False` before any handler returns
- After a handler returns `ERROR`, the outer `while self._running:` check fires immediately
  and exits — the `ERROR` handler itself is **never executed**
- The stop signal chain already calls `robot_service.stop_motion()` in
  `RobotCalibrationService.stop_calibration()`, so robot movement is already halted

---

## Affected Blocking Operations Not Fixed Here

`move_to_position(blocking=True)` calls in `handle_align_robot_state` (lines 63, 72)
are robot driver calls that cannot be interrupted mid-execution. The entry guard in 3a
catches the case where stop is requested *before* movement starts. If stop arrives
*during* a blocking move, it will be detected on the next handler invocation.