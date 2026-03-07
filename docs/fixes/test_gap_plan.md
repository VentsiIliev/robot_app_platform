# Test Gap Plan: Full Project

Audit of all 62 test files. Organised by layer, highest risk first.
Calibration engine gaps (ExecutableStateMachine, state handlers, context) are
documented separately in `stop_calibration_fix_plan.md` and are not repeated here
except where they overlap with the application layer.

---

## Coverage snapshot

| Layer | Files with tests | Files with zero tests | Risk |
|-------|-----------------|----------------------|------|
| Engine / calibration state machine | 0 of ~10 | ALL | Critical |
| Engine / process (BaseProcess) | 0 of 1 | 1 | High |
| Applications / camera_settings | 0 of ~5 | ALL | High |
| Applications / broker_debug | 0 of ~5 | ALL | Medium |
| Applications / workpiece_library | 0 of ~5 | ALL | High |
| Applications / contour_matching_tester | 0 of ~5 | ALL | Medium |
| Plugin integration (per application) | 4 of 13 apps | 9 apps | High |
| test_main.py | 0 lines of tests | 1 | Medium |
| Controller action handlers (all apps) | Partial | Many | Medium |

---

## SECTION 1 — Engine layer gaps

### 1.1 `BaseProcess` — `src/engine/process/base_process.py`

**New file:** `tests/engine/process/test_base_process.py`

No tests exist for the abstract base. All concrete processes rely on it.

| # | Test | Description |
|---|------|-------------|
| 1 | `test_initial_state_is_idle` | New process starts in IDLE |
| 2 | `test_start_from_idle_transitions_to_running` | `start()` → RUNNING |
| 3 | `test_stop_from_running_transitions_to_stopped` | `stop()` → STOPPED |
| 4 | `test_pause_from_running_transitions_to_paused` | `pause()` → PAUSED |
| 5 | `test_resume_from_paused_transitions_to_running` | `resume()` → RUNNING |
| 6 | `test_stop_from_idle_is_no_op` | `stop()` while IDLE stays IDLE |
| 7 | `test_pause_from_idle_is_no_op` | `pause()` while IDLE stays IDLE |
| 8 | `test_set_error_forces_error_state_from_any_state` | `set_error()` → ERROR regardless of current state |
| 9 | `test_reset_errors_returns_to_idle` | `reset_errors()` → IDLE |
| 10 | `test_start_from_stopped_transitions_to_running` | Restart after stop |
| 11 | `test_state_published_on_transition` | Broker receives state event on each transition |
| 12 | `test_hooks_called_on_start` | `_on_start` hook invoked |
| 13 | `test_hooks_called_on_stop` | `_on_stop` hook invoked |

### 1.2 `ExecutableStateMachine` + calibration state handlers + `RobotCalibrationContext`

Covered fully in `stop_calibration_fix_plan.md` (GAPs 5, 6, 7).
File assignments: `tests/engine/process/test_executable_state_machine.py`,
`tests/engine/robot/calibration/test_robot_calibration_context.py`,
`tests/engine/robot/calibration/test_calibration_state_handlers.py`.

### 1.3 `GlueProcess` — `src/robot_systems/glue/processes/glue_process.py`

**Add to:** `tests/robot_systems/glue/test_glue_processes.py`

`GlueProcess` is a core production process with zero state-transition tests.

| # | Test class | Description |
|---|-----------|-------------|
| 14 | `TestGlueProcessIdentity` | `process_id == "glue"`, initial state IDLE |
| 15 | `TestGlueProcessStateTransitions` | start/stop/pause/resume/set_error/reset_errors — mirror CleanProcess coverage |

### 1.4 `GlueOperationCoordinator` — calibration path

**Add to:** `tests/robot_systems/glue/test_glue_processes.py`
**Class:** `TestGlueOperationCoordinatorCalibration`

