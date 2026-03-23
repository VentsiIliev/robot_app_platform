# `src/robot_systems/glue/` — Glue Robot Application

`GlueRobotSystem` is the concrete robot application for automated glue dispensing. It currently declares 18 applications, 12 settings files, and 6 services. It is the only `BaseRobotSystem` subclass currently in the platform.

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
| `GLUE_TARGETING` | `GlueTargetingSettingsSerializer` | `targeting/definitions.json` | Named point definitions, named frame definitions, and point aliases for glue targeting |
| `GLUE_CELLS` | `GlueCellsConfigSerializer` | `glue/cells.json` | `GlueCellsConfig` (3 default cells) |
| `GLUE_CATALOG` | `GlueCatalogSerializer` | `glue/catalog.json` | `GlueCatalog` (glue type library) |
| `MODBUS_CONFIG` | `ModbusConfigSerializer` | `hardware/modbus.json` | `ModbusConfig` |
| `VISION_CAMERA_SETTINGS` | `CameraSettingsSerializer` | `vision/camera_settings.json` | Camera settings |
| `TOOL_CHANGER_CONFIG` | `ToolChangerSettingsSerializer` | `tools/tool_changer.json` | Tool changer config |
| `HEIGHT_MEASURING_SETTINGS` | `HeightMeasuringSettingsSerializer` | `height_measuring/settings.json` | Height-measuring settings |
| `HEIGHT_MEASURING_CALIBRATION` | `LaserCalibrationDataSerializer` | `height_measuring/calibration_data.json` | Laser calibration data |
| `DEPTH_MAP_DATA` | `DepthMapDataSerializer` | `height_measuring/depth_map.json` | Stored depth-map data |
| `GLUE_MOTOR_CONFIG` | `GlueMotorConfigSerializer` | `hardware/motors.json` | Glue motor board config + motor topology |

Files are resolved under `src/robot_systems/glue/storage/settings/`. `BaseRobotSystem.describe()` reports this as `storage/settings/gluesystem/` because it combines `settings_root` with `metadata.name.lower()`, but the actual checked-in glue system defaults live in the robot-system package under `storage/settings/`.

`robot/config.json` now contains only generic robot/runtime settings. Glue targeting definitions live in `targeting/definitions.json`, outside the glue-dispensing settings namespace, so the targeting model can evolve independently of both platform-level robot configuration and glue-process settings.

Non-settings storage paths are now standardized on `BaseRobotSystem` instead of being hardcoded as module globals in `application_wiring.py`. Shared runtime code uses:
- `workpieces_storage_path()`
- `users_storage_path()`
- `permissions_storage_path()`

---

## Services

| Name (`ServiceID`) | Type | Required | Builder |
|--------------------|------|----------|---------|
| `ROBOT` | `IRobotService` | Yes | Default (`_build_robot_service`) |
| `NAVIGATION` | `NavigationService` | Yes | Default (`_build_navigation`) |
| `VISION` | `IVisionService` | **No** | `build_vision_service` |
| `WEIGHT` | `IWeightCellService` | Yes | `build_weight_cell_service` |
| `MOTOR` | `IMotorService` | Yes | `build_motor_service` |
| `TOOLS` | `IToolService` | **No** | Default (`build_tool_service`) |

`build_weight_cell_service` reads `GLUE_CELLS` settings and calls `build_http_weight_cell_service(cells_config, messaging)`.

The glue system now relies on three shared engine assembly paths:

- `IVisionService` → default builder
- `IToolService` → default builder
- robot calibration / height measuring → shared engine builders plus glue
  providers

---

## Shell (Folders + Applications)

| Folder | `folder_id` | Applications |
|--------|------------|--------------|
| Production | 1 | `GlueDashboard`, `WorkpieceEditor`, `WorkpieceLibrary` |
| Service | 2 | `RobotSettings`, `GlueSettings`, `ModbusSettings`, `CellSettings`, `CameraSettings`, `DeviceControl`, `Calibration`, `ToolSettings` |
| Administration | 3 | `UserManagement` |
| Tests | 4 | `BrokerDebug`, `ContourMatchingTester`, `GlueProcessDriver`, `HeightMeasuring`, `PickAndPlaceVisualizer`, `PickTarget` |

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
| `DeviceControl` | `_build_device_control_application` | `DeviceControlApplicationService(motor, settings)` |
| `ToolSettings` | `_build_tool_settings_application` | `ToolSettingsApplicationService(settings)` |
| `ContourMatchingTester` | `_build_contour_matching_tester` | `ContourMatchingTesterService(vision, WorkpieceService)` |
| `HeightMeasuring` | `_build_height_measuring_application` | `HeightMeasuringApplicationService(height_measuring, calibration, vision)` |
| `PickAndPlaceVisualizer` | `_build_pick_and_place_visualizer` | `PickAndPlaceVisualizerService(coordinator)` |
| `PickTarget` | `_build_pick_target_application` | `PickTargetApplicationService(vision, robot, resolver, robot_config, navigation)` |
| `GlueProcessDriver` | `_build_glue_process_driver_application` | `GlueProcessDriverService(GlueProcess, MatchingService, GlueJobBuilderService, GlueJobExecutionService)` |
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
    self._height_measuring_provider = GlueRobotSystemHeightMeasuringProvider(self)
    self._height_measuring_service, self._height_measuring_calibration_service, \
        self._laser_detection_service = build_robot_system_height_measuring_services(self)
    self._calibration_provider = GlueRobotSystemCalibrationProvider(self)
    self._calibration_service = build_robot_system_calibration_service(self)
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

