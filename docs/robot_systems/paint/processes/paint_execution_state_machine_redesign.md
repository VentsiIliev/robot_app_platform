# Paint Execution State Machine Redesign Plan

## Goal

Replace the monolithic paint execution flow with a glue-style internal state machine while preserving the existing `PaintProcess(BaseProcess)` lifecycle and the editor-facing workpiece executor contract.

`PaintProcess` remains the coarse process lifecycle owner:

- `IDLE`
- `RUNNING`
- `PAUSED`
- `STOPPED`
- `ERROR`

A new internal paint execution machine owns the business phases of one paint cycle.

## Current Problem

Paint execution is split across `PaintProductionService.run_once()`, `PaintProductionService._run_single_cycle()`, and `PaintWorkpiecePathExecutor.execute_paint_process()`. The latter has grown into a mixed owner of:

- runtime configuration refresh
- pickup transfer state
- paint-contact projection
- ordered-chain planning
- pause/resume handling
- vacuum boundaries
- edge cleanup
- dropoff preparation
- final dropoff/release
- post-process return

This makes it hard to find phase logic and risky to modify one phase without touching unrelated behavior.

## Target Structure

```text
src/robot_systems/paint/processes/paint/execution_machine/
  __init__.py
  context.py
  state.py
  machine_factory.py
  handlers/
    __init__.py
    guards.py
    startup_handler.py
    magazine_load_handler.py
    capture_handler.py
    preparation_handler.py
    plan_handler.py
    execution_handler.py
    completion_handler.py
    terminal_handlers.py
```

The first implementation step keeps `execution_handler.py` as a compatibility wrapper around the existing `path_executor.execute_paint_process(...)`. After the outer production phases are stable, that handler can be split into:

- `pickup_handler.py`
- `paint_contact_handler.py`
- `cleanup_handler.py`
- `dropoff_preparation_handler.py`
- `dropoff_handler.py`
- `post_return_handler.py`

## State Model

Initial state: `STARTING`

Terminal states: `COMPLETED`, `STOPPED`, `ERROR`, then `IDLE`.

Core states:

- `STARTING`
- `MAGAZINE_LOAD`
- `CAPTURE_WORKPIECE`
- `PREPARE_WORKPIECE`
- `BUILD_EXECUTION_PLAN`
- `EXECUTE_PAINT`
- `COMPLETED`
- `PAUSED`
- `STOPPED`
- `ERROR`
- `IDLE`

`EXECUTE_PAINT` has been replaced by finer motion states for real executor-shaped
objects:

- `PICKUP`
- `PAINT_CONTACT`
- `EDGE_CLEANUP`
- `PREPARE_DROPOFF`
- `DROPOFF`
- `POST_RETURN`

## Target Fine-State Model

The process should be readable as the real robot timeline. Coarse states that
hide multiple hardware or planning operations should be split until each state
has one clear purpose.

Target top-level sequence:

1. `STARTING`
2. `MAGAZINE_MOVE_TO_MAGAZINE` when magazine load is enabled
3. `MAGAZINE_WAIT_CAMERA_SETTLE`
4. `MAGAZINE_CAPTURE`
5. `MAGAZINE_MATCH_PICKUP_TARGET`
6. `MAGAZINE_PREPARE_PICKUP_RELEASE`
7. `MAGAZINE_EXECUTE_PICKUP_RELEASE`
8. `MAGAZINE_MOVE_TO_CALIBRATION`
9. `CALIBRATION_WAIT_CAMERA_SETTLE`
10. `CALIBRATION_CAPTURE`
11. `CALIBRATION_MATCH_WORKPIECE`
12. `PREPARE_WORKPIECE`
13. `BUILD_EXECUTION_PLAN`
14. `PAINT_PREPARE_PICKUP`
15. `PAINT_EXECUTE_PICKUP`
16. `PAINT_CONTACT`
17. `EDGE_CLEANUP`
18. `DROPOFF_PREPARE`
19. `DROPOFF_EXECUTE`
20. `POST_RETURN`
21. `COMPLETED`

