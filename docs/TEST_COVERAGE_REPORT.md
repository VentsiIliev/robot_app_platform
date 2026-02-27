# Test Coverage Report

**Date:** 2026-02-27
**Total source files:** 214
**Total test files:** 36
**Estimated line coverage:** ~17 %

---

## Summary

| Tier | Count | Description |
|------|-------|-------------|
| Fully tested | 25 | Comprehensive assertions on success + error paths |
| Partially tested | 35 | Tests exist but meaningful gaps remain |
| Not tested | 154 | Zero test coverage |

---

## Fully Tested

Strong coverage with meaningful assertions across success and failure paths.

### `src/bootstrap/`
| Class / function | File |
|-----------------|------|
| `EngineContext.build()` | `build_engine.py` |
| `ShellConfigurator.configure()` | `shell_configurator.py` |
| `ApplicationLoader` | `application_loader.py` |
| `_ApplicationManager` | `application_loader.py` |
| `_WidgetFactory` | `application_loader.py` |

### `src/engine/hardware/communication/modbus/`
| Class / function | What is tested |
|-----------------|---------------|
| `ModbusConfig` | All defaults, custom construction, `to_dict`/`from_dict` roundtrip, `ConfigSerializer` |
| `ModbusActionService.detect_ports()` | Working serial, missing module, exception paths |
| `ModbusActionService.test_connection()` | All config params forwarded, exception handling |

### `src/engine/hardware/weight/`
| Class / function | What is tested |
|-----------------|---------------|
| `WeightCellService` | `connect`, `disconnect`, `read_weight`, `tare`, `update_offset`, `update_scale`, monitoring thread lifecycle, concurrent cells |
| `HttpCellTransport` | All HTTP endpoints, response format variants, HTTP errors, timeouts |
| `http_weight_cell_factory` | Returns `WeightCellService`, correct transport/calibrator wiring |
| `CellsConfig`, `CellConfig`, `CalibrationConfig`, `MeasurementConfig` | Defaults, roundtrip serialization, `get_cell_by_id`, `get_cells_by_type` |

### `src/engine/robot/`
| Class / function | What is tested |
|-----------------|---------------|
| `MotionService` | `move_ptp`, `move_linear`, `start_jog`, `stop_motion`, `_wait_for_position` timeout |
| `RobotService` | Delegation to motion + state layers, tool service optional property |
| `RobotStateManager` | Polling thread start/stop, publisher snapshot, exception resilience |
| `RobotStateSnapshot` | Frozen, `with_extra()` |
| `RobotStatePublisher` | All 4 topics published, correct payloads |
| `ToolChanger` | Slot lookup, availability, `get_occupied_slots`, `get_empty_slots` |
| `SafetyChecker` | No-settings pass-through, position length checks, XYZ bounds, exception fail-open |

### `src/applications/modbus_settings/`
| Class | What is tested |
|-------|---------------|
| `ModbusSettingsMapper` | Flat dict roundtrip, all fields |
| `ModbusSettingsModel` | Load, save, field mutations |
| `ModbusSettingsController` | Signal wiring, save delegation, detect_ports, test_connection, QThread worker |

### `src/applications/robot_settings/`
| Class | What is tested |
|-------|---------------|
| `RobotSettingsMapper` | Flat dict roundtrip |
| `RobotSettingsModel` | Load, save |
| `RobotSettingsController` | Signal wiring, save delegation |

### `src/applications/glue_cell_settings/`
| Class | What is tested |
|-------|---------------|
| `GlueCellMapper` | `cell_to_flat`, `flat_to_cell` |
| `GlueCellSettingsModel` | Load, save, multi-cell state |
| `GlueCellSettingsService` | load/save, push calibration to hardware |

---

## Partially Tested

Tests exist but have meaningful gaps.

### `src/engine/repositories/`
- **Tested (via integration):** `get()` caching, `reload()`, `save()` persistence, file creation
- **Missing:** Direct unit tests for unknown-key raises, corrupt JSON handling, factory `build_from_specs()` in isolation

