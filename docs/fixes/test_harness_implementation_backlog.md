# Test Harness Implementation Backlog

Review date: `2026-05-06`

Source inputs:
- [QA-SKILL.md](/home/ilv/Desktop/robot_app_platform/QA-SKILL.md:1)
- [TEST_FAKE_TESTS_REVIEW.md](/home/ilv/Desktop/robot_app_platform/TEST_FAKE_TESTS_REVIEW.md:1)
- [TEST_HARNESS_FINDINGS.md](/home/ilv/Desktop/robot_app_platform/TEST_HARNESS_FINDINGS.md:1)

Current observed suite status:
- `QT_QPA_PLATFORM=offscreen python tests/run_tests.py`
- `1974` total
- `1922` passed
- `10` failed
- `34` errors
- `8` skipped

## Objectives

1. Make the test harness deterministic and headless-safe by default.
2. Remove stale and misleading tests that produce false confidence.
3. Separate product regressions from test-maintenance failures.
4. Expand coverage in the highest-risk unprotected areas.
5. Enforce QA-SKILL falsifiability rules for new tests.

## Exit Criteria

- `python tests/run_tests.py` runs successfully in a headless terminal without extra env setup.
- Temporary test artifacts are written outside `tests/` and cleaned up.
- The current red suite is triaged into `stale`, `contract drift`, and `product regression`.
- Coverage is measured by the harness and reported in CI/local runs.
- `engine/core`, `shared_contracts`, and `paint` gain direct behavioral tests.
- New or rewritten tests document a concrete `Bug caught`.

## Workstreams

### 1. Harness Stabilization

Priority: `P0`

Files:
- [tests/run_tests.py](/home/ilv/Desktop/robot_app_platform/tests/run_tests.py:1)
- [.coveragerc](/home/ilv/Desktop/robot_app_platform/.coveragerc:1)
- new shared test bootstrap module under `tests/`

Tasks:
1. Set `QT_QPA_PLATFORM=offscreen` inside the runner when not already defined.
2. Add a shared bootstrap utility for Qt singleton setup and common test environment configuration.
3. Redirect runtime artifacts to a temp root instead of writing into `tests/`.
4. Add cleanup for generated artifact directories.
5. Run the suite through `coverage run` or add a dedicated coverage command alongside the runner.
6. Print a stable summary that distinguishes failures, errors, and skips.

Acceptance criteria:
- `python tests/run_tests.py` no longer aborts on Qt platform initialization.
- No new files or directories appear under `tests/` after a full run.
- Coverage output is generated consistently from a single documented command.

### 2. Red Suite Triage

Priority: `P0`

Goal:
- convert the current red suite into actionable buckets instead of one mixed failure set

Initial failing targets:
- [tests/applications/workpiece_editor/test_workpiece_editor_view.py](/home/ilv/Desktop/robot_app_platform/tests/applications/workpiece_editor/test_workpiece_editor_view.py:1)
- [tests/robot_systems/glue/test_pick_and_place_workflow.py](/home/ilv/Desktop/robot_app_platform/tests/robot_systems/glue/test_pick_and_place_workflow.py:1)
- [tests/engine/robot/calibration/test_calibration_vision.py](/home/ilv/Desktop/robot_app_platform/tests/engine/robot/calibration/test_calibration_vision.py:1)
- [tests/engine/robot/calibration/test_compute_offsets_handler.py](/home/ilv/Desktop/robot_app_platform/tests/engine/robot/calibration/test_compute_offsets_handler.py:1)
- [tests/engine/robot/test_motion_service.py](/home/ilv/Desktop/robot_app_platform/tests/engine/robot/test_motion_service.py:1)
- [tests/applications/robot_settings/test_robot_settings_mapper.py](/home/ilv/Desktop/robot_app_platform/tests/applications/robot_settings/test_robot_settings_mapper.py:1)

Tasks:
1. Mark each current failure as `stale test`, `contract drift`, or `likely product regression`.
2. Fix stale constructor-signature tests to use current public construction seams.
3. Remove private-hook coupling where the hook is not part of the contract.
4. For ambiguous failures, verify the intended product behavior before updating assertions.
5. Quarantine known stale tests only if they cannot be fixed immediately and only with a written reason.

Acceptance criteria:
- Every current failure has an owner and triage label.
- Constructor drift failures are either fixed or explicitly quarantined.
- No test depends on a removed private hook unless that hook is promoted to contract.

### 3. Low-Value Green Test Cleanup

Priority: `P1`

Goal:
- reduce false confidence from smoke-only and shape-only tests

Known weak patterns:
- commented-out test modules
- `test_implements_interface`
- `does_not_raise` checks
- `inspect.getsource` assertions
- metadata-only “integration” tests
- exact full-key-set mapper assertions when schema growth is allowed

