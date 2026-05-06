# Paint Process Cleanup Plan

## Scope

Target package:

- `src/robot_systems/paint/processes/paint/`

Primary goals:

- reduce file/class size
- separate geometry from orchestration
- remove duplicated contour/point utilities
- make pickup/alignment logic easier to test
- reuse existing shared helpers where they already exist

## Current Problems

### 1. Responsibilities are too concentrated

The main complexity is in two files:

- `workpiece_path_executor.py` (`~1530` lines)
- `workpiece_alignment.py` (`~1026` lines)

These files currently mix several concerns:

- data normalization
- contour math
- robot pose planning
- execution sequencing
- debug logging / dump writing / plotting
- payload mutation

That makes changes risky and pushes unrelated logic into the same module.

### 2. Contour utilities are duplicated

There are multiple local helpers that normalize, inspect, or reshape contours:

- `workpiece_alignment.py`
  - `_normalize_contour_points`
  - `_extract_raw_contour_points`
  - `_replace_raw_contour_payload`
  - `_describe_contour`
- `workpiece_preparation_service.py`
  - `contour_to_workpiece_raw`
  - `_extract_points_for_log`
  - `_describe_contour`
- `workpiece_matching_service.py`
  - `pick_largest_contour`

These should not be scattered across orchestration services.

### 3. Pickup geometry is not clearly owned

There is already a local helper in `pickup_planner.py`:

- `_camera_to_tcp_delta(...)`

It uses the shared engine helper:

- `src/engine/geometry/planar.py`

But pickup-related pose assembly still lives in `workpiece_path_executor.py`, so the package has both:

- a small reusable pickup helper
- a large executor with embedded pickup math

This is a sign that the package boundary is correct, but the logic is in the wrong place.

### 4. Alignment code is too monolithic

`workpiece_alignment.py` currently contains:

- raw payload extraction
- contour resampling
- scale estimation
- transform math
- nearest-neighbor search
- ICP-style pose refinement
- mask-overlap refinement
- payload rewrite logic

That is too much to evolve safely in one module.

### 5. Matching adapter logic is too local and anonymous

`workpiece_matching_service.py` defines `_MatchableWorkpiece` inside `_load_candidates()`.

That makes the matcher harder to test and harder to reuse. It also hides a real domain adapter inside an implementation detail.

## Existing Reuse Opportunities

### Shared helpers that should be reused now

#### `src/engine/geometry/planar.py`

Already useful and appropriate for this package:

- `rotate_xy`
- `rotate_xy_about`
- `normalize_degrees`
- `unwrap_degrees`

Recommendation:

- use this as the default home for small point-rotation / angle-wrapping logic
- do not duplicate angle/point rotation code inside paint modules

#### `pickup_planner.py`

This should become the canonical home for pickup-specific geometry such as:

- camera-to-TCP offset application
- pickup pose assembly
- pickup-to-stage / pickup-to-pivot plan building

Recommendation:

- expand it into a real pickup planning module
- move pickup math out of `workpiece_path_executor.py`

### Shared helper that can be reused selectively

#### `src/engine/vision/implementation/VisionSystem/core/models/contour.py`

`Contour` already provides:

- normalization to `(N, 2)`
- `translate`
- `rotate`
- `scale`
- centroid / bbox / area helpers

This is useful for simple contour operations and for boundary conversion.

Recommendation:

- reuse `Contour` for simple transform-heavy helpers and contour inspection
- do not force the whole alignment pipeline to depend on it immediately

Why not use it everywhere right away:

- current alignment code works heavily with dense `numpy` arrays
- some routines expect direct array math, KD-tree usage, and payload rewriting
- `Contour` is mutable, which is convenient in some places but can make optimization/refinement flows less explicit

Practical rule:

- use `Contour` at module boundaries and for basic transforms
- keep advanced alignment internals array-based unless there is a clear payoff from converting them

## Recommended Target Structure

Keep the package under `paint/processes/paint/`, but split by responsibility.

### Process orchestration

- `paint_process.py`
  - process lifecycle only
- `paint_production_service.py`
  - capture -> prepare -> plan -> execute flow only

No contour math or payload mutation should live here.

### Workpiece preparation and matching

- `workpiece_preparation_service.py`
  - choose matched-vs-captured workpiece
  - orchestrate DXF placement + alignment
- `workpiece_matching_service.py`
  - matching orchestration only
- `matchable_workpiece.py`
  - extracted adapter currently hidden inside `_load_candidates()`

### Shared paint contour utilities

Add a small local utility module, for example:

- `contour_utils.py`

Move these kinds of helpers there:

- normalize arbitrary contour payloads to `np.ndarray`
- convert `np.ndarray` -> raw workpiece contour payload
- contour logging/summary helpers
- `pick_largest_contour`

This module should be pure geometry/data-shape code with no robot dependencies.