Current mapping:

- The top-level paint execution machine now has explicit magazine states:
  `MOVE_TO_MAGAZINE`, `WAIT_CAMERA_SETTLE`, `CAPTURE_MAGAZINE`,
  `PREPARE_PICKUP_RELEASE`, `EXECUTE_PICKUP_RELEASE`, `MOVE_TO_CALIBRATION`,
  and `CALIBRATION_WAIT_CAMERA_SETTLE`.
- `MAGAZINE_LOAD` remains only as a compatibility state for mocked or legacy
  magazine services that still expose only `load_to_calibration(...)`.
- `CAPTURE_WORKPIECE` currently wraps calibration capture, dashboard freeze,
  and brightness handling.
- `PREPARE_WORKPIECE` currently wraps contour matching and workpiece preparation.
- `PICKUP` currently wraps paint-pickup plan preparation, optional ordered
  chain planning, vacuum-on, and pickup/staging execution.

Migration preference:

- Do not duplicate magazine-load logic. Either flatten the existing
  `magazine_load` handlers into the paint execution machine or expose
  substate events/snapshots from the nested magazine-load machine.
- If operator/debug readability is the goal, flattening into one top-level
  `PaintExecutionState` enum is clearer than a hidden nested machine.
- Keep move execution behavior unchanged while splitting states. Each new state
  should first call the same underlying service/executor method as before.

## Transition Rules

```text
STARTING -> MAGAZINE_LOAD | CAPTURE_WORKPIECE | STOPPED | ERROR
MAGAZINE_LOAD -> CAPTURE_WORKPIECE | COMPLETED | PAUSED | STOPPED | ERROR
CAPTURE_WORKPIECE -> PREPARE_WORKPIECE | COMPLETED | PAUSED | STOPPED | ERROR
PREPARE_WORKPIECE -> BUILD_EXECUTION_PLAN | STOPPED | ERROR
BUILD_EXECUTION_PLAN -> EXECUTE_PAINT | STOPPED | ERROR
EXECUTE_PAINT -> COMPLETED | PAUSED | STOPPED | ERROR
COMPLETED -> IDLE
STOPPED -> IDLE
ERROR -> IDLE
PAUSED -> STARTING | STOPPED | ERROR
IDLE -> IDLE
```

The `PAUSED -> STARTING` transition mirrors the existing paint magazine-load machine pattern. The context stores the state to resume from.

## Context Ownership

`PaintExecutionContext` owns per-cycle state:

- injected services
- current process config and magazine config
- stop callback
- cooperative `PaintExecutionControl`
- cycle index
- captured snapshot
- selected contour
- prepared raw workpiece
- workpiece description
- execution plan
- result status/message
- paused/resume state
- timing start values
- optional state timing recorder

Shared robot movement details stay inside the existing lower-level phase executors until those are split safely.

## Migration Steps

1. Add `execution_machine` scaffold:
   - state enum
   - context dataclass
   - machine factory
   - no production behavior change
   - status: done

2. Add handlers equivalent to `PaintProductionService._run_single_cycle()`:
   - magazine load
   - capture
   - workpiece preparation
   - execution-plan build
   - compatibility paint execution
   - completion/terminal handlers
   - status: done

3. Route `PaintProductionService._run_single_cycle()` through the state machine.
   - status: done

4. Keep loop policy in `PaintProductionService` initially:
   - manual loop
   - magazine loop
   - run-while-found behavior
   - status: done

5. Split `EXECUTE_PAINT` into internal paint-motion states after step 3 is stable.
   - status: done
   - note: `EXECUTE_PAINT` remains as a compatibility route for mocked or legacy executors. Real executor-shaped objects route through `PICKUP`, `PAINT_CONTACT`, `EDGE_CLEANUP`, `PREPARE_DROPOFF`, `DROPOFF`, and `POST_RETURN`.

