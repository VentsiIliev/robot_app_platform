# Test Harness Findings

## Scope

Review date: `2026-05-06`

This review answers two practical questions:

- what the current test harness actually protects today
- what is currently blocking or distorting that protection

I reviewed the test tree, sampled representative files, and ran the suite.

## Current Harness Status

Observed repo size:

- `src/`: `1176` Python files
- `tests/`: `146` discovered `test_*.py` files

Current execution status:

- `python tests/run_tests.py` aborts in a headless environment during Qt startup
- `QT_QPA_PLATFORM=offscreen python tests/run_tests.py` completes discovery and execution
- offscreen run result: `1974` total, `1922` passed, `10` failed, `34` errors, `8` skipped

## Highest-Priority Findings

### 1. The default runner is not headless-safe

Evidence:

- [tests/run_tests.py](/home/ilv/Desktop/robot_app_platform/tests/run_tests.py:13) does plain unittest discovery and execution
- the default run aborts with Qt xcb initialization errors before the suite can finish

Why this matters:

- CI or local terminal runs without a display do not get a usable test result
- the harness currently depends on callers knowing to set `QT_QPA_PLATFORM=offscreen`

Assessment:

- this is a harness defect, not a product defect
- fixing it would immediately make the suite more trustworthy

### 2. A meaningful slice of the red suite is stale due to API drift

These failures are test-maintenance failures first, not strong evidence of runtime breakage.

Representative examples:

- [tests/applications/workpiece_editor/test_workpiece_editor_view.py](/home/ilv/Desktop/robot_app_platform/tests/applications/workpiece_editor/test_workpiece_editor_view.py:9) still constructs `WorkpieceEditorView` without the now-required `workpiece_data_adapter`
- [tests/robot_systems/glue/test_pick_and_place_workflow.py](/home/ilv/Desktop/robot_app_platform/tests/robot_systems/glue/test_pick_and_place_workflow.py:127) still constructs `PickAndPlaceWorkflow` without the now-required `vacuum_pump`
- [tests/engine/robot/calibration/test_calibration_vision.py](/home/ilv/Desktop/robot_app_platform/tests/engine/robot/calibration/test_calibration_vision.py:38) patches a private `_build_aruco_detector` hook that no longer exists

Why this matters:

- these failures do not help refactoring decisions
- they create noise that can hide real regressions
- they show several tests are coupled to constructor signatures and private implementation details

### 3. Some failing tests point to contract drift between tests and current behavior

These failures may represent either intentional behavior changes or real regressions, but the suite currently does not make that distinction cleanly.

Representative examples:

- [tests/applications/robot_settings/test_robot_settings_mapper.py](/home/ilv/Desktop/robot_app_platform/tests/applications/robot_settings/test_robot_settings_mapper.py:75) and [same file](/home/ilv/Desktop/robot_app_platform/tests/applications/robot_settings/test_robot_settings_mapper.py:155) hard-code full expected key sets that no longer match current mapper output
- [tests/engine/robot/test_motion_service.py](/home/ilv/Desktop/robot_app_platform/tests/engine/robot/test_motion_service.py:20) expects `move_ptp()` success semantics that no longer hold in the current implementation
- [tests/applications/calibration/test_calibration_service.py](/home/ilv/Desktop/robot_app_platform/tests/applications/calibration/test_calibration_service.py:44) has a stub-service block that now errors, which usually means the stub contract drifted from the interface

Why this matters:

- this is the part of the red suite that needs triage, not blind updating
- some of these are likely real behavior regressions; some are just outdated assertions

### 4. Eight tests are skipped because bridge dependencies are absent

Evidence:

- the run skipped `ros2_bridge_*` tests because modules such as `motion`, `status`, and `fairino_ros2_robot` were unavailable

Why this matters:

- the suite gives less protection around ROS2 bridge code than the raw test count suggests
- those tests are only conditionally valuable unless their dependency boundary is stabilized

## Coverage Strengths

These areas have enough active tests to be useful refactor guardrails.

### 1. Engine process and repository infrastructure

Strong areas:

- `tests/engine/process/`
- `tests/engine/repositories/`
- `tests/engine/settings/`

Why this matters:

- these tests exercise state transitions, persistence behavior, and caching rules with meaningful assertions

### 2. Base application MVC wiring

Strong areas:

- `tests/applications/base/`
- several controller/model/service suites under `tests/applications/`

Why this matters:

- the repo already has repeatable patterns for testing application-layer composition and behavior in isolation

### 3. Glue-system functional slices

Strongest system-level area today:

- `tests/robot_systems/glue/`

Why this matters:

- glue remains the broadest cross-layer test surface in the repo
- even with some stale files, it is still the only robot-system area with substantial behavioral coverage

## Coverage Gaps Still Blocking Safe Refactors

### 1. Paint has no dedicated system test suite

Observed:

- `src/robot_systems/paint/`: `61` Python files
- `tests/robot_systems/paint/`: no dedicated suite

Risk:

- paint refactors still have almost no direct protection

### 2. Welding has no dedicated system test suite

Observed:

- `src/robot_systems/welding/`: `37` Python files
- `tests/robot_systems/welding/`: no dedicated suite

Risk:

- shared robot-system refactors can silently break welding

### 3. `src/engine/core/` has no direct tests

Observed:

- `src/engine/core/`: `7` Python files
- no direct `tests/engine/core/` suite

Critical missing coverage:

- broker lifecycle behavior
- request/response semantics
- duplicate subscriber handling
- unsubscribe-during-publish behavior

### 4. Vision remains under-protected and partially misleading

Observed:

- `src/engine/vision/`: `156` Python files
- the most substantial matching file is fully commented out: [tests/engine/vision/test_vision_service_matching.py](/home/ilv/Desktop/robot_app_platform/tests/engine/vision/test_vision_service_matching.py:1)

Risk:

- the visible test tree suggests more vision protection than the active suite actually provides

### 5. Shared contracts still have no direct tests

Observed:

- `src/shared_contracts/`: `20` Python files
- no direct tests

Risk:

- topic-name or payload-shape drift can break publishers and subscribers silently

## Triage Recommendation

Before using this suite as a refactor safety net, the highest-value sequence is:

1. Make [tests/run_tests.py](/home/ilv/Desktop/robot_app_platform/tests/run_tests.py:13) force an offscreen Qt platform in test mode.
2. Fix or quarantine stale constructor-signature and private-hook tests.
3. Separate red tests into two buckets: `contract drift` and `likely product regression`.
4. Add direct tests for `engine/core`, plus at least one dedicated harness slice for `paint`.

## Bottom Line

The repo does have a substantial harness, but the current safety signal is diluted by one harness-level environment defect and a noticeable batch of stale tests. After the headless runner issue and API-drift failures are cleaned up, the suite should be materially more useful for refactoring in `glue`, `engine/process`, and the application MVC layer. It is still not sufficient protection for `paint`, `welding`, `engine/core`, or most of `engine/vision`.
