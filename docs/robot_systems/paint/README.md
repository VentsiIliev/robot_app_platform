# `src/robot_systems/paint/` — Paint Robot System

`PaintRobotSystem` is the concrete robot-system package for automated edge painting. It combines:

- a declaration-heavy robot-system class in `paint_robot_system.py`
- robot-system-specific application wiring in `application_wiring.py`
- paint-domain process logic under `processes/paint/`
- supporting paint-domain adapters for workpieces, DXF import, targeting, calibration, and vacuum control

This document is the entry point for the paint system. Use it together with:

- [applications/README.md](applications/README.md)
- [processes/README.md](processes/README.md)
- [processes/paint/ALIGNMENT.md](processes/paint/ALIGNMENT.md)
- [processes/paint/TRAJECTORY_AND_EXECUTION.md](processes/paint/TRAJECTORY_AND_EXECUTION.md)
- [../../pivot_painting_reference.md](../../pivot_painting_reference.md)

---

## Package Map

```text
src/robot_systems/paint/
├── paint_robot_system.py              # robot-system declaration + runtime composition
├── application_wiring.py             # lazy builders for apps and paint runtime services
├── navigation.py                     # paint-specific navigation facade
├── calibration/                      # calibration provider + coordinator adapter
├── targeting/                        # targeting provider + frame/point builders
├── domain/                           # paint-specific schemas, adapters, repositories
├── processes/
│   ├── robot_calibration_process.py  # system-level calibration process
│   └── paint/                        # paint production process package
├── applications/dashboard/           # paint dashboard MVC package
├── service_builders.py               # paint-only service builders (vacuum pump)
└── storage/                          # checked-in settings, users, and workpiece data
```

---

## System Declaration

**File:** `src/robot_systems/paint/paint_robot_system.py`

`PaintRobotSystem` declares the shell, settings, services, movement groups, target points, target frames, work areas, and role policy that the platform consumes through `SystemBuilder`.

### Declared movement groups

| Group | Purpose |
|-------|---------|
| `HOME` | return-to-home pose |
| `CALIBRATION` | calibration observer pose |
| `JOG` | velocity-only jogging |
| `PAINTING` | primary paint / pickup base |
| `PAINTING_NEW` | secondary paint base used by some pivot-plane execution modes |

### Declared target points

| Point | Purpose |
|-------|---------|
| `camera` | camera TCP offset definition |
| `tool` | tool TCP offset definition |

### Declared target frames

| Frame | Work area | Notes |
|-------|-----------|-------|
| `calibration` | `paint` | supports height correction |

### Declared work areas

| Area | Purpose |
|------|---------|
| `paint` | primary work area for capture, targeting, and painting |

The default active work area is `paint`.

---

## Settings

All settings are rooted under `src/robot_systems/paint/storage/settings/`.

| Key (`CommonSettingsID`) | File | Purpose |
|--------------------------|------|---------|
| `ROBOT_CONFIG` | `robot/config.json` | generic robot runtime and tool offsets |
| `MOVEMENT_GROUPS` | `robot/movement_groups.json` | persisted named positions |
| `ROBOT_CALIBRATION` | `robot/calibration.json` | robot/camera calibration settings |
| `TARGETING` | `targeting/definitions.json` | target-point and target-frame persistence |
| `CALIBRATION_VISION_SETTINGS` | `vision/calibration_settings.json` | calibration-specific camera settings |
| `VISION_CAMERA_SETTINGS` | `vision/camera_settings.json` | runtime vision settings |
| `WORK_AREA_SETTINGS` | `vision/work_areas.json` | paint work-area polygons and ROI state |
| `HEIGHT_MEASURING_SETTINGS` | `height_measuring/settings.json` | laser/height-measuring settings |
| `HEIGHT_MEASURING_CALIBRATION` | `height_measuring/calibration_data.json` | height calibration data |
| `DEPTH_MAP_DATA` | `height_measuring/depth_map.json` | stored height-map data |

Non-settings storage owned by the paint system:

- `storage/users/users.csv`
- `storage/workpieces/`

---

## Services

### Declared services

| Name | Type | Required | Source |
|------|------|----------|--------|
| `ROBOT` | `IRobotService` | yes | shared default builder |
| `NAVIGATION` | `NavigationService` | yes | shared default builder |
| `WORK_AREAS` | `IWorkAreaService` | yes | shared default builder |
| `VISION` | `IVisionService` | no | shared default builder |
| `VACUUM_PUMP` | `IVacuumPumpController` | no | `build_vacuum_pump_service()` |

### Runtime-only paint services composed in `on_start()`

These are not `ServiceSpec` declarations. They are robot-system-owned runtime objects created after shared services and settings are available:

- `PaintNavigationService`
- `PaintRobotSystemTargetingProvider`
- height-measuring services via the shared engine builder
- calibration services via the shared engine builder
- `PaintCalibrationCoordinator`
- `PaintWorkpiecePathExecutor`
- `PaintWorkpieceMatchingService`
- `PaintWorkpiecePreparationService`
- `PaintProductionService`
- `PaintProcess`
- `PaintDashboardService`

---

## Shell And Applications

The paint shell currently exposes four folders:

| Folder | `folder_id` |
|--------|-------------|
| Production | `1` |
| Service | `2` |
| Administration | `3` |
| Tests | `4` |

Applications are documented in [applications/README.md](applications/README.md).

---

## Runtime Lifecycle

### `on_start()`

At startup the paint robot system:

1. resolves shared robot, navigation, work-area, and optional vision services
2. builds `PaintNavigationService`
3. loads robot and targeting settings into runtime fields
4. starts and registers the optional vision service
5. builds height-measuring services
6. builds calibration services and the paint calibration coordinator
7. builds workpiece-editor, snapshot, path-preparation, executor, matching, and preparation services
8. builds `PaintProductionService`
9. builds and registers `PaintProcess`
10. builds `PaintDashboardService`
11. enables the robot

### `on_stop()`

Shutdown is intentionally minimal:

1. stop robot motion
2. disable the robot

Longer-lived managed resources such as the vision service and background processes are registered with the robot system and are stopped through the shared platform lifecycle.

---

## Navigation, Targeting, And Calibration

### Navigation

**File:** `src/robot_systems/paint/navigation.py`

`PaintNavigationService` is a paint-specific facade over the shared `NavigationService`. It adds:

- paint-specific convenience moves such as `move_home()` and `move_to_calibration_position()`
- optional capture Z-offset application through the vision service
- active-work-area updates after successful moves

### Targeting

**Files:** `targeting/provider.py`, `targeting/frames.py`, `targeting/registry.py`

`PaintRobotSystemTargetingProvider` merges declared target definitions with persisted targeting settings and exposes:

- point registry construction
- frame construction for work areas
- target options for UI use
- work-area/frame resolution helpers

### Calibration

**Files:** `calibration/provider.py`, `calibration/coordinator.py`

The paint system reuses the shared engine calibration services, but supplies:

- a paint-specific calibration navigation adapter
- a thin coordinator around `RobotCalibrationProcess`

---

## Paint Production Architecture

The actual painting workflow lives under `src/robot_systems/paint/processes/paint/`.

High-level flow:

1. capture a fresh vision snapshot
2. select the usable contour
3. prepare a raw workpiece payload
4. build an execution plan
5. execute pickup, staging, pivot-path painting, and cleanup moves

The package is now structured by responsibility:

- `align/`: image-space placement and contour alignment
- `plan/`: matching and workpiece preparation
- `execute/`: pickup planning, pivot projection, plane strategies, and debug artifacts

Detailed process documentation lives in [processes/paint/README.md](processes/paint/README.md).

---

## Domain Modules

Important paint-domain packages outside the process runtime:

| Path | Responsibility |
|------|----------------|
| `domain/contour_editor_schema.py` | paint-specific editor form schemas |
| `domain/dxf_path_form_behavior.py` | DXF import behavior in the workpiece editor |
| `domain/paint_workpiece_editor_adapter.py` | bridges generic editor payloads with paint workpiece data |
| `domain/workpieces/` | repository and service layer for stored paint workpieces |
| `domain/users/paint_user_schema.py` | paint-system user schema |
| `domain/vacuum_pump/` | vacuum-pump transport/controller implementations |

---

## Application Wiring

**File:** `src/robot_systems/paint/application_wiring.py`

`application_wiring.py` is the composition root for paint applications and paint-process support services. It owns:

- widget-application factory functions used by `shell.applications`
- shared robot-system service builders for the workpiece editor and paint process
- paint-process configuration lookups from `PAINT_PROCESS_CONFIG`

This file is the best starting point when tracing how a paint UI screen gets its dependencies.

---

## Tests

The paint system has focused behavioral coverage under `tests/robot_systems/paint/`.

Important slices:

- `test_paint_system_integration.py`
- `test_paint_process_integration.py`
- `test_paint_workpiece_alignment.py`
- `test_paint_pivot_projection.py`
- `test_paint_execution_plane_strategies.py`
- `test_paint_workpiece_path_executor.py`

These tests are the main safety net for future refactors inside the `align / plan / execute` structure.

---

## Related Docs

- [applications/README.md](applications/README.md)
- [processes/README.md](processes/README.md)
- [processes/paint/README.md](processes/paint/README.md)
- [../../pivot_painting_reference.md](../../pivot_painting_reference.md)
- [../paint_process_refactor_review.md](../paint_process_refactor_review.md)
