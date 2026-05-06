# Paint System Review And Plan

Date: 2026-05-05
Scope: `src/robot_systems/paint`

## Summary

This review focused on:

- correctness and bug risk
- operator safety and runtime control
- performance costs on the production path
- architectural boundaries and maintainability

The paint system contains useful structure and a readable end-to-end flow, but it currently has a few concrete correctness issues and several architectural pressure points. The highest-risk problems are invalid work-area IDs, ineffective stop/pause behavior during execution, and a pickup/execution path that mixes runtime motion logic with debug and hardware concerns in one large class.

## Key Findings

### 1. Invalid work-area IDs are written during navigation and calibration

Severity: High

Files:

- `src/robot_systems/paint/paint_robot_system.py`
- `src/robot_systems/paint/calibration/provider.py`
- `src/robot_systems/paint/navigation.py`

Details:

- The paint robot system declares only one work area: `paint`.
- Calibration navigation sets the active work area to `spray`.
- Home navigation sets the active work area to `pickup`.

Evidence:

- `paint_robot_system.py`: declared work area is only `paint`
- `calibration/provider.py`: `work_area_service.set_active_area_id("spray")`
- `navigation.py`: `_set_area("pickup")`

Risk:

- If the work-area service validates IDs, these calls are simply wrong.
- If it does not validate, the system can silently drift into an invalid state, which can break downstream vision and targeting behavior.

Recommendation:

- Replace invalid hard-coded area IDs with declared IDs only.
- Centralize work-area IDs into a single source of truth.
- Add validation tests so undeclared area IDs fail fast.

### 2. Stop and pause controls do not provide meaningful control once execution begins

Severity: High

Files:

- `src/robot_systems/paint/processes/paint/paint_process.py`
- `src/robot_systems/paint/processes/paint/paint_production_service.py`
- `src/robot_systems/paint/processes/paint/workpiece_path_executor.py`

Details:

- `PaintProcess._on_stop()` only sets an internal boolean.
- `PaintProcess._on_pause()` and `_on_resume()` are no-ops.
- Cancellation checks exist only between coarse production stages.
- The executor then performs blocking robot motion calls without a cancellation path.

Risk:

- The dashboard exposes stop/pause, but operators may not be able to interrupt an active pickup or trajectory execution in time.
- This is a mismatch between UI semantics and real system behavior.

Recommendation:

- Define exact operator semantics for `stop` and `pause`.
- Add an execution interruption path at robot-service level or at least between motion segments.
- If pause is unsupported, remove or disable it in the UI until implemented.

### 3. Relay vacuum pump commands are sent twice

Severity: Medium

Files:

- `src/robot_systems/paint/domain/vacuum_pump/relay_client.py`

Details:

- `control_relay()` calls `client.set_relay(output_num, state)` and then calls it again in the `return`.

Risk:

- Unnecessary duplicate network traffic.
- Potential repeated side effects if the relay server is not fully idempotent.

Recommendation:

- Call `set_relay()` once and return that result.
- Add a unit test for a single command dispatch.

### 4. Camera-to-TCP pickup compensation is configured but not actually applied

Severity: Medium

Files:

- `src/robot_systems/paint/application_wiring.py`
- `src/robot_systems/paint/processes/paint/workpiece_path_executor.py`

Details:

- The executor is constructed with camera-to-TCP offset settings.
- Runtime refresh also reloads those settings.
- In pickup pose generation, the logic hard-codes `should_apply_tcp_offset = False` and uses zero offsets.

Risk:

- If pickup points are camera-derived while the robot acts with tool-center motion, the robot can systematically miss the intended pickup position.

Recommendation:

- Either apply the configured offset correctly or remove the dead configuration path.
- Add geometry-level tests for pickup pose generation with and without compensation.

### 5. Production execution always writes debug artifacts on the critical path

Severity: Medium

Files:

- `src/robot_systems/paint/application_wiring.py`
- `src/robot_systems/paint/processes/paint/workpiece_path_executor.py`

Details:

- The executor always receives a debug dump directory.
- Pivot execution always writes text dumps and debug plots.

Risk:

- Extra file I/O during production runs.
- Matplotlib rendering on the runtime path.
- Unbounded artifact growth under `src/bootstrap/debug_plots`.

Recommendation:

- Make debug dumping opt-in via persisted settings or explicit debug mode.
- Never render plots by default in production execution.
- Add retention or cleanup rules for generated debug artifacts.

### 6. Process health gating is effectively not used

Severity: Medium

Files:

- `src/robot_systems/paint/paint_robot_system.py`
- `src/robot_systems/paint/processes/paint/paint_process.py`

Details:

- The paint process receives a `service_checker`, but no actual `ProcessRequirements` are configured.
- The process therefore starts without requiring robot, vision, or vacuum readiness.

Risk:

- The process may begin and fail late instead of being blocked before execution.
- Operator experience becomes trial-and-error instead of deterministic readiness.

Recommendation:

- Define explicit start requirements.
- At minimum require robot health.
- Consider whether vision is required for all modes or only automatic capture-driven production runs.

### 7. Architectural coupling is too high between robot system state and application wiring

Severity: Medium

Files:

- `src/robot_systems/paint/application_wiring.py`
- `src/robot_systems/paint/paint_robot_system.py`
- `src/robot_systems/paint/targeting/provider.py`
- `src/robot_systems/paint/navigation.py`

Details:

- Builders frequently reach into `robot_system._...` private state.
- `PaintNavigationService` reaches into `NavigationService._get_group()`.
- `on_start()` builds one runtime object graph, while wiring functions also create fresh repositories, matchers, path executors, and snapshot services.

Risk:

- Lifecycle ownership is unclear.
- Hidden coupling makes refactoring risky.
- Stateful behavior can diverge if different parts of the UI and runtime use different service instances.

Recommendation:

- Replace private-attribute reach-through with explicit provider methods.
- Construct shared runtime services once and inject them consistently.
- Expose safe public APIs instead of using `_get_group()`.

### 8. `PaintWorkpiecePathExecutor` has too many responsibilities

Severity: Medium

Files:

- `src/robot_systems/paint/processes/paint/workpiece_path_executor.py`

Details:

- The class is about 1500 lines long.
- It owns config refresh, pickup planning, pivot projection, robot execution, unwind behavior, vacuum control, debug dumping, debug plotting, and runtime state caching.

Risk:

- Hard to reason about.
- Hard to test in isolation.
- Small changes are likely to create regressions in unrelated parts of execution.

Recommendation:

- Split into smaller collaborators:
- pickup pose planner
- pivot path projector
- execution coordinator
- vacuum operation helper
- debug artifact writer

### 9. Workpiece repository scans the whole tree for common operations

Severity: Low

Files:

- `src/robot_systems/paint/domain/workpieces/repository/json_paint_workpiece_repository.py`

Details:

- `workpiece_id_exists()` loads many files by scanning the storage tree.
- `_find_file()` also linearly scans date folders.

Risk:

- Fine at small scale, but it will degrade as the workpiece library grows.

Recommendation:

- Introduce an index file or metadata cache.
- At minimum, separate list metadata from full raw payload loads.

### 10. Paint-specific test coverage appears missing

Severity: Low

Files:

- no dedicated automated test files were found for the main paint execution flow

Details:

- The only obvious paint-adjacent test file in this area is an ad hoc relay script test.

Risk:

- High-risk geometry and process behavior is changing without safety rails.

Recommendation:

- Add isolated tests for:
- process state transitions
- workpiece preparation and matching fallback behavior
- pickup pose generation
- pivot path projection invariants
- vacuum pump command dispatch

## Strengths

- The system declaration in `paint_robot_system.py` is readable and discoverable.
- The separation between production service, matching, preparation, and execution is directionally good.
- Targeting, calibration, and workpiece editing are already broken into subdomains, which gives a good starting point for cleanup.

## Prioritized Plan

### Phase 1: Correctness and Operator Safety

Priority: Immediate

Tasks:

1. Fix all invalid work-area IDs.
2. Remove duplicate relay command dispatch.
3. Decide and implement real stop behavior for active motion.
4. Disable pause in the UI if it is unsupported.
5. Add explicit process start requirements for the paint process.

Expected outcome:

- Fewer silent state errors.
- Safer and more predictable runtime control.
- More honest UI behavior.

### Phase 2: Execution Path Reliability

Priority: High

Tasks:

1. Implement or remove camera-to-TCP pickup compensation.
2. Add tests around pickup pose generation.
3. Add tests around pivot path preflight and execution preparation.
4. Review whether vacuum-on should happen before approach or only before contact, depending on hardware intent.

Expected outcome:

- Better pickup accuracy.
- Fewer geometry regressions.
- Clearer execution assumptions.

### Phase 3: Production Performance Cleanup

Priority: High

Tasks:

1. Make debug dump and plot generation opt-in.
2. Separate production telemetry from heavy offline diagnostics.
3. Add retention rules for debug artifacts.

Expected outcome:

- Less runtime overhead.
- Cleaner production behavior.
- Lower disk growth.

### Phase 4: Architectural Refactor

Priority: Medium

Tasks:

1. Split `PaintWorkpiecePathExecutor` into smaller services.
2. Stop reaching into `robot_system._...` from wiring where possible.
3. Build shared runtime services once and inject them consistently.
4. Replace private `NavigationService` access with a public capability.

Expected outcome:

- Lower coupling.
- Better testability.
- Easier maintenance and safer future changes.

### Phase 5: Storage and Test Coverage

Priority: Medium

Tasks:

1. Add automated tests for the paint process and geometry helpers.
2. Improve repository lookup strategy for saved workpieces.
3. Replace ad hoc script-style relay tests with proper unit tests.

Expected outcome:

- Better regression protection.
- Better scalability as the workpiece library grows.

## Suggested Implementation Order

1. Fix invalid work-area IDs.
2. Fix duplicate relay dispatch.
3. Hide or disable unsupported pause behavior.
4. Add real stop/interruption support or make stop semantics explicit.
5. Enable process requirements.
6. Gate debug plotting behind configuration.
7. Implement or remove dead pickup compensation config.
8. Start refactoring the executor into smaller components.
9. Add focused automated tests around the refactored pieces.

## Notes

- This review was static analysis only. No hardware-backed validation was run.
- Any change to navigation, targeting, work areas, or process control should be validated on real equipment before production release.
