# `src/robot_systems/paint/processes/` — Paint Processes Overview

The paint robot system currently owns two process paths:

| Process | Class | `ProcessID` | Purpose |
|--------|-------|-------------|---------|
| Main paint production | `PaintProcess` | `MAIN_PROCESS` | one-shot paint cycle |
| Robot calibration | `RobotCalibrationProcess` | `ROBOT_CALIBRATION` | shared calibration workflow |

The process package layout is:

```text
src/robot_systems/paint/processes/
├── robot_calibration_process.py
└── paint/
    ├── paint_process.py
    ├── paint_production_service.py
    ├── config.py
    ├── align/
    ├── plan/
    └── execute/
```

---

## `PaintProcess`

**File:** `src/robot_systems/paint/processes/paint/paint_process.py`

`PaintProcess` is a `BaseProcess` wrapper around one background paint-production run.

Responsibilities:

- start one daemon thread
- delegate the real work to `PaintProductionService.run_once()`
- translate success/failure into `STOPPED` or `ERROR`
- honor stop requests through a shared `_stopping` flag

Important behavior:

- it is not a looping production process
- it does not currently implement pause/resume semantics
- it is safe to reset after errors because `_on_reset_errors()` clears the stop flag

---

## `PaintProductionService`

**File:** `src/robot_systems/paint/processes/paint/paint_production_service.py`

`PaintProductionService` owns the actual one-cycle production flow:

1. capture snapshot
2. pick the largest usable contour
3. prepare a workpiece payload
4. build the execution plan
5. execute pickup and paint

It is intentionally UI-free. The workpiece editor uses the same lower-level services, but the production service owns the background-process version of that flow.

---

## Configuration

**File:** `src/robot_systems/paint/processes/paint/config.py`

`PAINT_PROCESS_CONFIG` is the single source of truth for platform-side paint-process behavior.

Main config areas:

- execution target point selection
- DXF alignment strategy
- pivot motion plane
- paint/pickup base group selection
- pivot translation axis and direction
- XZ/RY behavior toggles
- pickup motion defaults

Supporting typed config objects:

- `PickupMotionConfig`
- `PaintProjectionTuning`
- `PaintMotionPlaneSpec`
- `PaintProjectionRules`
- `PaintSimulationConfig`

---

## Paint Process Package

The paint production package is documented separately in:

- [paint/README.md](paint/README.md)

That document covers the `align / plan / execute` split in detail.

---

## Calibration Process

**File:** `src/robot_systems/paint/processes/robot_calibration_process.py`

The calibration process is shared-engine-oriented rather than paint-production-specific. The paint system wraps it with `PaintCalibrationCoordinator` so calibration can be launched from the paint shell using paint observer/navigation context.

---

## Test Coverage

Primary process-level coverage:

- `tests/robot_systems/paint/test_paint_process_integration.py`
- `tests/robot_systems/paint/test_paint_system_integration.py`
- `tests/robot_systems/paint/test_paint_workpiece_path_executor.py`

Those tests are the first place to update when changing process orchestration or composition.
