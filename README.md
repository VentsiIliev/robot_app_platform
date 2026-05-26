<div align="center">

# Robot App Platform

### Vision-guided automation for painting, dispensing, calibration, and contour-based robot work

<p>
  <strong>PyQt6 operator shell</strong> &bull;
  <strong>Modular robot systems</strong> &bull;
  <strong>Camera-to-robot targeting</strong> &bull;
  <strong>DXF/contour workflows</strong>
</p>

![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)
![UI](https://img.shields.io/badge/UI-PyQt6-41CD52?logo=qt&logoColor=white)
![Automation](https://img.shields.io/badge/Domain-Industrial%20Automation-905BA9)
![Status](https://img.shields.io/badge/Active%20System-Paint-F28C28)

</div>

---

## Purpose

Robot App Platform is a desktop control environment for industrial robot cells that combine motion, vision, tooling, saved workpieces, and operator-facing workflows in one modular application.

This fork is currently configured around an **automated edge-painting workflow**: an operator can define or import contours, align them through calibrated vision, position the paint work relative to a physical marker, prepare pickup and pre-paint motion, and execute robot paint paths from a dashboard. The same platform structure also contains **glue dispensing** and **welding** robot-system configurations.

The project is organized so that reusable platform infrastructure remains separate from machine-specific process logic and independent GUI applications.

## Highlights

| Capability | What it provides |
| --- | --- |
| Vision-guided robot motion | Camera capture, calibration data, work-area handling, homography-based pixel-to-robot conversion, and target resolution |
| Automated painting | Paint dashboard, workpiece matching and preparation, pickup-to-paint staging, pivot/edge path execution, vacuum-pump integration, and return-to-calibration flow |
| Marker-based positioning | ArUco marker paint-base placement with runtime marker settings and a safe `PRE_PAINTING` position before contact execution |
| Contour and DXF workflows | Workpiece editing, contour processing, DXF import/export support, alignment logic, and path settings for robot execution |
| PL DXF Vision | Standalone Qt utility for camera-assisted contour capture and calibrated DXF export, with Windows packaging support |
| Calibration and setup | Camera, robot, work-area, intrinsic, hand-eye, height-measuring, and pick-target utilities |
| Operator shell | Folder-based PyQt6 interface, localization support, authorization-aware application visibility, and runtime process controls |
| Extensible cell model | Declaration-driven robot systems, injectable hardware/services, typed messaging topics, and isolated MVC applications |

## Active Paint Workflow

The active bootstrap configuration in [`src/bootstrap/main.py`](src/bootstrap/main.py) selects `PaintBootstrapProvider`, which builds `PaintRobotSystem`.

```text
Create or load a workpiece contour
        |
        v
Capture/match the physical workpiece through vision
        |
        v
Transform contour geometry into robot-space paths
        |
        v
Resolve paint base from the configured ArUco marker
        |
        v
Move through pickup and safe pre-paint staging
        |
        v
Execute projected edge-paint trajectory with tooling control
        |
        v
Return to calibration/service position
```

### Paint Functionality

- `PaintDashboard` provides operational actions such as test pickup, calibration movement, pickup-to-paint staging, pre-paint marker testing, zero/home movement, and error reset.
- `WorkpieceLibrary` and `WorkpieceEditor` manage contour-based workpieces and robot execution geometry.
- The paint process supports the horizontal `xz_y_ry` motion plane, with projected paint travel around an edge/pivot arrangement.
- `PAINTING_NEW` (`Painting2`) is used as the configured horizontal paint base; `PRE_PAINTING` allows planning and staging away from the work surface.
- ArUco-assisted paint positioning is configured through marker settings, defaulting to marker id `1` in `DICT_4X4_1000`.
- Optional vacuum-pump control supports workpiece pickup before painting.
- Vision, calibration, targeting, and work-area settings are integrated into the same operator shell.

> The paint-base marker and pre-paint paths are implemented and covered in repository tests. Physical accuracy still depends on the installed robot, camera, tool offsets, saved movement groups, and cell calibration.

## Platform Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Platform                                                            │
│ src/engine/ · src/bootstrap/ · pl_gui/                              │
│ Messaging, robot services, hardware I/O, persistence, localization  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│ Robot System                                                        │
│ src/robot_systems/paint · glue · welding                            │
│ Declares services, settings, work areas, movement groups, apps      │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│ Applications                                                        │
│ src/applications/                                                   │
│ Isolated MVC screens for operators, setup, diagnostics, and tools   │
└─────────────────────────────────────────────────────────────────────┘
```

### Core Design

- **Messaging:** applications and runtime services communicate through injected broker interfaces and typed shared event contracts.
- **Robot systems:** class-level declarations configure movement groups, required services, settings files, UI folders, work areas, and role policy.
- **Applications:** individual screens use an MVC pattern: view signals go to controllers, controllers use models, and models delegate I/O to application services.
- **Processes:** long-running robot operations use managed state machines with service-health requirements.
- **Vision targeting:** shared vision resolvers turn calibrated observations into positions consumed by system-specific execution code.

## Robot Systems

| System | Focus | Present capabilities |
| --- | --- | --- |
| `paint` | Automated edge painting | Paint dashboard, contour preparation, marker-based paint-base positioning, vacuum pickup, robot calibration, vision and workpiece tools |
| `glue` | Automated glue dispensing | Multi-channel dispensing declarations, pump/motor and weight-cell integrations, toolchanger support, matching and pick/place workflows |
| `welding` | Welding workflow foundation | Dashboard, calibration/targeting providers, height-measuring support, process and path-executor modules |

The application currently launches the **paint** system by default. The alternative system bootstrap providers are retained in [`src/bootstrap/main.py`](src/bootstrap/main.py) for configuration switching during development.

## Operator Applications

The shell loads role-filtered applications from the selected robot system. The paint configuration currently exposes:

| Area | Applications | Purpose |
| --- | --- | --- |
| Production | `PaintDashboard` | Run and supervise paint operations |
| Service | `RobotSettings`, `WorkAreaSettings`, `CameraSettings`, `CalibrationSettings`, `Calibration` | Configure motion, vision, work areas, and calibration |
| Administration | `UserManagement` | Manage users and access policy |
| Tests / Engineering | `WorkpieceLibrary`, `WorkpieceEditor`, `BrokerDebug`, `IntrinsicCapture`, `HandEyeCalibration`, `PickTarget` | Build contours, inspect messaging, calibrate systems, and validate targeting |

Reusable applications elsewhere in the repository add tooling for device control, Modbus setup, glue-cell settings, height measurement, contour matching, login, and pick-and-place diagnostics.

## PL DXF Vision

[`src/tools/vision_dxf_exporter/`](src/tools/vision_dxf_exporter/) contains **PL DXF Vision**, a standalone desktop utility for obtaining contour geometry through calibrated camera input and exporting DXF output.

It supports:

- live camera-assisted contour extraction
- calibration-driven conversion into physical units
- DXF version and output-unit selection
- smoothing and simplification post-processing options
- Windows standalone/installer packaging definitions under [`packaging/vision_dxf_exporter/`](packaging/vision_dxf_exporter/)

Build artifacts are intentionally excluded from Git under `build/` and `dist/`; packaging scripts recreate those outputs.

## Hardware and Integration Surface

The engine provides reusable contracts and services for:

- robot movement, state publication, safety, navigation, and saved movement groups
- camera/vision input, calibration transforms, work areas, and target frames
- Modbus register communication
- motors, generators, laser controls, vacuum pumps, and weight cells
- settings persistence through JSON-backed repositories
- user sessions, authorization, localization, and application visibility

Concrete hardware availability depends on cell configuration and connected equipment. Optional services such as vision or vacuum control may be enabled only for deployments that provide them.

## Repository Layout

```text
src/
  bootstrap/                 Application startup and active system selection
  engine/                    Shared platform, robot, vision, process, and hardware code
  applications/              MVC operator and engineering screens
  robot_systems/
    paint/                   Active automated paint system
    glue/                    Glue dispensing system
    welding/                 Welding system foundation
  tools/vision_dxf_exporter/ PL DXF Vision standalone application
contour_editor/              Contour editing and geometry toolkit
packaging/vision_dxf_exporter/
                              Windows packaging scripts and installer definitions
docs/                        Component-level architecture documentation
tests/                       Application, engine, system, and tool tests
```

## Running the Application

Dependencies are provided through the local `.venv/` used by this workspace rather than a committed requirements manifest.

```bash
source .venv/bin/activate
python src/bootstrap/main.py
```

The active startup configuration launches the paint operator shell. Before commanding real equipment, validate robot connection parameters, movement groups, camera/calibration settings, targeting offsets, work areas, and tooling behavior for the deployed cell.

### Run PL DXF Vision From Source

```bash
source .venv/bin/activate
python src/tools/vision_dxf_exporter/run.py
```

### Run Tests

```bash
source .venv/bin/activate
python tests/run_tests.py
```

For focused verification:

```bash
source .venv/bin/activate
python -m unittest tests/robot_systems/paint/test_paint_marker_positioning.py -v
python -m unittest tests/tools/test_vision_dxf_calibration_transform.py -v
python -m unittest tests/tools/test_vision_dxf_contour_units.py -v
```

## Windows Packaging: PL DXF Vision

On Windows:

```bat
packaging\vision_dxf_exporter\build_installer_windows.bat
```

From Linux with a prepared Wine/Windows Python environment:

```bash
packaging/vision_dxf_exporter/build_installer_wine.sh
packaging/vision_dxf_exporter/build_msi_wixl.sh
```

See [`packaging/vision_dxf_exporter/README.md`](packaging/vision_dxf_exporter/README.md) for prerequisites, installer behavior, and path overrides.

## Linux Installation: Robot App Platform

This fork provides an Ubuntu 24.04 amd64 Debian package for installing the full
Robot App Platform paint operator application with a desktop launcher and a
bundled prepared Python runtime.

Install a published package downloaded from the GitHub release page:

```bash
sudo apt install ./robot-app-platform_0.1.1_amd64.deb
robot-app-platform
```

The launcher keeps mutable robot settings, workpieces, user data, and runtime
outputs in a per-user application mirror under
`$XDG_DATA_HOME/robot-app-platform` (or `~/.local/share/robot-app-platform`).
The installed program under `/opt` remains immutable.
Desktop-menu startup output is retained in
`~/.local/share/robot-app-platform/logs/launcher.log`.

Build the `.deb` from a prepared Ubuntu checkout:

```bash
packaging/linux/debian/build_deb.sh 0.1.1
```

See [`packaging/linux/debian/README.md`](packaging/linux/debian/README.md) for
package layout, target-platform constraints, and smoke-check instructions.

## Documentation

| Topic | Reference |
| --- | --- |
| Application MVC structure | [`docs/applications/README.md`](docs/applications/README.md) |
| Robot-system declarations and builders | [`docs/robot_systems/README.md`](docs/robot_systems/README.md) |
| Engine modules | [`docs/engine/README.md`](docs/engine/README.md) |
| Shared broker contracts | [`docs/shared_contracts/README.md`](docs/shared_contracts/README.md) |
| Pivot painting reference | [`docs/pivot_painting_reference.md`](docs/pivot_painting_reference.md) |
| PL DXF Vision packaging | [`packaging/vision_dxf_exporter/README.md`](packaging/vision_dxf_exporter/README.md) |
| Linux Debian installer | [`packaging/linux/debian/README.md`](packaging/linux/debian/README.md) |

## Safety and Deployment Notes

- Robot motion, pumps, and peripheral controls can command physical equipment. Use verified poses, limits, tool offsets, and guarded operating procedures.
- Calibrated vision paths must be confirmed against the deployed camera and robot frame before production operation.
- Stored debug images and calibration captures in this development fork describe development sessions; they are not a substitute for commissioning on a target cell.
- Generated installer/build outputs remain local and ignored to keep the repository suitable for GitHub hosting.

---

<div align="center">

**Robot App Platform**  
Composable industrial robot workflows with vision, calibrated geometry, and operator-ready tooling.

</div>
