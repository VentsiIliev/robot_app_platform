# Test Gap Plan: Calibration Stop Flow

## Current Coverage Summary

| File | What is tested | What is missing |
|------|---------------|-----------------|
| `tests/applications/calibration/test_calibration_controller.py` | load/stop/handler routing, camera frame, log prefix | `stop_calibration_requested` wiring, `_on_stop_calibration` handler, stop-btn bridge signal |
| `tests/applications/calibration/test_calibration_model.py` | delegation for capture / calibrate_* | `stop_calibration` delegation |
| `tests/applications/calibration/test_calibration_service.py` | stub + app service for capture / calibrate_* | `stop_calibration` on stub and app service |
| `tests/robot_systems/glue/test_calibration_plugin_integration.py` | spec declaration, factory construction | nothing about the stop path |
| `tests/robot_systems/glue/test_glue_processes.py` | `GlueOperationCoordinator` start/stop/pause/clean for glue operations | `start_calibration` and `stop_calibration` on the coordinator |
| `tests/engine/process/` | `ProcessSequence` chain | **`ExecutableStateMachine` has zero tests** |
| *(no file)* | — | State handlers (`looking_for_chessboard`, `looking_for_aruco`, `remaining_handlers`) |
| *(no file)* | — | `RobotCalibrationContext` |
| *(no file)* | — | `RobotCalibrationService.stop_calibration()` |

---

## New Tests to Write

Each section maps to a new test class (or new test file where none exists).

---

### GAP 1 — `test_calibration_controller.py` (add to existing file)

**Class: `TestCalibrationControllerStopCalibration`**

1. `test_stop_calibration_requested_signal_is_wired` — after `load()`, check that `view.stop_calibration_requested.connect` was called
2. `test_on_stop_calibration_calls_model` — call `ctrl._on_stop_calibration()` directly; assert `model.stop_calibration()` was called once
3. `test_on_stop_calibration_disables_stop_button` — call `ctrl._on_stop_calibration()`; assert bridge emits `stop_btn_enabled(False)`

---

### GAP 2 — `test_calibration_model.py` (add to existing file)

**Class: `TestCalibrationModelStopDelegation`**

4. `test_stop_calibration_delegates_to_service` — call `model.stop_calibration()`; assert `svc.stop_calibration()` was called once

---

### GAP 3 — `test_calibration_service.py` (add to existing file)

**Class: `TestStubCalibrationServiceStop`**

5. `test_stop_calibration_does_not_raise` — call `stub.stop_calibration()`; must not raise

**Class: `TestCalibrationApplicationServiceStop`**

6. `test_stop_calibration_delegates_to_process_controller` — construct `CalibrationApplicationService` with a mock process controller; call `svc.stop_calibration()`; assert `process_controller.stop_calibration()` was called

---

### GAP 4 — `test_glue_processes.py` (add to existing file)

**Class: `TestGlueOperationCoordinatorCalibration`**

7. `test_start_calibration_calls_process_start` — call `runner.start_calibration()`; assert the calibration process `start()` was called
8. `test_stop_calibration_calls_process_stop_when_active` — after `start_calibration()`, call `stop_calibration()`; assert `calibration_process.stop()` was called
9. `test_stop_calibration_does_not_raise_when_not_active` — call `stop_calibration()` without starting; must not raise
10. `test_stop_calibration_clears_active_process` — after `start_calibration()` + `stop_calibration()`, the coordinator's `_active_process` must be `None`

---

### GAP 5 — NEW FILE: `tests/engine/process/test_executable_state_machine.py`

**Class: `TestExecutableStateMachineStop`** — the core of the bug

11. `test_stop_sets_running_false` — call `stop_execution()` on a machine; assert `_running` is `False`
12. `test_stop_sets_context_stop_event` — call `stop_execution()`; assert `context.stop_event.is_set()` is `True`
13. `test_stop_without_context_does_not_raise` — machine constructed with `context=None`; call `stop_execution()`; must not raise
14. `test_loop_exits_after_stop_flag` — start a machine whose handler immediately checks `stop_event` and returns `ERROR`; call `start_execution()` in a thread; call `stop_execution()` from main thread; thread must join within 1 s
15. `test_invalid_transition_exits_loop` — handler returns a state not in transition rules; assert `start_execution()` returns without infinite loop