6. Move pause/resume state out of `PaintWorkpiecePathExecutor` into execution-machine context/controllers where possible.
   - status: next

7. Reduce `workpiece_path_executor.py` to:
   - editor preview API
   - execution plan preparation
   - low-level path projection helpers
   - compatibility facade during migration

8. Add structured end-of-cycle state timing.
   - status: done
   - switch: `PaintProcessConfig.enable_execution_state_timing`
   - settings key: `enable_execution_state_timing` in `storage/settings/paint/process.json`
   - output: `[STATE_TIMING_SUMMARY]` log lines emitted once after a cycle finishes, stops, or errors

Example state timing output:

```text
[STATE_TIMING_SUMMARY] name=paint_execution_cycle_1 success=True total_s=74.215 states=10
[STATE_TIMING_SUMMARY] order=1 state=STARTING next=CAPTURE_WORKPIECE success=True exception=False elapsed_s=0.000 start_s=0.000 end_s=0.000 message=-
[STATE_TIMING_SUMMARY] order=2 state=CAPTURE_WORKPIECE next=PREPARE_WORKPIECE success=True exception=False elapsed_s=1.432 start_s=0.000 end_s=1.432 message=-
```

Set `enable_execution_state_timing` to `false` from Paint Process Settings or
`storage/settings/paint/process.json` when the end-of-cycle state table is not
needed.

## Verification After Each Step

Minimum checks:

```bash
python3 -m py_compile src/robot_systems/paint/processes/paint/paint_production_service.py
python3 -m py_compile src/robot_systems/paint/processes/paint/execute/workpiece_path_executor.py
python -m unittest tests/robot_systems/paint/test_paint_workpiece_path_executor.py -v
python -m unittest tests/robot_systems/paint/test_paint_process_integration.py -v
```

When state-machine routing is enabled, also add focused tests for:

- successful single cycle
- no contour detected
- magazine empty
- stop before/after each blocking phase
- pause/resume through `PaintExecutionControl`

## Design Constraints

- Keep `BaseProcess` hooks non-blocking.
- Do not change robot motion semantics while extracting phases.
- Do not move every waypoint into the state machine; states represent business phases.
- Preserve existing `PaintExecutionControl` cooperative pause/stop behavior until replacement is proven.
- Keep hardware calls inside phase handlers/executors, not in views/controllers.
- Preserve the current workpiece editor `IWorkpiecePathExecutor` contract.

## Current Implementation Status

`PaintProductionService._run_single_cycle()` now delegates to `PaintExecutionMachineFactory`.
The production loop policy still lives in `PaintProductionService`, so run-while-found,
manual loop, and magazine loop behavior remain unchanged.

`EXECUTE_PAINT` remains as a compatibility state that calls the existing
`path_executor.execute_paint_process(...)` when the path executor does not expose the
real paint phase surface. Real executor-shaped objects now run through the explicit
motion states:

- `PICKUP`
- `PAINT_CONTACT`
- `EDGE_CLEANUP`
- `PREPARE_DROPOFF`
- `DROPOFF`
- `POST_RETURN`

The Workpiece Editor `paint_process` action also uses the explicit motion states
for an already prepared execution plan. It builds a `PaintExecutionContext` around
the executor and starts `PaintExecutionMachineFactory` at `PICKUP`, so the old
`PaintWorkpiecePathExecutor.execute_paint_process(...)` method is now only a
compatibility wrapper for callers that still invoke that public method directly.

The next redesign step is to move pause/resume ownership and remaining process-level
state out of `PaintWorkpiecePathExecutor` and into explicit context/controller objects.

## Phase Ownership Progress

The move sequence builders are being moved beside the phase code that owns the
robot behavior. This is the practical lookup map for motion tuning:

- Magazine pickup/release transfer segments:
  `src/robot_systems/paint/processes/paint/execute/pickup_executor.py`
  `build_magazine_pickup_release_segments(...)`