### `src/applications/base/`
- **Tested:** `ApplicationFactory` and `WidgetApplication` exercised indirectly through integration tests
- **Missing:** Isolated unit tests for the template method wiring (`_create_model` → `_create_view` → `_create_controller` → `controller.load()`), the GC fix (`view._controller = controller`), and `WidgetApplication.create_widget()` + `register()`

### `src/robot_systems/glue/glue_settings/`
- **Tested:** `GlueSettingsController` (full signal coverage), `GlueSettingsMapper`, `GlueSettingsApplicationService` (load/save)
- **Missing:** `GlueSettingsModel` (add/update/remove glue type logic), `GlueSettingsService` (storage interaction), `GlueSettingsView`

### `src/robot_systems/glue/dashboard/`
- **Tested:** `ApplicationSpec` declaration, factory returns `WidgetApplication`, broker subscription via integration
- **Missing:** `GlueDashboardController` (state transitions, button state map, broker callbacks), `GlueDashboardService` (start/stop/pause delegation, process subscription), `GlueDashboardModel` (load, meter value aggregation)

---

## Not Tested At All

### Priority 1 — Business logic, high risk

#### `src/engine/core/MessageBroker` + `MessagingService`
Foundation of the entire event architecture. Zero tests.
- Singleton pattern (`__new__`)
- `subscribe` / `unsubscribe` with weak references
- Automatic cleanup of dead subscribers
- `publish` delivers to all live subscribers
- `request` returns first non-None response
- `get_subscriber_count`, `get_all_topics`, `clear_topic`, `clear_all`
- `MessagingService` facade delegation

#### `src/engine/process/BaseProcess`
Thread-safe state machine. Zero tests.
- `_TRANSITIONS` table enforced correctly (e.g. cannot `pause` from `IDLE`)
- `start()` on IDLE calls `_on_start`; on PAUSED calls `_on_resume`
- Lock is held during hook calls
- Hook exception → forced `ERROR` state + event published
- `set_error()` bypasses `_TRANSITIONS`
- `ProcessTopics.state(name)` event published on every transition
- `ProcessRequirements` checking before start

#### `src/robot_systems/glue/processes/`
All process logic untested.
- `GlueProcess` — start/stop/pause with actual robot service calls
- `CleanProcess` — cleaning sequence
- `PickAndPlaceProcess` — pick-and-place sequence

#### `src/engine/robot/features/NavigationService`
- `move_home()`, `move_to_calibration_position()`, `move_to_login_position()`
- Z-offset application
- Movement group lookup by name
- Error handling on missing group

#### `src/engine/robot/features/ToolManager`
Complex retry and slot management, zero tests.
- `pickup_gripper()` — slot search, `ToolChanger` interaction, retry on transient error, backoff
- `drop_off_gripper()` — slot verification, release
- `add_tool()`, `get_tool()`

#### `src/robot_systems/system_builder.py`
`SystemBuilder` — the assembly step that wires all three levels together.
- `with_robot()`, `with_messaging_service()`, `register()`
- `build(SystemClass)` — settings loaded, services instantiated, system started
- `required=True` service missing → raises
- `required=False` service missing → skipped gracefully

### Priority 2 — Configuration / serialization

#### `src/robot_systems/base_robot_system.py`
- `SettingsSpec`, `ServiceSpec`, `ShellSetup`, `FolderSpec` dataclasses — construction + defaults
- `SystemMetadata` — name, settings_root

#### `src/robot_systems/glue/settings/`
Serializer roundtrips — cheap tests that catch silent data loss.

