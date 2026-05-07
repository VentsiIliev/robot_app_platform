# Paint Trajectory Planning And Execution

This document explains how paint execution works after a workpiece has already been prepared.

Relevant code:

- `src/robot_systems/paint/processes/paint/config.py`
- `src/robot_systems/paint/processes/paint/execute/workpiece_path_executor.py`
- `src/robot_systems/paint/processes/paint/execute/pivot_projection/core.py`
- `src/robot_systems/paint/processes/paint/execute/execution_plane/strategies.py`
- `src/engine/robot/path_preparation/default_workpiece_path_preparation_service.py`

This document focuses on:

- what the different "plans" are
- how trajectory projection math works
- the exact execution order
- how `xy_z_rz` differs from `xz_y_ry`

---

## The Three Different Plans

There are three separate planning layers in the paint runtime.

### 1. Workpiece execution plan

Produced by:

- `DefaultWorkpiecePathPreparationService.build_execution_plan(...)`

This is the generic path-preparation result. It contains per-job source geometry such as:

- `execution_jobs`
- `execution_path`
- `pickup_xy`
- `pickup_rz`
- `workpiece_height_mm`
- per-job motion parameters like `vel` and `acc`

This plan is still expressed in the source process geometry, not yet in pivot-projected robot motion.

### 2. Pickup-to-pivot plan

Produced by:

- `PaintWorkpiecePathExecutor._build_pickup_and_stage_poses(...)`

This is a concrete robot-motion plan for the handoff phase before painting.

It contains:

- `pickup_approach_pose`
- `pickup_pose`
- `lift_pose`
- `align_pose`
- `change_plane_pose`
- optional `stage_transition_poses`
- `staged_pose`

This is a short sequence of robot poses, not a full paint trajectory.

### 3. Pivot execution path

Produced by:

- `project_paint_motion_geometry(...)`
- wrapped by `_build_pivot_execution_path(...)`

This is the final per-waypoint robot trajectory sent to `execute_trajectory(...)`.

This is the plan that translates the source path into pivot-based paint motion.

---

## End-To-End Runtime Order

`execute_pickup_and_paint()` runs in this order:

1. build pickup/staging poses
2. vacuum on
3. move to pickup approach
4. descend to pickup pose
5. lift
6. align rotation at pickup area
7. change plane
8. run any stage transitions
9. move to first pivot contact pose
10. execute each projected pivot paint path
11. return to align pose
12. restore original pickup orientation
13. vacuum off
14. unwind joint 6
15. run post-execute return callback, typically return-to-calibration

That ordering is important. The executor assumes pickup and paint are one continuous workflow, not two independent tools.

---

## High-Level Projection Idea

The pivot projection layer does not replay the source Cartesian path directly.

Instead, it interprets the source path as instructions for how a workpiece should move around a pivot:

- segment heading becomes a rotation demand
- segment length becomes translation along the configured paint axis
- the emitted robot pose is the centroid of the transformed shape

This is why the final robot XYZ trajectory can look very different from the original source path.

---

## Projection Math

The projection runs in the 2D active plane defined by `PaintSimulationConfig`.

### Step 1: Choose the active plane

For each mode, the config defines:

- which position axes are the active planar coordinates
- which position axis is orthogonal/fixed
- which orientation component is the active rotation component

The emitted 6D pose is reconstructed afterward with `_compose_pose()`.

### Step 2: Build the source 2D contour

The source execution path is converted into 2D points using:

- `source_planar_coordinate_indices`

This gives the geometry that will be pivot-projected.

### Step 3: Resolve pivot orientation references

The projector derives:

- `paint_axis_heading`
- `translation_heading`
- `contact_segment_heading`

Important distinction:

- `translation_axis` decides which axis the workpiece travels along
- `paint_side` decides on which side of the pivot normal the shape lies
- `translation_direction` decides forward vs reverse travel along the chosen axis

These are separate controls.

### Step 4: Canonicalize closed contours

For closed shapes, `_canonicalize_closed_source_path()`:

1. chooses the contour point closest to the physical pivot as the start point
2. selects loop direction to best match the requested projected travel direction

This avoids arbitrary start-point and winding behavior.

### Step 5: Initial contact alignment

The first source segment is rotated so it points along the desired contact heading.

Then the shape is translated so its first point sits exactly on the pivot location.

This establishes the initial staged contact pose.

### Step 6: Per-segment iterative projection

For each segment:

1. measure current segment heading
2. compute required rotation delta to match desired contact heading
3. optionally deadband tiny deltas
4. rotate the whole shape around the fixed pivot
5. translate the whole shape along the configured paint axis by the original segment length
6. emit the centroid of the transformed shape as the robot pose

Current rotation deadband:

- `0.5 deg`

That comes from `PAINT_PROJECTION_TUNING.rotation_deadband_deg`.

---

## Why Segment Length Becomes Linear Translation

This is the core modeling choice of the pivot planner.

The source path is treated as a 2D process path on the workpiece. During pivot painting, the robot is not tracing that exact path in free Cartesian space. Instead:

- the workpiece rotates around a pivot
- the whole workpiece translates along the configured axis
- source arc length is reinterpreted as translation distance

So:

- source heading affects rotation
- source segment length affects linear travel

This is why the resulting path is called a projection, not a direct replay.

---

## The Emitted Pose Is The Shape Centroid

The robot pose generated for each step is the centroid of the transformed projected shape, not the first contact point.

That matters because:

- the contact point is anchored at the pivot logic level
- the robot motion is commanded through the overall transformed workpiece center

This is a major reason the projected XYZ trajectory may appear longer or shifted compared with the original source path.

---

## Pickup-To-Pivot Planning

`_build_pickup_and_stage_poses()` builds the transition from pickup geometry into the first pivot pose.

### Inputs

From the first execution job it uses:

- `pickup_xy`
- `pickup_rz`
- `workpiece_height_mm`
- the first source `execution_path`

From the robot/runtime configuration it uses:

- pickup base pose
- paint base pose
- pickup tool/user
- pickup motion defaults
- pivot configuration

### Pickup Z

If no explicit pickup Z is configured, the executor derives it as:

`pickup_z = safety_z_min + workpiece_height_mm + pickup_contact_offset_mm`

With the current default contact offset:

- `2.0 mm`

Approach Z is then:

`pickup_approach_z = pickup_z + pickup_approach_offset_mm`

Current default approach offset:

- `100.0 mm`

### Pickup sequence poses

The plan builds:

- approach pose above pickup center
- contact pose at pickup center
- lift pose, currently same as approach pose
- align pose at lifted pickup position
- change-plane pose
- staged pose, which is the first projected pivot pose

The first projected pivot pose comes from `project_paint_motion_geometry(...)`.

So the pickup plan depends directly on the projection logic.

---

## Execution Plane Strategies

The executor no longer spreads plane checks through ad hoc `if` statements. It uses a strategy object from:

- `get_execution_plane_strategy(...)`

Current strategy classes:

- `XyZRzExecutionPlaneStrategy`
- `XzYRyExecutionPlaneStrategy`

These own the main behavioral differences between the two execution modes.

---

## `xy_z_rz` Vs `xz_y_ry`

This is the most important plane-specific section.

### Shared idea

Both modes:

- use the same projection algorithm
- use the same pickup/staging pipeline shape
- use the same execution API

What changes is the axis mapping and a small set of behavior rules.

### Axis mapping

| Property | `xy_z_rz` | `xz_y_ry` |
|----------|-----------|-----------|
| active planar axes | `X`, `Y` | `X`, `Z` |
| planar coordinate indices | `(0, 1)` | `(0, 2)` |
| source planar indices | `(0, 1)` | `(0, 1)` |
| orthogonal position index | `2` | `1` |
| active rotation index | `5` (`RZ`) | `4` (`RY`) |
| orientation overrides | none | `RX = 90 deg` |
| default paint side from `PaintProcessConfig` | `negative` | `positive` |
| default paint base group | `PAINTING` | `PAINTING_NEW` |
| pickup base group | `PAINTING` | `PAINTING` |

