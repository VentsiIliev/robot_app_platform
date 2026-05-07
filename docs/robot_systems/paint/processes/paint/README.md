# `src/robot_systems/paint/processes/paint/` — Paint Production Package

This package contains the full paint production workflow used both by the background paint process and by parts of the workpiece editor preview path.

Deep technical references:

- [ALIGNMENT.md](ALIGNMENT.md)
- [TRAJECTORY_AND_EXECUTION.md](TRAJECTORY_AND_EXECUTION.md)

It is now organized by responsibility:

```text
paint/
├── paint_process.py
├── paint_production_service.py
├── config.py
├── align/
│   ├── __init__.py
│   ├── dxf_image_placement.py
│   └── alignment/
│       ├── core.py
│       ├── io.py
│       └── sampling.py
├── plan/
│   ├── workpiece_matching_service.py
│   └── workpiece_preparation_service.py
└── execute/
    ├── workpiece_path_executor.py
    ├── paint_debug_artifacts.py
    ├── execution_plane/
    │   └── strategies.py
    └── pivot_projection/
        └── core.py
```

---

## End-To-End Flow

The production path is:

1. `PaintProcess` starts a background run
2. `PaintProductionService` captures a contour and prepares a workpiece
3. `DefaultWorkpiecePathPreparationService` builds the execution plan
4. `PaintWorkpiecePathExecutor` performs pickup, staging, pivot projection, and paint execution

The workpiece editor reuses large parts of the same stack for preview and DXF-assisted authoring.

---

## `align/`

`align/` owns geometry preparation before path planning.

### Responsibilities

- map DXF/mm-space workpiece geometry into image space
- extract and normalize raw contour payload points
- align DXF-based workpieces to captured contours
- resample and smooth contour geometry used by alignment

### Key entry points

| Function | Purpose |
|----------|---------|
| `map_raw_workpiece_mm_to_image()` | place DXF geometry into image coordinates |
| `estimate_local_image_basis()` | derive local image basis for DXF placement |
| `align_raw_workpiece_to_contour()` | fit a raw workpiece to a captured contour |

### Internal split

| Module | Responsibility |
|--------|----------------|
| `dxf_image_placement.py` | image-space placement from DXF/mm geometry |
| `alignment/io.py` | raw contour payload extraction/rewrite helpers |
| `alignment/sampling.py` | resampling, smoothing, contour stats |
| `alignment/core.py` | alignment solve, transform application, scoring |

---

## `plan/`

`plan/` owns workpiece selection and transformation from captured contour to execution-ready raw workpiece payload.

### `workpiece_matching_service.py`

`PaintWorkpieceMatchingService` bridges the vision matcher and stored workpiece library.

Responsibilities:

- capture a snapshot for matching
- choose a usable contour
- provide saved-workpiece candidates to the matcher
- return match metadata and matched raw payload

### `workpiece_preparation_service.py`

`PaintWorkpiecePreparationService` decides which preparation branch to take:

- use matched saved workpiece when available
- fall back to wrapping the captured contour as a minimal workpiece
- align DXF-based workpieces after image placement

Outputs:

- a raw workpiece payload compatible with path preparation
- a human-readable description string for the operator/process log

---

## `execute/`

`execute/` owns the transition from prepared execution plan to actual robot motion.

### `workpiece_path_executor.py`

`PaintWorkpiecePathExecutor` is the main orchestration class.

Responsibilities include:

- resolve pickup and paint base poses
- apply camera-to-TCP pickup compensation
- build pickup, approach, lift, plane-change, align, and staged poses
- project source paint paths into pivot motion
- run execution-plane-specific logic through strategy objects
- emit debug artifacts for executed paths

### `pivot_projection/`

Projection converts planar source paint geometry into robot poses around a pivot.

Public entry points:

- `project_paint_motion_geometry()`
- `rebase_projected_paint_path_to_zero_start_rz()`

Detailed operator/debug notes are in [../../../../pivot_painting_reference.md](../../../../pivot_painting_reference.md).

### `execution_plane/strategies.py`

This package removes scattered `if plane == ...` branching by giving each supported motion plane its own strategy.

Current strategies:

- `XyZRzExecutionPlaneStrategy`
- `XzYRyExecutionPlaneStrategy`

Owned behavior:

- pivot offset axis selection
- pickup alignment rotation handling
- XZ/RY preflight reachability checks
- execution-rotation direction flipping

### `paint_debug_artifacts.py`

This module owns debug dump/plot generation rather than leaving plotting code in the executor.

Key helpers:

- `write_pivot_debug_dump()`
- `write_pivot_debug_plot()`
- `build_executed_snapshot_series()`

---

## Motion Planes

The package currently supports two pivot motion planes:

| Plane | Active planar axes | Fixed axis | Active rotation |
|-------|--------------------|------------|-----------------|
| `xy_z_rz` | `X`, `Y` | `Z` | `RZ` |
| `xz_y_ry` | `X`, `Z` | `Y` | `RY` |

The axis/index mapping lives in `PaintProjectionRules` inside `config.py`.

---

## Key Integration Points Outside This Package

| External module | Why it matters |
|-----------------|----------------|
| `src/robot_systems/paint/application_wiring.py` | constructs all runtime paint services |
| `src/robot_systems/paint/domain/dxf_path_form_behavior.py` | uses align helpers during DXF import in the editor |
| `src/applications/workpiece_editor/service/workpiece_editor_service.py` | consumes paint editor/runtime helpers |
| `src/engine/robot/path_preparation/default_workpiece_path_preparation_service.py` | builds execution plans from prepared workpieces |

---

## Tests

Focused coverage for this package lives in:

- `test_paint_workpiece_alignment.py`
- `test_paint_matching_service.py`
- `test_paint_workpiece_preparation_service.py`
- `test_paint_pivot_projection.py`
- `test_paint_execution_plane_strategies.py`
- `test_paint_workpiece_path_executor.py`
- `test_paint_geometry_and_config.py`
- `test_paint_process_integration.py`

These tests are meant to keep the `align / plan / execute` package boundaries safe to refactor.