| # | Test | Description |
|---|------|-------------|
| 16 | `test_start_calibration_calls_process_start` | `start_calibration()` calls `_calibration_process.start()` |
| 17 | `test_stop_calibration_calls_process_stop_when_active` | After `start_calibration()`, `stop_calibration()` calls `process.stop()` |
| 18 | `test_stop_calibration_clears_active_process` | After stop, `_active_process` is `None` |
| 19 | `test_stop_calibration_when_not_active_does_not_raise` | `stop_calibration()` before start is safe |

---

## SECTION 2 — Application unit test gaps

### 2.1 `camera_settings` — zero tests

**New file:** `tests/applications/camera_settings/test_camera_settings_service.py`

| # | Class | Test |
|---|-------|------|
| 20 | `TestStubCameraSettingsService` | implements interface, `load_settings()` returns `CameraSettingsData`, `save_settings()` no-op, `update_settings()` returns `(True, msg)`, `set_raw_mode()` no-op |
| 21 | `TestCameraSettingsApplicationServiceLoad` | `load_settings()` calls settings_service, returns data |
| 22 | `TestCameraSettingsApplicationServiceSave` | `save_settings(data)` persists via settings_service |
| 23 | `TestCameraSettingsApplicationServiceUpdateSettings` | `update_settings(dict)` merges and saves |
| 24 | `TestCameraSettingsApplicationServiceVisionOptional` | service constructed without vision_service does not raise |
| 25 | `TestCameraSettingsApplicationServiceWorkArea` | `save_work_area` / `get_work_area` roundtrip |

**New file:** `tests/applications/camera_settings/test_camera_settings_model.py`

| # | Class | Test |
|---|-------|------|
| 26 | `TestCameraSettingsModelLoad` | `load()` delegates to service, caches settings |
| 27 | `TestCameraSettingsModelSave` | `save()` delegates to service with current settings |
| 28 | `TestCameraSettingsModelGetFlat` | `get_flat()` returns dict of current settings |

### 2.2 `broker_debug` — zero tests

**New file:** `tests/applications/broker_debug/test_broker_debug_service.py`

| # | Class | Test |
|---|-------|------|
| 29 | `TestStubBrokerDebugService` | implements interface, `get_all_topics()` returns list, `get_subscriber_count()` returns int, `publish()` no-op, `subscribe_spy()` / `unsubscribe_spy()` no-op, `get_topic_map()` returns dict |
| 30 | `TestBrokerDebugApplicationServiceTopics` | `get_all_topics()` reflects broker's registered topics |
| 31 | `TestBrokerDebugApplicationServicePublish` | `publish(topic, msg)` calls broker |
| 32 | `TestBrokerDebugApplicationServiceSpy` | `subscribe_spy` / `unsubscribe_spy` delegates to broker |
| 33 | `TestBrokerDebugApplicationServiceTopicMap` | `get_topic_map()` counts subscribers per topic |

### 2.3 `workpiece_library` — zero tests

**New file:** `tests/applications/workpiece_library/test_workpiece_library_service.py`

| # | Class | Test |
|---|-------|------|
| 34 | `TestWorkpieceLibraryServiceListAll` | `list_all()` returns workpiece records from underlying workpiece_service |
| 35 | `TestWorkpieceLibraryServiceDelete` | `delete(id)` delegates, returns `(True, msg)` on success |
| 36 | `TestWorkpieceLibraryServiceDeleteNotFound` | delete of unknown ID returns `(False, msg)` |
| 37 | `TestWorkpieceLibraryServiceUpdate` | `update(id, updates)` propagates to workpiece_service |
| 38 | `TestWorkpieceLibraryServiceGetThumbnail` | `get_thumbnail(id)` returns bytes or None |
| 39 | `TestWorkpieceLibraryServiceLoadRaw` | `load_raw(id)` returns dict or None |

**New file:** `tests/applications/workpiece_library/test_workpiece_library_model.py`

| # | Class | Test |
|---|-------|------|
| 40 | `TestWorkpieceLibraryModelDelegation` | `list_all`, `delete`, `update` delegate to service |