### Strategy-owned behavior

| Behavior | `xy_z_rz` | `xz_y_ry` |
|----------|-----------|-----------|
| pivot offset axis | `Y` index | `Z` index |
| rotation axis label | `RZ` | `RY` |
| reachability preflight | disabled | enabled-capable |
| rotation-direction flip support | no-op | supported |

### Align rotation behavior

For `xy_z_rz`:

- align rotation is taken directly from the first projected pivot pose `RZ`

For `xz_y_ry`:

- the executor computes a delta between projected `RY` and paint-base `RY`
- that delta is unwrapped against the paint pivot pose
- the delta is then applied on top of the pickup `RZ`

This looks odd at first glance, but the goal is practical:

- preserve a stable wrist branch during handoff
- avoid abrupt equivalent-angle jumps in the XZ/RY mode

### Why `xz_y_ry` has preflight validation

The XZ/RY mode is more branch-sensitive and more likely to produce poses that are mathematically valid but awkward for the robot to traverse.

So `_validate_xz_ry_pivot_path()` samples several waypoints across the projected path and calls `robot_service.validate_pose(...)` before execution.

This is intentionally limited to the XZ/RY strategy so the XY/RZ path stays unchanged.

### Why `xz_y_ry` can flip rotation direction

`maybe_flip_execution_rotation_direction()` mirrors each `RY` value around the start `RY`:

`new_ry = 2 * reference_ry - old_ry`

This is not generic kinematics math. It is a pragmatic branch-control tool for the XZ/RY process mode.

---

## Config Parameters That Matter Most

The main execution parameters live in `PaintProcessConfig` and `PaintSimulationConfig`.

### Process-level parameters

| Parameter | Meaning |
|-----------|---------|
| `pivot_motion_plane` | selects `xy_z_rz` vs `xz_y_ry` |
| `primary_group_id` | main pickup/paint base group |
| `secondary_group_id` | secondary paint base group |
| `pivot_translation_axis` | path travel axis inside the active plane |
| `pivot_translation_direction` | forward or reverse projected travel |
| `flip_xz_ry_execution_rotation_direction` | enables XZ/RY branch flip |
| `enable_xz_ry_preflight` | enables XZ/RY reachability sampling |
| `xz_ry_preflight_max_checks` | how many path samples to validate |
| `enable_vacuum_pump` | pickup vacuum enable |
| `apply_camera_to_tcp_for_pickup` | pickup compensation toggle |

### Pickup motion defaults

| Parameter | Default |
|-----------|---------|
| `default_z_mm` | `300.0` |
| `default_vel_percent` | `30.0` |
| `default_acc_percent` | `100.0` |
| `approach_offset_mm` | `100.0` |
| `contact_offset_mm` | `2.0` |

### Projection tuning

| Parameter | Default |
|-----------|---------|
| `smooth_max_linear_step_mm` | `1.0` |
| `smooth_max_angular_step_deg` | `0.2` |
| `rotation_deadband_deg` | `0.5` |

Only `rotation_deadband_deg` is currently used directly in the pivot projection code path.

---

## Debug Artifacts

During execution the executor writes:

- a text dump
- a plot

Through:

- `write_pivot_debug_dump()`
- `write_pivot_debug_plot()`

These are the first tools to inspect when:

- the shape is on the wrong side of the pivot
- the first contact orientation is wrong
- XZ/RY branch behavior is unstable
- projected centroid travel looks unintuitive

---

## Practical Mental Model

If you want one compact mental model of the executor:

1. the generic path-preparation layer creates process geometry
2. the pickup plan gets the part from the table to the pivot entry pose
3. the pivot projector converts source heading into rotation and source length into translation
4. the execution-plane strategy injects the plane-specific rules
5. the executor sends the projected path to the robot, then reverses the handoff flow enough to release safely

That is the actual planning and execution model used by the paint system today.
