# `src/robot_systems/glue/` — Glue Robot Application

`GlueRobotSystem` is the concrete robot application for automated glue dispensing. It declares 13 applications, 8 settings files, and 6 services. It is the only `BaseRobotSystem` subclass currently in the platform.

---

## Class Declaration

**File:** `glue_robot_system.py`

```python
class GlueRobotSystem(BaseRobotSystem):
    metadata = SystemMetadata(
        name="GlueSystem",
        version="1.0.0",
        description="Automated glue dispensing vision_service",
        settings_root="storage/settings",
    )
```

---

## Settings Files

| Key (`SettingsID`) | Serializer | File Path | Type |
|---------------------|-----------|-----------|------|
| `ROBOT_CONFIG` | `RobotSettingsSerializer` | `robot/config.json` | `RobotSettings` |
| `ROBOT_CALIBRATION` | `RobotCalibrationSettingsSerializer` | `robot/calibration.json` | `RobotCalibrationSettings` |
| `GLUE_SETTINGS` | `GlueSettingsSerializer` | `glue/settings.json` | `GlueSettings` |
| `GLUE_CELLS` | `GlueCellsConfigSerializer` | `glue/cells.json` | `GlueCellsConfig` (3 default cells) |
| `GLUE_CATALOG` | `GlueCatalogSerializer` | `glue/catalog.json` | `GlueCatalog` (glue type library) |
| `MODBUS_CONFIG` | `ModbusConfigSerializer` | `hardware/modbus.json` | `ModbusConfig` |
| `VISION_CAMERA_SETTINGS` | `CameraSettingsSerializer` | `vision/camera_settings.json` | Camera settings |
| `TOOL_CHANGER_CONFIG` | `ToolChangerSettingsSerializer` | `tools/tool_changer.json` | Tool changer config |

All files are stored under `storage/settings/GlueSystem/`. Defaults are auto-created on first run.

---

## Services

| Name (`ServiceID`) | Type | Required | Builder |
|--------------------|------|----------|---------|
| `ROBOT` | `IRobotService` | Yes | Default (`_build_robot_service`) |
| `NAVIGATION` | `NavigationService` | Yes | Default (`_build_navigation`) |
| `VISION` | `IVisionService` | **No** | `build_vision_service` |
| `WEIGHT` | `IWeightCellService` | Yes | `build_weight_cell_service` |
| `MOTOR` | `IMotorService` | Yes | `build_motor_service` |
| `TOOLS` | `IToolService` | **No** | `build_tool_service` |

`build_weight_cell_service` reads `GLUE_CELLS` settings and calls `build_http_weight_cell_service(cells_config, messaging)`.

---

## Shell (Folders + Applications)

| Folder | `folder_id` | Applications |
|--------|------------|--------------|
| Production | 1 | `GlueDashboard`, `WorkpieceEditor`, `WorkpieceLibrary` |
| Service | 2 | `RobotSettings`, `GlueSettings`, `ModbusSettings`, `CellSettings`, `CameraSettings`, `Calibration`, `ToolSettings`, `ContourMatchingTester` |
| Administration | 3 | `BrokerDebug`, `UserManagement` |

### Application Factory Functions

All factories are defined in `application_wiring.py` with lazy imports.

| Application Name | Factory | Key Service(s) Used |
|-----------------|---------|---------------------|
| `GlueDashboard` | `_build_dashboard_application` | `coordinator`, `settings_service`, `weight_service` |
| `WorkpieceEditor` | `_build_workpiece_editor_application` | `vision` (optional), `WorkpieceService`, `settings_service` |
| `WorkpieceLibrary` | `_build_workpiece_library_application` | `GlueWorkpieceLibraryService`, `GLUE_CATALOG` |
| `RobotSettings` | `_build_robot_settings_application` | `RobotSettingsApplicationService(settings, robot, navigation)` |
| `GlueSettings` | `_build_glue_settings_application` | `GlueSettingsApplicationService(settings)` |
| `ModbusSettings` | `_build_modbus_settings_application` | `ModbusSettingsApplicationService(settings)` + `ModbusActionService()` |
| `CellSettings` | `_build_glue_cell_settings_application` | `GlueCellSettingsService(settings, weight)` |
| `CameraSettings` | `_build_camera_settings_application` | `CameraSettingsApplicationService(settings, vision)` |
| `Calibration` | `_build_calibration_application` | `CalibrationApplicationService(vision, coordinator)` |
| `ToolSettings` | `_build_tool_settings_application` | `ToolSettingsApplicationService(settings)` |
| `ContourMatchingTester` | `_build_contour_matching_tester` | `ContourMatchingTesterService(vision, WorkpieceService)` |
| `BrokerDebug` | `_build_broker_debug_application` | `BrokerDebugApplicationService(messaging)` |
| `UserManagement` | `_build_user_management_application` | `UserManagementApplicationService(CsvUserRepository)` |

---

## Lifecycle (`on_start` / `on_stop`)

### `on_start()`

```python
def on_start(self) -> None:
    self._robot      = self.get_service(ServiceID.ROBOT)
    _nav_engine      = self.get_service(ServiceID.NAVIGATION)
    self._navigation = GlueNavigationService(_nav_engine)    # typed facade
    self._vision     = self.get_optional_service(ServiceID.VISION)
    self._tools      = self.get_optional_service(ServiceID.TOOLS)
    # load all settings into instance vars ...
    self._weight = self.get_service(ServiceID.WEIGHT)
    self._weight.start_monitoring(
        cell_ids   = self._glue_cells.get_all_cell_ids(),
        interval_s = 0.5,
    )
    self._vision.start()
    self._motor = self.get_service(ServiceID.MOTOR)
    self._motor.open()
    self._calibration_service = _build_calibration_service(self)
    self._coordinator = self._build_coordinator()
    self._robot.enable_robot()
```

### `on_stop()`

```python
def on_stop(self) -> None:
    self._weight.stop_monitoring()
    self._weight.disconnect_all()
    self._robot.stop_motion()
    self._robot.disable_robot()
    self._motor.close()
```

---

## Coordinator

`GlueOperationCoordinator` is built inside `on_start()` via `_build_coordinator()`. It wraps four processes:

| Process | `ProcessRequirements` |
|---------|----------------------|
| `GlueProcess` | `ROBOT`, `MOTOR`, `VISION` |
| `PickAndPlaceProcess` | `ROBOT`, `VISION` |
| `CleanProcess` | `ROBOT` |
| `RobotCalibrationProcess` | `ROBOT`, `VISION` |

---

## Settings Shim Files

`src/robot_systems/glue/settings/` contains thin re-export shims:

| File | Content |
|------|---------|
| `modbus.py` | Re-exports `ModbusConfig`, `ModbusConfigSerializer` from engine layer |
| `robot.py` | Re-exports `RobotSettings`, `RobotSettingsSerializer` etc. from engine layer |
| `robot_calibration.py` | Legacy `RobotCalibrationConfig` class (runtime config object, not a settings serializer) |
| `cells.py` | Defines `GlueCellsConfigSerializer` with glue-specific defaults (3 cells, default IPs) |
| `glue.py` | Defines `GlueSettings` dataclass + `GlueSettingsSerializer` |
| `glue_types.py` | Defines `Glue`, `GlueCatalog` dataclasses + `GlueCatalogSerializer` |
| `tools.py` | Defines `ToolChangerSettingsSerializer` |

→ Subpackages: [settings/](settings/README.md) · [dashboard/](dashboard/README.md) · [glue_settings/](glue_settings/README.md)