**Class: `TestExecutableStateMachineExecution`**

16. `test_on_enter_called_before_handler` — register a state with `on_enter`; verify call order
17. `test_on_exit_called_after_handler` — register a state with `on_exit`; verify call order
18. `test_state_published_to_broker` — mock broker; verify `publish(state_topic, state_name)` is called on each iteration
19. `test_unhandled_exception_in_handler_exits_loop` — handler raises; assert `start_execution()` returns cleanly

---

### GAP 6 — NEW FILE: `tests/engine/robot/calibration/test_robot_calibration_context.py`

20. `test_reset_creates_new_stop_event` — call `reset()` twice; second `stop_event` must be a different object (not the same instance)
21. `test_stop_event_initially_clear` — after `__init__`, `stop_event.is_set()` is `False`
22. `test_reset_clears_stop_event` — set `stop_event`, call `reset()`; new `stop_event` must be clear
23. `test_flush_camera_buffer_calls_get_frame_n_times` — mock `vision_service`; call `flush_camera_buffer()`; assert `get_latest_frame` called `min_camera_flush` times

---

### GAP 7 — NEW FILE: `tests/engine/robot/calibration/test_calibration_state_handlers.py`

Each handler test uses a minimal fake context with `stop_event = threading.Event()` and
a mock `vision_service` whose `get_latest_frame()` returns `None` until the test releases it.

**`handle_looking_for_chessboard_state`**

24. `test_returns_error_when_stop_event_set_before_frame` — set `stop_event` before call; assert returns `ERROR`
25. `test_returns_error_when_stop_event_set_while_waiting` — `get_latest_frame` returns `None` first call, then sets `stop_event` and returns `None` again; assert returns `ERROR`
26. `test_normal_path_found_returns_chessboard_found` — `get_latest_frame` returns a frame; calibration_vision finds chessboard; assert returns `CHESSBOARD_FOUND`
27. `test_normal_path_not_found_returns_looking` — calibration_vision does not find chessboard; assert returns `LOOKING_FOR_CHESSBOARD`

**`handle_looking_for_aruco_markers_state`**

28. `test_returns_error_when_stop_event_set_before_frame` — same pattern as 24
29. `test_returns_error_when_stop_event_set_while_waiting` — same pattern as 25
30. `test_all_found_returns_all_aruco_found` — calibration_vision finds all markers; assert `ALL_ARUCO_FOUND`
31. `test_not_found_returns_looking` — markers not found; assert `LOOKING_FOR_ARUCO_MARKERS`

**`handle_iterate_alignment_state`**

32. `test_returns_error_when_stop_event_set_before_frame` — set `stop_event`; assert returns `ERROR`
33. `test_returns_error_when_stop_event_set_in_stability_wait` — alignment succeeds, then `stop_event` set before stability wait ends; assert returns `ERROR`
34. `test_returns_error_on_max_iterations` — set `iteration_count` to `max_iterations`; assert `ERROR`
35. `test_stays_in_iterate_when_marker_not_found` — marker not detected; assert `ITERATE_ALIGNMENT`

**`handle_align_robot_state`**

36. `test_returns_error_when_stop_event_set_at_entry` — set `stop_event` before call; assert `ERROR` without calling `move_to_position`
37. `test_returns_error_when_stop_event_set_in_post_move_wait` — move succeeds, `stop_event` set during 1 s wait; assert `ERROR`
38. `test_move_failure_returns_error` — `move_to_position` returns `False` on first and second attempt; assert `ERROR`
39. `test_move_success_returns_iterate_alignment` — `move_to_position` returns `True`; stop_event clear; assert `ITERATE_ALIGNMENT`

---

## Implementation Order

Run these in order — each builds on the one before:

1. GAP 5 (`ExecutableStateMachine`) — pure unit tests, no dependencies, validates the core stop mechanism
2. GAP 6 (`RobotCalibrationContext`) — tiny, confirms stop_event lifecycle
3. GAP 7 (state handlers) — validates the actual fix from `stop_calibration_fix_plan.md`
4. GAP 4 (`GlueOperationCoordinator` calibration) — validates coordinator wiring
5. GAPs 1–3 (application layer) — validates the full MVC chain end-to-end