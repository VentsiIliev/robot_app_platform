# Paint Process Refactor Review

## Scope

This document reviews the current state of the paint-process implementation under:

- `src/robot_systems/paint/processes/paint/`
- `src/robot_systems/paint/domain/`
- `src/engine/robot/path_preparation/`

It also reviews the previously proposed cleanup plan and identifies gaps, risks, and a stronger staged refactor path.

No code changes are proposed here. This is a planning and review document only.

## Current State Review

### 1. The main complexity center is still `workpiece_path_executor.py`

`src/robot_systems/paint/processes/paint/workpiece_path_executor.py` currently combines all of these responsibilities:

- runtime config refresh
- base pose resolution
- plane-specific pivot offset application
- preview path generation
- preview motion snapshot generation
- pivot trajectory execution path construction
- pickup/stage pose planning
- pickup robot move sequencing
- pivot path preflight validation
- debug dump writing
- debug plot writing
- executed snapshot reconstruction for plotting
- post-run return and release flow

This is the core maintainability problem. The file is not just large. It contains several behavior layers that change at different rates and should not be edited together.

### 2. Plane behavior is distributed, not centralized

Plane-specific semantics are currently split across:

- `config.py`
- `pivot_projection.py`
- `workpiece_path_executor.py`
- path-preparation assumptions

Examples:

- `rotation_index`
- `planar_coordinate_indices`
- `orthogonal_position_index`
- `orientation_overrides_deg`
- pickup alignment behavior
- pivot offset axis
- `flip_xz_ry_execution_rotation_direction`

This means that `xz_y_ry` behavior is not controlled from one source of truth. The configuration object carries only part of the semantics; the rest is encoded in executor branches.

### 3. The data model is weak at the process boundaries

The execution pipeline still relies heavily on loosely structured dicts:

- `execution_plan.workpiece`
- `execution_plan.execution_jobs`
- per-job keys like:
  - `pivot_offset_mm`
  - `pickup_xy`
  - `pickup_rz`
  - `workpiece_height_mm`
  - `pattern_type`
  - `execution_target_offset_x`

This makes behavior hard to reason about because important process state has no explicit type boundary. New fields can be added in one place and forgotten in another.

### 4. Editor and execution concerns are leaking into each other

The new pivot offset is a good example of the current architecture problem:

- it starts in editor-facing settings
- gets preserved by the paint adapter
- gets read by path preparation
- gets copied into each execution job
- gets re-read in the executor
- gets applied at preview, staging, and execution time

This works, but the ownership is unclear. The offset is a process-level concept, yet it is being threaded through multiple generic layers as plain settings data.

### 5. Preview and execution are closer than before, but still not one unified pipeline

The code now applies the pivot offset in:

- `get_pivot_preview_paths(...)`
- `get_pivot_motion_preview(...)`
- `_build_pickup_and_stage_poses(...)`
- `_build_pivot_execution_path(...)`
- `_execute_pivot_paths(...)`
- `execute_preview_paths(...)`

This is an improvement in correctness, but it also shows the duplication problem clearly. The same semantic adjustment is applied in several call sites instead of being part of one reusable resolved execution context.

### 6. Pickup sequencing and projection logic are still tightly coupled

Recent changes changed the move order to:

- pickup
- lift
- align
- change plane
- move to staged pose
- execute pivot trajectory

That order directly affects how:

- `align_pose`
- `change_plane_pose`
- `staged_pose`

must be constructed.

Right now that coupling is implicit inside `_build_pickup_and_stage_poses(...)`. This is risky because changing robot sequencing requires changing the pose-construction math in the same method.

### 7. There are signs of stale state and unfinished cleanup

`_pending_stage_pose` is still present on the executor object even though the current flow no longer defers staged pose insertion into pivot execution in the same way.

That is a concrete sign that the code is evolving by patching rather than by re-establishing a clear model after each change.

### 8. Debugging features are valuable but too embedded in the executor

The debug plotting work is useful and now closer to real execution. But the plot generation logic still sits inside the execution class and depends on internal executor details.

This creates two risks:

- plotting changes can accidentally affect execution behavior
- execution refactors become harder because debug behavior is mixed into orchestration

### 9. Geometry assumptions are not yet isolated from controller-side execution choices

`pivot_projection.py` defines the projection model:

- whole-shape rotation around the pivot
- discrete per-segment rotation
- discrete per-segment translation
- centroid-based emitted pose

But execution-time behaviors still live outside that model:

- staged entry pose handling
- alignment ordering
- optional execution-time `RY` flip
- preview/debug reconstruction from final executed path