- Paint pickup/staging ordered-chain segments:
  `src/robot_systems/paint/processes/paint/execute/pickup_executor.py`
  `build_paint_pickup_segments(...)`
- Paint-contact ordered path segments:
  `src/robot_systems/paint/processes/paint/execute/pickup_executor.py`
  `build_ordered_paint_contact_segments(...)`
- Dropoff preparation segments:
  `src/robot_systems/paint/processes/paint/execution_machine/handlers/dropoff_handlers.py`
  `build_ordered_dropoff_preparation_segments(...)`

`PaintWorkpiecePathExecutor` still contains compatibility delegates while the
rest of the executor is being reduced. New edits to phase-specific route labels,
velocity/acceleration propagation, and `blendR` values should be made in the
phase owner above instead of adding more logic to `workpiece_path_executor.py`.

Naming note: the existing `PaintPickupTransferPlanner` calculates the
calibration-table workpiece pickup and paint-staging poses. It is not the
magazine pickup/release transfer. That class should be renamed in a separate
cleanup once the remaining imports/tests are migrated.

Dropoff sequential production ownership has moved into
`execution_machine/handlers/dropoff_handlers.py`.

That handler now owns:

- paint-to-dropoff safe-travel execution
- pre-dropoff align decision
- Joint 6 unwind before release
- dropoff release-plan construction
- release waypoint execution
- vacuum-off release boundary
- post-return result handling
- ordered dropoff preparation segment construction
- ordered dropoff route `blendR`
- ordered dropoff distributed Joint 6 unwind

The old dropoff helpers on `PaintWorkpiecePathExecutor` remain temporarily for ordered-chain
construction and existing edge-cleanup callers. They should be removed only after those callers
are migrated to the execution-machine phase handlers or a dedicated dropoff planning object.

## Handler Layout

Each `PaintExecutionState` handler lives in its own `handlers/*_handler.py` file.
Files named `*_common.py`, `motion_handlers.py`, `dropoff_handlers.py`, and
`magazine_load_handler.py` are shared helper/planning modules and should not own
state handlers directly.

- `STARTING` -> `startup_handler.py`
- `MAGAZINE_LOAD` -> `magazine_load_compat_handler.py`
- `MAGAZINE_MOVE_TO_MAGAZINE` -> `magazine_move_to_magazine_handler.py`
- `MAGAZINE_WAIT_CAMERA_SETTLE` -> `magazine_wait_camera_settle_handler.py`
- `MAGAZINE_CAPTURE` -> `magazine_capture_handler.py`
- `MAGAZINE_PREPARE_PICKUP_RELEASE` -> `magazine_prepare_pickup_release_handler.py`
- `MAGAZINE_EXECUTE_PICKUP_RELEASE` -> `magazine_execute_pickup_release_handler.py`
- `MAGAZINE_MOVE_TO_CALIBRATION` -> `magazine_move_to_calibration_handler.py`
- `CALIBRATION_WAIT_CAMERA_SETTLE` -> `calibration_wait_camera_settle_handler.py`
- `CAPTURE_WORKPIECE` -> `capture_handler.py`
- `PREPARE_WORKPIECE` -> `preparation_handler.py`
- `BUILD_EXECUTION_PLAN` -> `plan_handler.py`
- `EXECUTE_PAINT` -> `execution_handler.py`
- `PICKUP` -> `pickup_handler.py`
- `PAINT_CONTACT` -> `paint_contact_handler.py`
- `EDGE_CLEANUP` -> `edge_cleanup_handler.py`
- `PREPARE_DROPOFF` -> `prepare_dropoff_handler.py`
- `DROPOFF` -> `dropoff_handler.py`
- `POST_RETURN` -> `post_return_handler.py`
- `COMPLETED` -> `completed_handler.py`
- `PAUSED` -> `pause_handler.py`
- `STOPPED` -> `stopped_handler.py`
- `ERROR` -> `error_handler.py`
- `IDLE` -> `idle_handler.py`