Representative targets:
- [tests/engine/vision/test_vision_service_matching.py](/home/ilv/Desktop/robot_app_platform/tests/engine/vision/test_vision_service_matching.py:1)
- [tests/bootstrap/test_main.py](/home/ilv/Desktop/robot_app_platform/tests/bootstrap/test_main.py:19)
- [tests/robot_systems/glue/test_broker_debug_plugin_integration.py](/home/ilv/Desktop/robot_app_platform/tests/robot_systems/glue/test_broker_debug_plugin_integration.py:1)
- [tests/applications/camera_settings/test_camera_settings_service.py](/home/ilv/Desktop/robot_app_platform/tests/applications/camera_settings/test_camera_settings_service.py:1)
- [tests/engine/hardware/communication/modbus/test_modbus_action_service.py](/home/ilv/Desktop/robot_app_platform/tests/engine/hardware/communication/modbus/test_modbus_action_service.py:1)

Tasks:
1. Delete or restore commented-out tests so visible files always represent executable coverage.
2. Replace type-only stub checks with assertions about state, data mapping, or side effects.
3. Pair interaction assertions with output/state assertions so the test fails when logic is wrong.
4. Replace source-text introspection with behavior or dependency-boundary tests.
5. Reclassify smoke tests as smoke tests and keep them out of coverage-quality claims.

Acceptance criteria:
- Commented-out test files are removed or converted to runnable tests.
- Each rewritten test can answer the QA-SKILL question: `If the implementation were incorrect, would this test fail?`
- Mapper tests assert required semantics, not brittle total key equality, unless full equality is the real contract.

### 4. Coverage Expansion

Priority: `P1`

Goal:
- cover the largest currently under-protected surfaces

Gap areas:
- `src/engine/core/`
- `src/shared_contracts/`
- `src/robot_systems/paint/`
- `src/robot_systems/welding/`
- `src/engine/vision/`

Tasks:
1. Add direct tests for `engine/core` broker lifecycle and request/response behavior.
2. Add direct tests for `shared_contracts` topic names and payload defaults.
3. Add a dedicated `paint` system slice covering app wiring and one behavioral process path.
4. Add a smaller `welding` contract suite to prevent silent shared-refactor breakage.
5. Reintroduce active behavioral vision tests and stop omitting the area from meaningful coverage reporting.

Acceptance criteria:
- `tests/engine/core/` exists with behavioral coverage for broker operations.
- `tests/shared_contracts/` exists and protects event/topic contract drift.
- `tests/robot_systems/paint/` exists with at least one meaningful composition path.
- Coverage reporting includes a visible strategy for `engine/vision`, even if split into a separate lane.

### 5. Test Taxonomy and Execution Lanes

Priority: `P1`

Goal:
- make it obvious what kind of signal each suite provides

Tasks:
1. Define suite lanes such as `unit`, `gui-headless`, `integration`, `bridge-optional`, and `quarantined`.
2. Keep ROS2 bridge tests out of the default required lane unless dependencies are present.
3. Document the commands for each lane.
4. Make the default lane the highest-signal deterministic subset.

Acceptance criteria:
- Test commands map cleanly to named lanes.
- Optional dependency tests do not distort the main pass/fail signal.

### 6. QA-SKILL Enforcement

Priority: `P2`

Goal:
- prevent new fake tests from entering the suite

Tasks:
1. Add a short test-review checklist to repo docs or PR guidance.
2. Require new non-trivial tests to state:
   - `Precondition`
   - `Action`
   - `Assert`
   - `Bug caught`
3. Prefer real logic execution and minimal mocking.
4. Require at least one failure-path or edge-case assertion for new behavior-heavy tests.

Acceptance criteria:
- New tests are reviewed against QA-SKILL falsifiability rules.
- Mock-only delegation tests are not accepted without a paired behavioral assertion.

## Proposed Sequence

### Phase 1: unblock the harness

1. Fix headless execution in [tests/run_tests.py](/home/ilv/Desktop/robot_app_platform/tests/run_tests.py:1).
2. Stop artifact pollution under `tests/`.
3. Add shared bootstrap utilities.
4. Add coverage execution and reporting.

### Phase 2: clean the red suite

1. Triage current failures.
2. Fix stale constructor/private-hook tests.
3. Separate product regressions from outdated assertions.

### Phase 3: remove false confidence

1. Delete or restore commented-out tests.
2. Rewrite low-value stub and smoke-heavy suites.
3. Replace brittle source-introspection tests.

### Phase 4: expand protection

1. Add `engine/core` tests.
2. Add `shared_contracts` tests.
3. Add `paint` tests.
4. Add `welding` tests.
5. Add meaningful `vision` tests.

## Suggested Issue Breakdown

1. `P0: Make test runner headless-safe and artifact-clean`
2. `P0: Triage and fix stale failing tests`
3. `P1: Replace low-value fake tests with falsifiable behavior tests`
4. `P1: Add direct tests for engine/core and shared_contracts`
5. `P1: Add dedicated paint and welding system test slices`
6. `P1: Restore meaningful vision coverage and reporting`

## Notes

- This backlog assumes the current branch is `work`.
- Issues and PRs should reference this document when splitting follow-up work.
- The default goal is better signal quality first, not inflated test count.