This is functional, but the system lacks an explicit distinction between:

- projection model
- entry/exit sequencing policy
- execution path mutation policy
- visualization policy

## Review Of The Earlier Proposed Refactor Plan

The earlier plan was directionally correct. It identified the real issue: too many responsibilities in the executor and scattered plane-specific logic.

The strongest points in the earlier plan were:

- add characterization tests first
- split `workpiece_path_executor.py` by responsibility
- centralize plane-specific behavior
- separate geometry from sequencing
- use explicit data models
- unify preview and execution

Those should stay.

However, the plan had several gaps.

## Gaps And Risks In The Earlier Plan

### Gap 1. It did not explicitly cover editor-to-process data ownership

The plan mentioned typed structures, but it did not clearly address the boundary between:

- workpiece editor settings
- persisted workpiece raw data
- path-preparation settings
- process-execution inputs

This matters because the current system already has leakage here, and new parameters like pivot offset will keep making that worse unless the ownership model is cleaned up deliberately.

The plan should explicitly include:

- a typed paint-process settings object
- a defined mapping from editor data into process settings
- a clear decision about which settings are:
  - workpiece-level
  - segment-level
  - execution-only

### Gap 2. It did not include a migration path for `execution_jobs`

The current pipeline depends heavily on `execution_jobs` dicts produced by `DefaultWorkpiecePathPreparationService`.

If these dicts are replaced too early, the refactor will become large and risky. The plan needs an explicit migration strategy:

1. introduce typed wrapper objects around the existing dict structure
2. adapt read sites to use wrappers
3. only then change the producer

Without this stepwise migration, the refactor may become invasive across unrelated code.

### Gap 3. It did not explicitly treat `pivot_projection.py` as a stable math kernel

The plan talked about splitting geometry and sequencing, but it should say more clearly:

- `pivot_projection.py` should become a stable projection kernel
- executor policies should be layered on top of it
- plotting should consume its outputs, not redefine its semantics

This is important because otherwise refactoring may accidentally turn projection math into a place where orchestration concerns are reintroduced.

### Gap 4. It did not include a dedicated “resolved context” object

Right now many repeated lookups occur:

- base pivot pose
- pickup base pose
- pivot offset
- motion plane
- alignment conventions
- execution flip policy
- robot-config-dependent settings

The plan should introduce an explicit runtime object, for example:

- `PaintProcessRuntimeContext`

Possible fields:

- normalized pivot config
- pickup config
- resolved pickup base pose
- resolved paint base pose
- resolved pivot pose after offset
- active plane rules
- runtime flags

This would remove repeated recomputation and make preview, staging, and execution consume the same resolved context.

### Gap 5. It did not explicitly address stale fields and dead branches

A cleanup plan should include a dedicated dead-state removal pass after behavior is frozen:

- remove unused executor fields
- remove stale sequencing mechanisms
- remove duplicated preview/execution branches where one has replaced the other
- collapse obsolete compatibility logic only after tests exist

Without this, the code may be better structured but still carry misleading state.

### Gap 6. It did not include observability/logging cleanup

The current logs are detailed but semantically inconsistent. A refactor should include:

- standard event names
- consistent pose labels
- explicit frame naming
- clear distinction between preview geometry, staged entry, and executed path

This is not cosmetic. In this codebase, logs are part of the debugging workflow.

### Gap 7. It did not explicitly protect adapter/schema/preparation boundaries

The paint process is not only the executor. The workpiece-editor adapter and path-preparation service are part of the process behavior now.

The plan must explicitly cover:

- `paint_workpiece_editor_adapter.py`
- `contour_editor_schema.py`
- `default_workpiece_path_preparation_service.py`

Otherwise the executor could be cleaned up while the upstream settings flow remains ambiguous and brittle.

## Revised Cleanup Strategy

The revised plan below keeps the good direction of the earlier plan but closes the gaps.

### Phase 1. Freeze behavior with characterization tests

Before changing structure, add tests that lock in current behavior for:

- `xy_z_rz` preview path generation
- `xz_y_ry` preview path generation
- offset application to pivot pose
- staged pose computation
- pickup move ordering
- alignment-before-plane-change behavior
- execution-time `RY` flip
- preview/debug path agreement against final executed path construction

Also add small data-flow tests for:

- adapter round-trip of `offset`
- schema defaults
- execution job metadata containing `pivot_offset_mm`

### Phase 2. Introduce explicit process data objects without changing behavior

Add typed wrappers first, while keeping existing dict producers.

Suggested objects:

- `PaintProcessSettings`
- `PaintExecutionJob`
- `ResolvedPivotPose`
- `PickupStagePlan`
- `PaintProcessRuntimeContext`

This phase should not change behavior. It should only replace direct dict indexing in downstream consumers.

### Phase 3. Centralize plane rules

Create one module that defines plane-dependent semantics beyond raw indices.

It should answer:

- which pose indices define the plane
- which axis receives pivot offset
- which rotation component is active in projection
- which rotation component is used before plane change
- whether orientation overrides apply
- whether execution-time rotation flip is allowed or needed

This should eliminate most `if self._uses_xz_ry_pivot_mode()` branching from the executor.

### Phase 4. Extract pivot pose resolution

Create a dedicated resolver that owns:

- base pose lookup
- pickup base pose lookup
- workpiece/editor pivot offset application
- plane-aware axis selection for the offset

Every consumer should receive a resolved pivot pose from this component rather than applying offset locally.

### Phase 5. Extract pickup/stage planning from robot move sequencing

Split:

- pose computation
- robot movement execution

into separate components.

Suggested split:

- `pickup_stage_planner.py`
- `pickup_stage_executor.py`

The planner should build:

- pickup approach
- pickup
- lift
- align
- change plane
- staged pose

The executor should only run those steps in the configured order.

### Phase 6. Extract pivot execution path building

Create a dedicated service that owns:

- coarse pivot path build
- optional execution-time path mutation
- optional zero-start rotation normalization
- optional plane-specific rotation flip

This makes it easier to align preview, execution, and debug artifacts around one path-construction pipeline.

### Phase 7. Extract debug artifact generation

Create a dedicated debug service for:

- text dump generation
- plot generation
- executed snapshot reconstruction

Inputs should be plain data objects, not executor internals.

This step should reduce the risk of future debugging improvements destabilizing execution logic.

### Phase 8. Clean up upstream settings flow

After downstream consumers use typed process settings, simplify the editor and preparation flow:

- define which settings are workpiece-level
- define which settings are segment-level
- remove accidental leakage of process-only semantics through generic settings bags where possible

This is where the pivot offset should become a first-class paint-process setting rather than “just another stringly field.”

### Phase 9. Remove stale state and flatten branches

Only after tests and extracted modules are in place:

- remove stale executor fields
- remove no-longer-used state handoff patterns
- remove duplicated preview/execution branches
- reduce executor to orchestration only

### Phase 10. Standardize terminology and logging

Normalize naming across code and logs for:

- base pivot pose
- resolved pivot pose
- staged pose
- first execution pose
- first boundary contact candidate
- pickup-frame alignment
- pivot-plane execution

This phase should include doc updates because terminology is a real part of maintainability here.

## Recommended File Targets

Likely extraction targets:

- `src/robot_systems/paint/processes/paint/paint_plane_rules.py`
- `src/robot_systems/paint/processes/paint/pivot_pose_resolver.py`
- `src/robot_systems/paint/processes/paint/pickup_stage_planner.py`
- `src/robot_systems/paint/processes/paint/pickup_stage_executor.py`
- `src/robot_systems/paint/processes/paint/pivot_path_builder.py`
- `src/robot_systems/paint/processes/paint/pivot_debug_service.py`
- `src/robot_systems/paint/processes/paint/models/` for typed runtime objects

The existing `workpiece_path_executor.py` should remain as the orchestration facade until the end of the migration.

## Refactor Risks To Watch

### 1. Silent behavior drift in `xz_y_ry`

This mode already depends on both config and executor-side behavior. It must be protected by explicit tests before extraction.

### 2. Over-eager replacement of dict-based jobs

Replacing the execution job format in one large step would be risky. Wrap first, replace later.

### 3. Mixing preview correctness with plot correctness

Plots should reflect final execution artifacts, but plotting logic should not become the source of execution truth.

### 4. Collapsing editor and process settings too early

The editor is generic. The paint process is not. The refactor should preserve that separation.

### 5. Refactoring around logs without stabilizing names

If logs are important for robot debugging, naming cleanup should be deliberate and staged, not incidental.

## Final Recommendation

The earlier plan was good at the structural level, but it needs three concrete additions to be safe and complete:

1. a dedicated editor-to-process settings cleanup track
2. a typed runtime/execution context introduced before module extraction
3. an explicit migration strategy for the `execution_jobs` dict boundary

If those are added, the cleanup can preserve behavior while making the paint process much easier to reason about and much safer to extend.

## Execution Checklist

This section converts the revised refactor strategy into a practical rollout checklist.

