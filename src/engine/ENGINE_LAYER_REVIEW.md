# Engine Layer Review

Date: 2026-05-05
Scope: `src/engine`

## Purpose

This note captures current layer violations and robot-system-specific knowledge found inside the engine layer, with suggested fixes.

The main review question was:

- does `src/engine` import or depend on `src/robot_systems/glue`, `paint`, or `welding` directly?
- does the engine layer contain robot-system-specific assumptions that should live above it?

## Summary

Most of `src/engine` is structurally clean. The strongest real violations are limited to:

1. the weight-cell stack
2. one interpolation/debug UI script under `engine/robot/path_interpolation`
3. a few glue-specific examples in engine comments/docstrings

The weight-cell stack is the most important issue because it affects engine interfaces and factories, not just examples or tools.

## Findings

### 1. Engine weight interfaces depend on glue settings types

Severity: High

Files:

- `src/engine/hardware/weight/interfaces/i_cell_calibrator.py`
- `src/engine/hardware/weight/interfaces/i_weight_cell_service.py`

Details:

- `ICellCalibrator` imports `CalibrationConfig` from `src.robot_systems.glue.settings.cells`
- `IWeightCellService` imports `CalibrationConfig` from `src.robot_systems.glue.settings.cells`

Why this is a violation:

- these are engine-layer abstractions
- engine interfaces must not depend on one specific robot system
- this creates the wrong dependency direction:

  `engine -> robot_systems.glue`

The engine already has its own generic weight config models in:

- `src/engine/hardware/weight/config.py`

That file already defines:

- `CalibrationConfig`
- `CellConfig`
- `CellsConfig`
- `CellsConfigSerializer`

So the glue import is not only wrong, it is also unnecessary.

Suggested fix:

- change both engine interfaces to import `CalibrationConfig` from `src.engine.hardware.weight.config`

Expected result:

- engine interfaces become robot-system-agnostic
- glue remains a consumer of engine weight abstractions, which is the correct direction

### 2. Engine HTTP weight-cell factory is glue-specific

Severity: High

File:

- `src/engine/hardware/weight/http/http_weight_cell_factory.py`

Details:

- the factory imports `CellConfig` and `GlueCellsConfig` from `src.robot_systems.glue.settings.cells`
- the function signature accepts `GlueCellsConfig`

Why this is a violation:

- this file lives in `src/engine`
- it should build a reusable engine service
- right now it is typed around glue-specific settings aliases instead of engine-native config types

This is especially inconsistent because `WeightCellService` itself already depends on engine-owned types:

- `src/engine/hardware/weight/weight_cell_service.py`

Suggested fix:

- update the factory to import `CellConfig` and `CellsConfig` from `src.engine.hardware.weight.config`
- change the function signature to accept `CellsConfig`
- keep glue-specific serializers and defaults inside `src/robot_systems/glue/settings/cells.py`

Expected result:

- the factory becomes reusable by glue, paint, welding, or future systems
- robot-system-specific defaults stay in the robot system layer

### 3. Engine interpolation/debug UI imports `GlueRobotSystem`

Severity: Medium

File:

- `src/engine/robot/path_interpolation/new_interpolation/simple_interpolation_pyqt6.py`

Details:

- the file imports `GlueRobotSystem`
- it reads:
  - `GlueRobotSystem.settings_specs`
  - `GlueRobotSystem.metadata.settings_root`
  - `GlueRobotSystem.work_areas`
- it also hard-codes default active area `"spray"`

Why this is a problem:

- even if this is only a debug or developer UI, it still lives under `src/engine`
- engine tools should not assume one robot system
- the file currently embeds glue-specific bootstrap knowledge into an engine package

Suggested fix options:

Option A:

- move this file out of `src/engine` into:
  - `src/robot_systems/glue/...`
  - or `scripts/`
  - or another dev-tools area

Option B:

- keep it in engine, but make it accept injected robot-system context:
  - settings specs
  - settings root
  - work-area definitions
  - default work area

Preferred option:

- move it out of `src/engine` if it is glue-specific by purpose
- only keep it in engine if it is redesigned as a truly generic tool

### 4. Glue-specific examples remain in engine comments/docstrings

Severity: Low

Files:

- `src/engine/robot/calibration/calibration_navigation_service.py`
- `src/engine/process/base_process.py`
- `src/engine/process/service_health_registry.py`

Details:

- `calibration_navigation_service.py` uses glue and `"spray"` as the example
- `base_process.py` mentions `GlueOperationCoordinator`
- `service_health_registry.py` mentions `GlueProcess`

Why this matters:

- these are not runtime dependency bugs
- but they reinforce glue as the implicit engine default
- that makes the engine layer look less generic than it actually is

Suggested fix:

- replace glue-specific names with generic examples:
  - `SomeProcessCoordinator`
  - `ExampleProcess`
  - `switch active work area before move`

Expected result:

- engine docs read as platform docs, not glue docs

## What did not look like a violation

These showed domain-specific language, but they appear to be shared platform concepts rather than robot-system leakage:

- `workpiece`
- `sprayPattern`
- contour matching
- path preparation
- generic vacuum pump interfaces

Those concepts are used by more than one system or sit at a reusable platform level, so they are not necessarily a layer problem by themselves.

Also:

- `Welding...` methods inside the Fairino driver look like vendor API surface, not repo-level welding-system knowledge

## Recommended Fix Order

### Phase 1: Real dependency violations

1. Fix `i_cell_calibrator.py`
2. Fix `i_weight_cell_service.py`
3. Fix `http_weight_cell_factory.py`

Goal:

- eliminate direct `src.robot_systems.glue...` imports from engine production abstractions

### Phase 2: Tooling placement

1. review whether `simple_interpolation_pyqt6.py` is meant to be generic
2. either move it out of engine or parameterize it properly

Goal:

- remove glue bootstrap assumptions from engine-owned tooling

### Phase 3: Documentation hygiene

1. replace glue-specific examples in engine docstrings/comments

Goal:

- make engine documentation system-neutral

## Concrete Refactor Targets

### Weight interfaces

Replace imports like:

```python
from src.robot_systems.glue.settings.cells import CalibrationConfig
```

with:

```python
from src.engine.hardware.weight.config import CalibrationConfig
```

### Weight-cell factory

Replace glue-bound types like:

```python
from src.robot_systems.glue.settings.cells import CellConfig, GlueCellsConfig
```

with engine-owned types:

```python
from src.engine.hardware.weight.config import CellConfig, CellsConfig
```

and update the function signature accordingly.

### Interpolation debug UI

If it stays generic, it should accept a context object or parameters instead of importing `GlueRobotSystem` directly.

Example direction:

- `settings_specs`
- `settings_root`
- `work_area_definitions`
- `default_active_area_id`

## Bottom Line

The engine layer is not broadly polluted by robot-system code, but it does contain a few concrete violations that should be cleaned up.

The most important issue is:

- engine weight abstractions currently depend on glue-only settings types

That should be fixed first.