### Alignment package split

Split `workpiece_alignment.py` into smaller modules, for example:

- `alignment_io.py`
  - raw contour extraction / payload replacement
- `alignment_sampling.py`
  - resampling, smoothing, path length, polygon area
- `alignment_transform.py`
  - rotation matrices, scaling, point transforms
- `alignment_search.py`
  - KD-tree helpers, nearest-neighbor matching, trimmed matches
- `alignment_refinement.py`
  - ICP and mask-overlap refinement
- `workpiece_alignment.py`
  - public orchestration entry point only

This allows refactoring without changing external callers first.

### Execution split

Split `workpiece_path_executor.py` into smaller units, for example:

- `pickup_planner.py`
  - pickup pose planning and camera-to-TCP compensation
- `pivot_projection.py`
  - keep as geometry-focused module
- `path_motion_executor.py`
  - robot trajectory execution only
- `paint_debug_artifacts.py`
  - debug dump/plot generation only
- `workpiece_path_executor.py`
  - high-level coordination only

The executor should own sequencing, not every helper detail.

## Refactor Order

### Phase 1. Extract shared contour helpers

Low-risk first step:

- create `contour_utils.py`
- move:
  - `_normalize_contour_points`
  - raw contour extraction helpers
  - `_describe_contour`
  - `contour_to_workpiece_raw`
  - `pick_largest_contour`
- update imports without changing behavior

Expected outcome:

- immediate duplication reduction
- cleaner preparation/matching/alignment modules

### Phase 2. Make pickup planning real

- move pickup offset and pickup pose math from `workpiece_path_executor.py` into `pickup_planner.py`
- make `pickup_planner.py` expose explicit functions or a small planner class
- wire executor to consume the resulting plan object

Expected outcome:

- pickup logic becomes testable without robot execution
- easier to verify camera-to-TCP handling

### Phase 3. Split alignment internals

- keep `align_raw_workpiece_to_contour(...)` as the public entry point
- move private helper groups into focused modules
- preserve behavior before attempting algorithm changes

Expected outcome:

- lower cognitive load
- easier tuning of one alignment stage at a time

### Phase 4. Shrink executor to orchestration

- move debug dump/plot code out
- move path/pose helper logic out
- keep only:
  - precondition checks
  - call ordering
  - progress/error reporting
  - collaboration with robot/vacuum services

Expected outcome:

- executor becomes readable
- robot-side failures are easier to isolate from geometry-side failures

### Phase 5. Extract matcher adapter

- lift `_MatchableWorkpiece` into its own module/class
- make matching service depend on that adapter explicitly

Expected outcome:

- better unit-test surface
- less hidden structure inside method bodies

## What Not To Do First

- do not move everything into `src/engine/` immediately
- do not rewrite the alignment algorithm while also splitting files
- do not convert all payloads to `Contour` in one pass

Reason:

- structural cleanup should happen before algorithm replacement
- otherwise the change set becomes too wide to verify

## Suggested Utility Decisions

### Use engine planar helpers

Yes. This is already the right shared layer for:

- point rotation
- pivot rotation
- angle normalization/unwrapping

### Reuse `Contour`

Yes, but selectively.

Good uses:

- local transform helpers
- bbox/centroid/area inspection
- converting untrusted contour inputs into a normalized shape

Avoid as an immediate full replacement for:

- KD-tree alignment internals
- high-frequency numeric refinement loops
- raw payload mutation/orchestration logic

### Keep a local paint contour utility module

Yes.

Even with `Contour` available, the paint package still needs local helpers for:

- raw workpiece payload shape
- spray-pattern-specific contour arrays
- logging/diagnostics formatting

Those are paint-domain concerns, not engine-generic concerns.

## Verification Plan

After each phase, add or update targeted tests.

Priority tests:

1. `contour_utils`
   - normalize mixed contour input shapes
   - convert to/from raw payload
   - largest contour selection

2. `pickup_planner`
   - camera-to-TCP offset application
   - rotation behavior at several angles
   - pickup/stage pose generation

3. `workpiece_alignment`
   - align a saved contour to a translated/rotated/scaled capture
   - verify scale clamping behavior
   - verify no-crash behavior on degenerate contours

4. `workpiece_preparation_service`
   - matched contour branch
   - DXF branch
   - fallback-to-captured branch

5. `workpiece_path_executor`
   - orchestration flow with mocked robot/vacuum services
   - cancellation and error propagation

## Recommended First Implementation Slice

If the goal is the safest first cleanup, do this first:

1. add `contour_utils.py`
2. move contour normalization/logging/payload helpers into it
3. update `workpiece_preparation_service.py`, `workpiece_matching_service.py`, and `workpiece_alignment.py` to use it
4. expand `pickup_planner.py` and move camera-to-TCP / pickup pose assembly there

That will simplify the package materially without changing the higher-level behavior.
