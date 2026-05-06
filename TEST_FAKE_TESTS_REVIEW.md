# Fake / Low-Value Test Review

## Scope

Review date: `2026-05-06`

This document covers representative tests I inspected directly under the `QA-SKILL.md` falsifiability rule:

> If the implementation were incorrect, would this test fail?

The findings below focus on tests that create a false sense of safety, not on every weak test in the suite.

## Main Finding

The repo contains four recurring low-value patterns:

1. tests that look substantial but are not active
2. smoke tests that only prove importability or construction
3. mock-only delegation tests that barely exercise logic
4. brittle implementation-coupled tests that fail on harmless refactors

## Reviewed Examples

### 1. Commented-out file that looks like real coverage

File:

- [tests/engine/vision/test_vision_service_matching.py](/home/ilv/Desktop/robot_app_platform/tests/engine/vision/test_vision_service_matching.py:1)

Review:

- Test: `entire file`
- Precondition: the repo contains a large matching test module
- Action: unittest discovery runs
- Assert: none, because every line is commented out
- Bug caught: none

Verdict:

- fake coverage
- this file visually implies vision matching protection while contributing zero executable tests

### 2. Import smoke test with minimal falsifiability

File:

- [tests/bootstrap/test_main.py](/home/ilv/Desktop/robot_app_platform/tests/bootstrap/test_main.py:19)

Review:

- Test: `test_main_module_imports_without_error`
- Precondition: `src.bootstrap.main` imports successfully
- Action: import module
- Assert: `callable(m.main)`
- Bug caught: syntax or import-time crash only

Verdict:

- valid as a smoke test
- too weak to count as bootstrap behavior protection

### 3. “Integration” test that only checks metadata and construction

File:

- [tests/robot_systems/glue/test_broker_debug_plugin_integration.py](/home/ilv/Desktop/robot_app_platform/tests/robot_systems/glue/test_broker_debug_plugin_integration.py:31)

Representative reviewed tests:

- Test: `test_spec_declared`
- Precondition: app spec exists on `GlueRobotSystem.shell.applications`
- Action: fetch spec
- Assert: spec is not `None`
- Bug caught: only missing registration

- Test: `test_factory_returns_widget_application`
- Precondition: factory is callable
- Action: build app
- Assert: result is `WidgetApplication`
- Bug caught: only gross construction failure

Verdict:

- these are construction/registration smoke tests, not real integration tests
- they do not prove widget behavior, controller wiring, or cleanup behavior

### 4. Stub-service interface checks that barely test behavior

File:

- [tests/applications/camera_settings/test_camera_settings_service.py](/home/ilv/Desktop/robot_app_platform/tests/applications/camera_settings/test_camera_settings_service.py:57)

Representative reviewed tests:

- Test: `test_implements_interface`
- Precondition: stub instance exists
- Action: none
- Assert: `isinstance(..., ICameraSettingsService)`
- Bug caught: almost none beyond class inheritance drift

- Test: `test_load_settings_returns_data`
- Precondition: stub instance exists
- Action: call `load_settings()`
- Assert: result is `CameraSettingsData`
- Bug caught: only return-type drift

- Test: `test_set_raw_mode_does_not_raise`
- Precondition: stub exists
- Action: call method twice
- Assert: no exception
- Bug caught: only unexpected crash

Verdict:

- acceptable as tiny scaffold checks
- should not be counted as service-level safety

### 5. Mock-only delegation tests with weak behavioral assertions

File:

- [tests/applications/camera_settings/test_camera_settings_service.py](/home/ilv/Desktop/robot_app_platform/tests/applications/camera_settings/test_camera_settings_service.py:95)

Representative reviewed tests:

- Test: `test_load_calls_settings_service_get`
- Precondition: service has mocked dependency
- Action: call `load_settings()`
- Assert: `ss.get.assert_called_once()`
- Bug caught: dependency not called

- Test: `test_save_calls_vision_update_settings`
- Precondition: service has mocked dependency
- Action: call `save_settings(...)`
- Assert: `vs.update_settings.assert_called_once()`
- Bug caught: dependency not called

Verdict:

- these prove wiring
- they do not prove data mapping, fallback behavior, or meaningful observable outputs unless paired with stronger assertions

### 6. Shape/type assertions that let wrong behavior pass

File:

- [tests/applications/contour_matching_tester/test_contour_matching_tester_service.py](/home/ilv/Desktop/robot_app_platform/tests/applications/contour_matching_tester/test_contour_matching_tester_service.py:43)

Representative reviewed tests:

- Test: `test_implements_interface`
- Precondition: stub exists
- Action: none
- Assert: `isinstance`
- Bug caught: inheritance drift only