### Phase 0. Preparation

Tasks:

- list every touched module in the paint-process execution path
- identify the current public entry points that must keep working
- capture a few representative real workpieces for regression testing
- capture current debug plots and dumps for those representative workpieces

Files to inspect:

- `src/robot_systems/paint/processes/paint/workpiece_path_executor.py`
- `src/robot_systems/paint/processes/paint/pivot_projection.py`
- `src/robot_systems/paint/processes/paint/config.py`
- `src/engine/robot/path_preparation/default_workpiece_path_preparation_service.py`
- `src/robot_systems/paint/domain/paint_workpiece_editor_adapter.py`
- `src/robot_systems/paint/domain/contour_editor_schema.py`

Deliverables:

- one inventory list of responsibilities by file
- one list of public behaviors that must not change
- one set of saved representative inputs and expected outputs

Exit criteria:

- the team agrees on what is behavior and what is implementation detail
- at least two representative workpieces exist for manual and automated regression

### Phase 1. Characterization Tests

Tasks:

- add tests around pivot preview path generation
- add tests around pivot motion preview snapshot count and shape
- add tests around staged pose generation
- add tests around pickup sequencing assumptions
- add tests around offset application on `Y` vs `Z`
- add tests around `flip_xz_ry_execution_rotation_direction`
- add tests around editor adapter round-trip for `offset`
- add tests around execution-job metadata carrying `pivot_offset_mm`

Suggested test groups:

- `tests/robot_systems/paint/test_paint_workpiece_editor_adapter.py`
- `tests/robot_systems/paint/test_paint_contour_editor_schema.py`
- `tests/engine/robot/test_default_workpiece_path_preparation_service_paint.py`
- `tests/robot_systems/paint/test_paint_pivot_projection.py`
- `tests/robot_systems/paint/test_paint_workpiece_path_executor.py`

Concrete test cases:

- `xy_z_rz` preview uses base pivot pose with no offset
- `xy_z_rz` preview with `offset=12.5` shifts pivot on `Y`
- `xz_y_ry` preview with `offset=12.5` shifts pivot on `Z`
- staged pose changes when pivot offset changes
- align-before-change-plane ordering preserves expected pre-plane-change orientation
- `flip_xz_ry_execution_rotation_direction=True` mirrors `RY` around the first pivot waypoint only
- preview/debug path builder uses the same offset as execution path builder

Exit criteria:

- the existing behavior is reproducible in tests
- recent fixes around offset, staging, and plot alignment are covered

### Phase 2. Typed Wrappers Without Producer Changes

Tasks:

- introduce a typed wrapper for `execution_jobs` without changing the existing producer format
- introduce a typed wrapper for workpiece-level paint settings
- replace direct string-key access in the executor with typed accessors

Suggested objects:

- `PaintProcessSettings`
- `PaintExecutionJobView`
- `PaintPreviewArtifacts`
- `PaintProcessRuntimeContext`

Rules:

- do not change raw persisted data format in this phase
- do not change `DefaultWorkpiecePathPreparationService` output shape yet

Exit criteria:

- executor code stops indexing ad hoc strings for most paint-specific fields
- tests still pass unchanged

### Phase 3. Centralize Plane Rules

Tasks:

- create one plane-rules module
- move nontrivial plane behavior out of executor branches
- define explicit rules for:
  - pivot offset axis
  - projection rotation index
  - pre-plane-change alignment axis
  - orientation overrides
  - optional execution-time rotation flip

Suggested file:

- `src/robot_systems/paint/processes/paint/paint_plane_rules.py`

Exit criteria:

- executor no longer contains multiple scattered plane-specific conditional blocks
- plane semantics are discoverable from one file

### Phase 4. Extract Pivot Pose Resolution

Tasks:

- extract base pose lookup
- extract pickup base pose lookup
- extract pivot offset application
- make preview, staging, and execution consume the same resolved pivot pose API

Suggested file:

- `src/robot_systems/paint/processes/paint/pivot_pose_resolver.py`

Required tests:

- resolved pivot pose is identical across preview and execution for the same job
- changing offset changes only the plane-specific target axis

Exit criteria:

- `_apply_pivot_offset(...)` and related resolution logic are no longer embedded in the executor

### Phase 5. Separate Pickup/Stage Planning From Move Execution

Tasks:

- move pose construction into a planner
- move robot movement sequencing into a small executor/runner
- keep the sequence explicit and configurable in one place

Suggested files:

- `pickup_stage_planner.py`
- `pickup_stage_executor.py`

Key behaviors to preserve:

- align-before-change-plane ordering
- current staged-pose entry semantics
- release/dropoff return path

Test targets:

- planner returns the same `pickup_approach_pose`, `align_pose`, `change_plane_pose`, and `staged_pose` as before
- execution runner calls moves in the expected order

Exit criteria:

- pose math and move ordering can be edited independently

### Phase 6. Extract Pivot Path Builder

Tasks:

- move coarse projected path build into a dedicated service
- move optional path mutations into that same service
- ensure preview and execute both request path artifacts from the same builder

Suggested file:

- `pivot_path_builder.py`

Responsibilities:

- build projected pivot path
- optionally normalize start rotation
- optionally apply execution-time rotation flip
- return both path and diagnostics

Test targets:

- path builder returns the same paths as the old executor flow
- execution-time flip remains behaviorally identical

Exit criteria:

- executor stops owning path-construction details

### Phase 7. Extract Debug Artifact Generation

Tasks:

- move text dump writing out of the executor
- move plot writing out of the executor
- move executed snapshot reconstruction out of the executor

Suggested file:

- `pivot_debug_service.py`

Test targets:

- debug service receives final executed path artifacts
- debug plots still mark:
  - pivot
  - executed TCP/centroid
  - nearest contour point to pivot

Exit criteria:

- modifying debug plots no longer requires editing execution orchestration

### Phase 8. Clean Up Editor And Preparation Boundaries

Tasks:

- define which paint settings are workpiece-level
- define which paint settings are segment-level
- decide whether `offset` remains a generic setting key or becomes a paint-owned concept with explicit mapping
- reduce plain settings leakage into process code

Files to revisit:

- `paint_workpiece_editor_adapter.py`
- `contour_editor_schema.py`
- `default_workpiece_path_preparation_service.py`

Questions to settle:

- should pivot offset be stored on the workpiece root, on the main contour settings, or in a dedicated paint settings object
- which layer owns validation of paint-only settings

Exit criteria:

- there is a clear contract from editor data to process settings
- new paint-specific parameters can be added without threading them through generic dicts by hand

### Phase 9. Remove Stale State And Flatten Branches

Tasks:

- remove stale executor fields
- remove dead compatibility branches
- simplify code paths now covered by extracted collaborators

Known candidates to evaluate:

- `_pending_stage_pose`
- duplicated preview/execution offset application sites
- executor-side repeated pivot pose resolution

Exit criteria:

- executor state contains only orchestration-level fields
- obsolete state handoff logic is gone

### Phase 10. Logging, Naming, And Docs

Tasks:

- normalize naming across logs and helpers
- update robot/process docs after code structure stabilizes
- add one short architecture note for the paint process

Naming to standardize:

- base pivot pose
- resolved pivot pose
- staged pose
- first execution pose
- first boundary contact candidate
- pickup-frame alignment
- pivot-plane execution

Docs to consider:

- `docs/robot_systems/`
- any paint-specific process notes already used operationally

Exit criteria:

- logs are easier to read during live debugging
- docs reflect the new module boundaries and data flow

## Suggested Work Breakdown

### Small, low-risk PRs

- add tests only
- add typed wrappers only
- add plane-rules module only
- add pivot-pose resolver only

### Medium-risk PRs

- extract pickup/stage planner
- extract pivot path builder
- extract debug service

### Higher-risk PRs

- change upstream editor-to-process settings ownership
- replace execution-job dict producer format
- remove stale branches after migration

## PR Review Checklist

For each refactor PR, reviewers should verify:

- behavior is covered by a test added in the same or earlier PR
- no public entry point changed unintentionally
- preview and execution still use the same resolved pivot semantics
- `xz_y_ry` and `xy_z_rz` both still have explicit coverage
- any moved plane logic is removed from the old location
- logging remains sufficient for robot-side debugging

## Minimum Test Matrix

At minimum, keep this matrix green through the refactor:

- `xy_z_rz`, no offset
- `xy_z_rz`, positive offset
- `xz_y_ry`, no offset
- `xz_y_ry`, positive offset
- `xz_y_ry`, rotation flip enabled
- workpiece-layer execution source
- spray-pattern execution source
- DXF-backed path
- contour-backed path

## Final Success Criteria

The refactor is complete when:

- `workpiece_path_executor.py` is mostly orchestration
- plane semantics come from one authoritative place
- preview and execution consume one resolved runtime context
- editor/process settings boundaries are explicit
- new paint-process parameters can be added with predictable touch points
- robot/plot mismatches are easier to diagnose because logs, debug artifacts, and runtime data flow align
