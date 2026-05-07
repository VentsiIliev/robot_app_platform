# `src/robot_systems/paint/applications/` — Paint Applications

The paint robot system currently has one paint-owned application package plus a larger set of shared applications wired with paint-specific services.

The shell registration happens in:

- `src/robot_systems/paint/paint_robot_system.py`
- `src/robot_systems/paint/application_wiring.py`

---

## Folder Layout

| Folder | Applications |
|--------|--------------|
| Production | `PaintDashboard` |
| Service | `RobotSettings`, `WorkAreaSettings`, `CameraSettings`, `CalibrationSettings`, `Calibration` |
| Administration | `UserManagement` |
| Tests | `WorkpieceLibrary`, `WorkpieceEditor`, `BrokerDebug`, `IntrinsicCapture`, `HandEyeCalibration`, `PickTarget` |

---

## Paint-Owned MVC Package

### `dashboard/`

**Files:** `applications/dashboard/`

This is the only fully paint-owned application package in the system today.

Key pieces:

- `paint_dashboard_factory.py`
- `service/paint_dashboard_service.py`
- `model/paint_dashboard_model.py`
- `controller/paint_dashboard_controller.py`
- `view/paint_dashboard_view.py`

The dashboard is a thin UI over `PaintDashboardService`, which is built in `PaintRobotSystem.on_start()` from the current `PaintProcess`.

Primary responsibility:

- display paint-process state and operator-facing runtime status

---

## Shared Applications With Paint Wiring

Most UI screens are shared platform applications that receive paint-specific services, schemas, or repositories from `application_wiring.py`.

### Workpiece editing and library

| Application | Paint-specific dependency |
|-------------|---------------------------|
| `WorkpieceEditor` | `WorkpieceEditorService` with `PaintWorkpieceEditorAdapter`, paint schemas, paint matching, paint path prep, and paint executor |
| `WorkpieceLibrary` | `PaintWorkpieceLibraryService` over `JsonPaintWorkpieceRepository` |

### Robot, camera, and calibration settings

| Application | Paint-specific dependency |
|-------------|---------------------------|
| `RobotSettings` | paint robot settings service wiring |
| `WorkAreaSettings` | paint work-area declarations and vision integration |
| `CameraSettings` | paint vision settings storage |
| `CalibrationSettings` | paint calibration settings storage |
| `Calibration` | paint calibration coordinator and observer bindings |

### Utility and test applications

| Application | Paint-specific dependency |
|-------------|---------------------------|
| `BrokerDebug` | messaging only |
| `IntrinsicCapture` | optional vision service |
| `HandEyeCalibration` | paint calibration services |
| `PickTarget` | paint targeting provider + robot/navigation context |
| `UserManagement` | paint user schema and permission policy |

---

## Wiring Conventions

`application_wiring.py` follows a few consistent rules:

- all imports are lazy inside builder functions
- paint-owned configuration comes from `PAINT_PROCESS_CONFIG`
- robot-system storage paths come from `BaseRobotSystem` helpers
- the workpiece editor is the main consumer of paint process services outside the background process itself

When adding a new paint screen, prefer following the existing pattern:

1. add a `_build_<app>()` function in `application_wiring.py`
2. keep paint-specific composition there
3. register the app in `PaintRobotSystem.shell`

---

## Workpiece Editor As The Main Paint UI

The workpiece editor is the most paint-specialized screen even though it is built from the shared application package.

It receives:

- paint contour form schema
- paint segment settings schema
- DXF import behavior through `PaintDxfPathFormBehavior`
- paint alignment and image-placement logic
- paint matching service
- paint path preparation service
- paint path executor for preview and execution-oriented diagnostics

That makes it the main authoring surface for paint workpieces and the main manual entry point into the same geometry pipeline later used by the background paint process.