- Test: `test_get_workpieces_returns_list`
- Precondition: stub exists
- Action: call `get_workpieces()`
- Assert: result is a list and length is greater than zero
- Bug caught: only empty return or wrong container type

- Test: `test_run_matching_returns_tuple`
- Precondition: stub exists
- Action: call `run_matching([], [])`
- Assert: result is a tuple of length `4`
- Bug caught: shape drift only

Verdict:

- these are classic false-confidence tests
- the core matching behavior could be wrong and these tests would still pass

### 7. Source-text introspection instead of contract testing

File:

- [tests/engine/hardware/communication/modbus/test_modbus_action_service.py](/home/ilv/Desktop/robot_app_platform/tests/engine/hardware/communication/modbus/test_modbus_action_service.py:25)

Reviewed tests:

- Test: `test_does_not_depend_on_settings_service`
- Precondition: source file can be inspected
- Action: `inspect.getsource(ModbusActionService)`
- Assert: source text does not contain `"ISettingsService"` or `"settings_service"`
- Bug caught: string presence only

- Test: `test_does_not_depend_on_settings_repository`
- Precondition: source file can be inspected
- Action: inspect source text
- Assert: string `"ISettingsRepository"` is absent
- Bug caught: string presence only

Verdict:

- brittle and low-signal
- fails on harmless refactors, aliases, comments, or formatting changes
- should be replaced by tests of public behavior and dependency boundaries

### 8. Exact key-set tests are brittle and over-coupled

File:

- [tests/applications/robot_settings/test_robot_settings_mapper.py](/home/ilv/Desktop/robot_app_platform/tests/applications/robot_settings/test_robot_settings_mapper.py:75)
- [same file](/home/ilv/Desktop/robot_app_platform/tests/applications/robot_settings/test_robot_settings_mapper.py:155)

Reviewed tests:

- Test: `test_all_expected_keys_present`
- Precondition: mapper returns a flat dict
- Action: call mapper
- Assert: returned key set equals one hard-coded set exactly
- Bug caught: key addition/removal only

Verdict:

- these are not fake, but they are brittle
- they turn harmless schema extension into a failing test
- they should usually assert required keys and critical semantic mappings, not exact total equality

### 9. Constructor and private-hook coupling creates noisy failures

Files:

- [tests/applications/workpiece_editor/test_workpiece_editor_view.py](/home/ilv/Desktop/robot_app_platform/tests/applications/workpiece_editor/test_workpiece_editor_view.py:9)
- [tests/robot_systems/glue/test_pick_and_place_workflow.py](/home/ilv/Desktop/robot_app_platform/tests/robot_systems/glue/test_pick_and_place_workflow.py:127)
- [tests/engine/robot/calibration/test_calibration_vision.py](/home/ilv/Desktop/robot_app_platform/tests/engine/robot/calibration/test_calibration_vision.py:38)

Representative reviewed tests:

- Test: `_make_view()`-based workpiece editor tests
- Precondition: constructor signature stays frozen
- Action: construct view without `workpiece_data_adapter`
- Assert: construction succeeds
- Bug caught: none when signature evolves legitimately

- Test: `PickAndPlaceWorkflow(...)` tests
- Precondition: constructor keeps old parameter list
- Action: instantiate without `vacuum_pump`
- Assert: workflow can run
- Bug caught: none when dependency injection evolves legitimately

- Test: `test_detect_specific_marker_uses_single_scale_detector`
- Precondition: private method `_build_aruco_detector` exists
- Action: patch private hook
- Assert: patched path is used
- Bug caught: implementation-shape drift, not user-visible behavior

Verdict:

- these are high-maintenance tests
- they are useful only if the constructor shape or private seam is itself the contract, which is not the case here

## Reclassification Guidance

These tests should be treated as lower-signal categories unless strengthened:

- smoke tests
- construction checks
- interface-shape checks
- stub scaffolding checks
- dependency-delegation checks

They are not meaningless, but they should not be used as evidence that a module is safe to refactor.

## Better Replacements

The strongest replacements for the patterns above are:

1. assert exact transformed values rather than container type or truthiness
2. test public behavior through real logic with minimal mocking
3. assert required keys and semantic round-trips instead of exact key inventory when schemas are expected to grow
4. test user-visible outcomes rather than private helper names or source text
5. delete or restore commented-out files so coverage signals are honest

## Bottom Line

The main risk is not that the suite has no tests. The risk is that parts of the suite are easy to over-credit. The most misleading areas today are commented-out vision coverage, plugin “integration” smoke tests, stub/interface checks, and source-introspection tests. Those should be counted as low-signal until they are replaced with falsifiable behavior checks.