| File | Class | Gap |
|------|-------|-----|
| `cells.py` | `GlueCellsConfigSerializer` | `to_dict` / `from_dict` roundtrip |
| `glue.py` | `GlueSettingsSerializer` | `to_dict` / `from_dict` roundtrip |
| `modbus.py` | `ModbusSettingsSerializer` | `to_dict` / `from_dict` roundtrip |
| `robot.py` | `RobotSettingsSerializer` | `to_dict` / `from_dict` roundtrip |
| `robot_calibration.py` | `RobotCalibrationSerializer` | `to_dict` / `from_dict` roundtrip |

#### `src/shared_contracts/events/`
Event dataclasses have no contract tests.
- `RobotStateSnapshot` fields present (partially covered)
- `WeightReading`, `CellStateEvent` — field presence, topic string format
- `ProcessStateEvent` — topic format, state value

### Priority 3 — Acceptable gaps

| Module | Reason acceptable |
|--------|-----------------|
| All `*/view/*.py` | PyQt widgets — UI framework not unit-testable without display |
| `engine/robot/drivers/fairino/fairino_robot.py` | Hardware driver, requires physical device |
| `engine/vision/VisionService` | Stub only |
| `robot_systems/glue/application_wiring.py` | Factory wiring covered by integration specs |
| Interfaces (`i_*.py`) | ABCs have no implementation to test |

---

## Test File Map

| Test file | Source covered |
|-----------|---------------|
| `tests/bootstrap/test_build_engine.py` | `build_engine.py` |
| `tests/bootstrap/test_shell_configurator.py` | `shell_configurator.py` |
| `tests/bootstrap/test_application_loader.py` | `application_loader.py` |
| `tests/bootstrap/test_main.py` | `main.py` |
| `tests/bootstrap/test_plugin_loader.py` | *(deleted — replaced by test_application_loader.py)* |
| `tests/engine/hardware/communication/modbus/test_modbus_action_service.py` | `modbus_action_service.py` |
| `tests/engine/hardware/communication/modbus/test_modbus_config.py` | `modbus.py` |
| `tests/engine/hardware/weight/test_weight_cell_service.py` | `weight_cell_service.py` |
| `tests/engine/hardware/weight/test_weight_config.py` | `config.py` (weight) |
| `tests/engine/robot/` | `MotionService`, `RobotService`, `RobotStateManager`, etc. |
| `tests/engine/settings/` | `SettingsService` integration |
| `tests/applications/modbus_settings/test_modbus_settings_controller.py` | `ModbusSettingsController` |
| `tests/applications/modbus_settings/test_modbus_settings_mapper.py` | `ModbusSettingsMapper` |
| `tests/applications/modbus_settings/test_modbus_settings_model.py` | `ModbusSettingsModel` |
| `tests/applications/robot_settings/test_robot_settings_controller.py` | `RobotSettingsController` |
| `tests/applications/robot_settings/test_robot_settings_mapper.py` | `RobotSettingsMapper` |
| `tests/applications/robot_settings/test_robot_settings_model.py` | `RobotSettingsModel` |
| `tests/applications/glue_cell_settings/test_glue_cell_mapper.py` | `GlueCellMapper` |
| `tests/applications/glue_cell_settings/test_glue_cell_settings_model.py` | `GlueCellSettingsModel` |
| `tests/applications/glue_cell_settings/test_glue_cell_settings_service.py` | `GlueCellSettingsService` |
| `tests/robot_systems/glue/test_modbus_settings_plugin_integration.py` | `GlueRobotSystem` modbus wiring |
| `tests/robot_systems/glue/test_glue_cell_settings_integration.py` | `GlueRobotSystem` cell wiring |
| `tests/robot_systems/glue/test_robot_settings_plugin_integration.py` | `GlueRobotSystem` robot settings wiring |
| `tests/robot_systems/glue/test_glue_settings_controller.py` | `GlueSettingsController` |
| `tests/robot_systems/glue/test_glue_settings_model.py` | `GlueSettingsApplicationService` |
| `tests/robot_systems/glue/test_dashboard_plugin_integration.py` | `GlueRobotSystem` dashboard wiring |