### 2.4 `contour_matching_tester` — zero tests

**New file:** `tests/applications/contour_matching_tester/test_contour_matching_tester_service.py`

| # | Class | Test |
|---|-------|------|
| 41 | `TestStubContourMatchingTesterService` | implements interface, `get_workpieces()` returns list, `get_latest_contours()` returns list, `run_matching()` returns tuple |
| 42 | `TestContourMatchingTesterServiceGetWorkpieces` | `get_workpieces()` delegates to workpiece_service |
| 43 | `TestContourMatchingTesterServiceRunMatching` | `run_matching(wps, contours)` calls vision service |
| 44 | `TestContourMatchingTesterServiceWithoutVision` | service with `vision_service=None` returns empty/fallback on matching |

### 2.5 `calibration` — stop_calibration chain

Covered in `stop_calibration_fix_plan.md` (GAPs 1, 2, 3).
File assignments: add to existing `test_calibration_controller.py`, `test_calibration_model.py`, `test_calibration_service.py`.

### 2.6 Controller action-handler gaps (all applications)

Each controller has `_on_*` handlers that are signal targets. Currently only signal
*wiring* is tested, not the handler *behaviour*.

**Add to:** `tests/applications/modbus_settings/test_modbus_settings_controller.py`

| # | Class | Test |
|---|-------|------|
| 45 | `TestModbusSettingsControllerPortScan` | `_on_detect_ports()` calls model, view receives port list |
| 46 | `TestModbusSettingsControllerTestConnection` | `_on_test_connection()` calls model, view receives result message |
| 47 | `TestModbusSettingsControllerLoadPopulatesView` | after `load()`, view fields match config values |

**Add to:** `tests/applications/robot_settings/test_robot_settings_controller.py`

| # | Class | Test |
|---|-------|------|
| 48 | `TestRobotSettingsControllerSave` | `_on_save()` collects view values, calls model.save |
| 49 | `TestRobotSettingsControllerPositionBroadcast` | live position subscription updates view when active |

**Add to:** `tests/robot_systems/glue/test_glue_settings_controller.py`

| # | Class | Test |
|---|-------|------|
| 50 | `TestGlueSettingsControllerSave` | `_on_save()` reads view, calls model.save_settings |
| 51 | `TestGlueSettingsControllerSprayOn` | `_on_spray_on()` calls model/service |
| 52 | `TestGlueSettingsControllerSprayOff` | `_on_spray_off()` calls model/service |

**Add to:** `tests/applications/tool_settings/test_tool_settings_controller.py`

| # | Class | Test |
|---|-------|------|
| 53 | `TestToolSettingsControllerAddTool` | add-tool signal calls model.add_tool, view updated |
| 54 | `TestToolSettingsControllerRemoveTool` | remove-tool signal calls model.remove_tool, view updated |
| 55 | `TestToolSettingsControllerUpdateSlot` | update-slot signal calls model.update_slot |

**Add to:** `tests/applications/user_management/test_user_management_controller.py`

| # | Class | Test |
|---|-------|------|
| 56 | `TestUserManagementControllerAddUser` | add signal calls model.add_user, view refreshed |
| 57 | `TestUserManagementControllerDeleteUser` | delete signal calls model.delete_user, view refreshed |
| 58 | `TestUserManagementControllerLoadPopulatesView` | after `load()`, view contains all users |

---

## SECTION 3 — Plugin integration tests (per application)

Standard pattern for each:
```
tests/robot_systems/glue/test_<name>_plugin_integration.py
├── TestXxxApplicationSpec     → spec declared, folder_id, factory, icon
└── TestXxxApplicationFactory  → returns WidgetApplication, fetches correct services
```

Applications missing a plugin integration test: **9 of 13**

### 3.1 `GlueSettings`

**New file:** `tests/robot_systems/glue/test_glue_settings_plugin_integration.py`