`GlueNavigationService` remains the glue runtime facade for glue-specific
workflow movement such as `HOME`, `LOGIN`, pickup, and capture-offset-aware
navigation.

Calibration now uses the generic engine-level
`CalibrationNavigationService` instead:

- it moves to the standard `CALIBRATION` navigation group through the shared
  `NavigationService`
- the glue-only side effect `vision.set_detection_area("spray")` is injected
  explicitly from glue wiring via the adapter's `before_move` callback

That keeps the calibration path reusable without baking glue camera policy into
the generic navigation abstraction.

Height measuring now follows the same pattern:

- the generic engine builder assembles detector, detection, calibration, and
  measuring services from common settings and repositories
- the glue system supplies only `GlueRobotSystemHeightMeasuringProvider`
- that provider's only job is to build the glue-specific laser control

---

## Coordinator

`GlueOperationCoordinator` is built inside `on_start()` via `_build_coordinator()`. It wraps four processes:

| Process | `ProcessRequirements` |
|---------|----------------------|
| `GlueProcess` | `ROBOT`, `MOTOR`, `VISION` |
| `PickAndPlaceProcess` | `ROBOT`, `VISION` |
| `CleanProcess` | `ROBOT` |
| `RobotCalibrationProcess` | `ROBOT`, `VISION` |

The coordinator owns the runtime mode selection:
- `SPRAY_ONLY`
- `PICK_AND_SPRAY`

`PickAndPlaceProcess` now also publishes structured diagnostics on `PickAndPlaceTopics.DIAGNOSTICS` while it runs. Those snapshots expose the current workflow stage, active workpiece/gripper, resolved height source, plane state, and the last typed error.

`GlueRobotSystem` also builds a reusable `GlueJobExecutionService` during coordinator setup. That service encapsulates:

1. move the robot to the `CALIBRATION` position using the vision capture offset
2. wait briefly for the camera/scene to stabilize
3. capture latest contours
4. run contour matching
5. build the glue job from matched workpieces
6. load the job into `GlueProcess`
7. optionally start `GlueProcess`

It is reused in two places:
- dashboard `SPRAY_ONLY` start
- `PICK_AND_SPRAY` handoff after pick-and-place finishes

The glue system also owns one shared `VisionTargetResolver` runtime instance. It is built through the generic base-system method `self.get_shared_vision_resolver()`, which delegates the glue-specific details to `GlueRobotSystemTargetingProvider`, caches the result on the robot system, and injects it into:
- `PickTargetApplicationService`
- `GlueJobBuilderService`
- `PickAndPlaceProcess` / `PickAndPlaceWorkflow`

That keeps point/frame definitions and TCP-delta logic consistent across the whole glue system.

### `SPRAY_ONLY`

In dashboard spray-only mode, pressing Start still goes through `GlueOperationCoordinator.start()`. The coordinator reads `GlueSettings.spray_on` from `SettingsID.GLUE_SETTINGS`, passes that value into `GlueJobExecutionService.prepare_and_load(...)`, and starts the spray sequence only if preparation succeeds.

This path now distinguishes clearly between resume and restart:

1. if the glue process is `paused`, `SPRAY_ONLY` Start/Resume continues the already active run in place and does **not** re-run capture/match/build/load
2. if the previous glue run is `stopped` or has already completed, `SPRAY_ONLY` Start is treated as a fresh run and goes back through the full preparation flow again before glue motion starts

### `PICK_AND_SPRAY`

In pick-and-spray mode, the coordinator still owns the sequence:

1. `PickAndPlaceProcess` starts
2. when it stops, the `ProcessSequence.before_next_start(...)` hook runs
3. the hook reads `GlueSettings.spray_on` from `SettingsID.GLUE_SETTINGS`
4. the hook calls `GlueJobExecutionService.prepare_and_load(spray_on=<configured value>)`
5. `GlueProcess` starts only if preparation succeeds

If preparation fails, the transition is blocked and the glue process is marked with an error message.

The mandatory capture-position step is shared by all callers of `GlueJobExecutionService`, so the behavior is the same whether glue is started from the dashboard, from the glue driver backend, or from the pick-and-spray sequence.

When a glue job is prepared and loaded successfully, the same execution service now also publishes a static preview overlay event for the production dashboard:

1. capture image used for glue preparation
2. image-space glue segments preserved before robot-coordinate conversion
3. `GlueOverlayJobLoadedEvent` published on `GlueOverlayTopics.JOB_LOADED`

The dashboard uses that to render a static progress image and color completed vs pending segments while glue runs.

The preparation phase is also cancellable. If the operator presses Stop or Pause while glue is still moving to the capture position, stabilizing, matching, building, or loading, the coordinator cancels the pending preparation and the robot stop command is issued before glue starts.

The capture-position move now uses a cancellable navigation wait path, so cancellation interrupts the move wait immediately instead of waiting for the navigation timeout to expire.

The spray-enable behavior for this automated path is not hardcoded. It comes from `GlueSettings.spray_on` in `src/robot_systems/glue/storage/settings/glue/settings.json`, accessed through the shared settings service.

Within the glue dispensing process, robot motion can now be configured independently from pump behavior:
- `use_segment_motion_settings=True` makes `move_to_first_point` and `execute_trajectory` use per-segment `velocity` / `acceleration` when those fields exist in the workpiece segment settings
- if segment motion values are missing, or the flag is disabled, the process falls back to `global_velocity` / `global_acceleration`

The glue navigation facade now treats `move_home()` literally: it moves directly to the `HOME` group, applying the vision capture Z offset when configured, but it does not insert an automatic calibration waypoint. Any required move to `CALIBRATION` must be requested explicitly by the caller.

The `PickTarget` debug application now uses that same distinction explicitly:
- in calibration-plane mode its `Start` action moves to `CALIBRATION`
- in pickup-plane mode its `Start` action moves to `HOME`

`PickTarget` also now exposes a dedicated pickup-plane test mode that combines:
- calibration-plane to pickup-plane mapping via `PlanePoseMapper`
- operator-controlled pickup `rz`
- TCP-delta compensation relative to the known-good `90°` pickup reference

That debug path exists to validate orientation-dependent pickup targeting before applying the same correction model to the production pick-and-place workflow.

Within pick-and-place, camera-to-robot conversion is now also split explicitly by plane:
- homography maps image points into calibration-plane robot coordinates
- matching captures contours and the current robot pose together through `ICaptureSnapshotService`
- a dedicated `PlanePoseMapper` is rebuilt at transform time to convert those coordinates into the actual capture-pose frame
- `VisionTargetResolver` (from [`src/engine/robot/targeting/`](/home/ilv/Desktop/robot_app_platform/src/engine/robot/targeting)) then resolves the requested target point in that plane:
  - `camera`
  - `tool`
  - `gripper`
- capture-plane reference-angle correction is applied before target-point offsets are added
- `PickupCalculator` now assumes XY is already fully resolved and only applies heights and final orientation

The current transformation order for pickup is:

1. capture contours and current robot pose together via `ICaptureSnapshotService`
2. image pixel -> calibration-plane XY via homography
3. calibration-plane XY -> capture-plane XY via `PlanePoseMapper`
4. capture-plane reference-angle delta using calibrated `camera_to_tcp_*`
5. camera/tool/gripper target resolution from measured reference points
6. pose construction in `PickupCalculator`

For glue dispensing, the transform path is separate and currently simpler:

1. image-space spray contour point
2. raw homography into calibration-plane XY
3. `VisionTargetResolver.resolve(VisionPoseRequest(...), registry.by_name("tool"))` — resolves to the tool point and returns the final pose, no plane mapper
4. final spray waypoint `[x, y, z, rx, ry, rz]` for `GlueProcess`

This means the glue process now resolves spray geometry to the configured tool point directly, but it does not apply capture-pose plane remapping like pick-and-place.

The glue system’s main robot calibration can now also capture camera-TCP offset samples during the normal marker-alignment run. When enabled in `robot/calibration.json`, up to `max_markers_for_tcp_capture` centered markers can be revisited at several wrist `rz` angles, re-centered iteratively, and used to solve a local `camera_to_tcp_x_offset` / `camera_to_tcp_y_offset` result that is saved back into `robot/config.json` only if the sample spread passes the configured acceptance threshold. If TCP-offset capture fails on one marker, the calibration logs a warning and continues with the next marker instead of aborting the whole run.

The calibration service now refreshes both `robot/calibration.json` and `robot/config.json` from the shared `SettingsService` each time a calibration run starts. In practice this means changes made in Robot Settings, such as TCP-capture iterations or robot tool/user values, are picked up by the next calibration run immediately without restarting the glue application.

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
| `device_control.py` | Defines `GlueMotorConfig`, `MotorSpec`, and `GlueMotorConfigSerializer` for `hardware/motors.json` |

→ Subpackages: [settings/](settings/README.md) · [dashboard/](dashboard/README.md) · [glue_settings/](glue_settings/README.md) · [pick_and_place/](processes/pick_and_place/README.md) · [targeting/](targeting/README.md)