| # | Test |
|---|------|
| 59 | `test_spec_declared` — name == "GlueSettings" present in GlueRobotSystem.shell.applications |
| 60 | `test_spec_folder_id` — folder_id == expected folder |
| 61 | `test_spec_has_factory` |
| 62 | `test_spec_icon_set` |
| 63 | `test_factory_returns_widget_application` |
| 64 | `test_factory_fetches_settings_service` — robot_system._settings_service is accessed |

### 3.2 `CameraSettings`

**New file:** `tests/robot_systems/glue/test_camera_settings_plugin_integration.py`

| # | Test |
|---|------|
| 65 | `test_spec_declared` |
| 66 | `test_spec_folder_id` |
| 67 | `test_spec_has_factory` |
| 68 | `test_spec_icon_set` |
| 69 | `test_factory_returns_widget_application` |
| 70 | `test_factory_fetches_vision_service_as_optional` |

### 3.3 `BrokerDebug`

**New file:** `tests/robot_systems/glue/test_broker_debug_plugin_integration.py`

| # | Test |
|---|------|
| 71 | `test_spec_declared` |
| 72 | `test_spec_folder_id` |
| 73 | `test_spec_has_factory` |
| 74 | `test_factory_returns_widget_application` |

### 3.4 `WorkpieceEditor`

**Add to:** `tests/robot_systems/glue/` as `test_workpiece_editor_plugin_integration.py`

| # | Test |
|---|------|
| 75 | `test_spec_declared` |
| 76 | `test_spec_folder_id` |
| 77 | `test_spec_has_factory` |
| 78 | `test_spec_icon_set` |
| 79 | `test_factory_returns_widget_application` |

### 3.5 `UserManagement`

**New file:** `tests/robot_systems/glue/test_user_management_plugin_integration.py`

| # | Test |
|---|------|
| 80 | `test_spec_declared` |
| 81 | `test_spec_folder_id` |
| 82 | `test_spec_has_factory` |
| 83 | `test_factory_returns_widget_application` |
| 84 | `test_factory_creates_service_with_repository` |

### 3.6 `WorkpieceLibrary`

**New file:** `tests/robot_systems/glue/test_workpiece_library_plugin_integration.py`

| # | Test |
|---|------|
| 85 | `test_spec_declared` |
| 86 | `test_spec_folder_id` |
| 87 | `test_spec_has_factory` |
| 88 | `test_spec_icon_set` |
| 89 | `test_factory_returns_widget_application` |
| 90 | `test_factory_fetches_catalog_settings` |

### 3.7 `ToolSettings`

**New file:** `tests/robot_systems/glue/test_tool_settings_plugin_integration.py`

| # | Test |
|---|------|
| 91 | `test_spec_declared` |
| 92 | `test_spec_folder_id` |
| 93 | `test_spec_has_factory` |
| 94 | `test_factory_returns_widget_application` |
| 95 | `test_factory_fetches_settings_service` |

### 3.8 `ContourMatchingTester`

**New file:** `tests/robot_systems/glue/test_contour_matching_tester_plugin_integration.py`

| # | Test |
|---|------|
| 96 | `test_spec_declared` |
| 97 | `test_spec_folder_id` |
| 98 | `test_spec_has_factory` |
| 99 | `test_factory_returns_widget_application` |
| 100 | `test_factory_fetches_vision_service_as_optional` |

### 3.9 `GlueDashboard` — expand partial coverage

**Existing file:** `tests/robot_systems/glue/test_dashboard_plugin_integration.py`
Currently covers only config/catalog construction. Missing:

| # | Test |
|---|------|
| 101 | `test_spec_declared` — name == "GlueDashboard" |
| 102 | `test_spec_folder_id` |
| 103 | `test_spec_has_factory` |
| 104 | `test_spec_icon_set` |
| 105 | `test_factory_returns_widget_application` |
| 106 | `test_factory_fetches_glue_operation_coordinator` |

### 3.10 `GlueCellSettings` — expand partial coverage

**Existing file:** `tests/robot_systems/glue/test_glue_cell_settings_integration.py`
Currently only checks spec name and folder_id. Missing:

| # | Test |
|---|------|
| 107 | `test_spec_has_factory` |
| 108 | `test_spec_icon_set` |
| 109 | `test_factory_returns_widget_application` |
| 110 | `test_factory_fetches_weight_service_as_optional` |

---

## SECTION 4 — Empty / near-empty test files

### 4.1 `test_main.py`

**File:** `tests/bootstrap/test_main.py` — currently empty (1 line).

`main.py` runs the entire startup sequence which is complex. The appropriate coverage
is integration-style smoke tests that mock hardware and Qt.

| # | Test | Description |
|---|------|-------------|
| 111 | `test_main_imports_without_error` | `import src.bootstrap.main` does not raise |
| 112 | `test_startup_sequence_order` | Patch each step; verify call order (EngineContext → SystemBuilder → ShellConfigurator → QApplication → ApplicationLoader → AppShell) |
| 113 | `test_startup_aborts_cleanly_on_engine_build_failure` | Patch `EngineContext.build` to raise; verify process exits with non-zero or raises, does not hang |

---

## Summary: new files to create

| File | Tests | Priority |
|------|-------|----------|
| `tests/engine/process/test_base_process.py` | 13 | Critical |
| `tests/engine/process/test_executable_state_machine.py` | 9 | Critical |
| `tests/engine/robot/calibration/test_robot_calibration_context.py` | 4 | Critical |
| `tests/engine/robot/calibration/test_calibration_state_handlers.py` | 16 | Critical |
| `tests/applications/camera_settings/test_camera_settings_service.py` | 6 | High |
| `tests/applications/camera_settings/test_camera_settings_model.py` | 3 | High |
| `tests/applications/broker_debug/test_broker_debug_service.py` | 5 | Medium |
| `tests/applications/workpiece_library/test_workpiece_library_service.py` | 6 | High |
| `tests/applications/workpiece_library/test_workpiece_library_model.py` | 1 | High |
| `tests/applications/contour_matching_tester/test_contour_matching_tester_service.py` | 4 | Medium |
| `tests/robot_systems/glue/test_glue_settings_plugin_integration.py` | 6 | High |
| `tests/robot_systems/glue/test_camera_settings_plugin_integration.py` | 6 | High |
| `tests/robot_systems/glue/test_broker_debug_plugin_integration.py` | 4 | Medium |
| `tests/robot_systems/glue/test_workpiece_editor_plugin_integration.py` | 5 | High |
| `tests/robot_systems/glue/test_user_management_plugin_integration.py` | 5 | High |
| `tests/robot_systems/glue/test_workpiece_library_plugin_integration.py` | 6 | High |
| `tests/robot_systems/glue/test_tool_settings_plugin_integration.py` | 5 | High |
| `tests/robot_systems/glue/test_contour_matching_tester_plugin_integration.py` | 5 | Medium |
| `tests/bootstrap/test_main.py` (fill in) | 3 | Medium |

## Summary: additions to existing files

| Existing file | New tests | Priority |
|--------------|-----------|----------|
| `test_glue_processes.py` | GlueProcess (2), Coordinator calibration (4) | Critical/High |
| `test_calibration_controller.py` | stop_calibration chain | High |
| `test_calibration_model.py` | stop_calibration delegation | High |
| `test_calibration_service.py` | stop_calibration stub + app service | High |
| `test_modbus_settings_controller.py` | port scan, test connection, load-populates-view | Medium |
| `test_robot_settings_controller.py` | save handler, position broadcast | Medium |
| `test_glue_settings_controller.py` | save, spray_on, spray_off | Medium |
| `test_tool_settings_controller.py` | add/remove tool, update slot | Medium |
| `test_user_management_controller.py` | add/delete user, load populates | Medium |
| `test_dashboard_plugin_integration.py` | standard spec + factory tests | High |
| `test_glue_cell_settings_integration.py` | factory, icon, weight service | High |

**Total new tests: ~113** across 19 new files and 10 expanded existing files.