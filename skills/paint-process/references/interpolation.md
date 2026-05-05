# Interpolation And Densification

## Purpose

This reference covers how waypoint interpolation currently behaves for the paint process, and what to inspect when motion looks too coarse or “jumps” between rotations.

## Current Pivot Projection Behavior

In `project_paint_motion_geometry(...)`:

- one source segment becomes one projected execution step
- one rotation delta is applied per source segment
- one translation step is applied per source segment
- one output pose is emitted per source segment

That means there is no automatic interpolation of intermediate poses during rotation in the pivot projection itself.

Practical consequence:
- if a source path has sparse points, the pivot path will also be sparse
- large heading changes become large discrete orientation jumps
- visual mismatch can be exaggerated because the real robot controller may smooth internally, while the debug plot shows only the explicit waypoints

## Existing Constants

In `config.py`:

- `_PAINT_SMOOTH_MAX_LINEAR_STEP_MM = 1.0`
- `_PAINT_SMOOTH_MAX_ANGULAR_STEP_DEG = 0.2`
- `_PAINT_ROTATION_DEADBAND_DEG = 0.5`

Today:
- the deadband is active
- the smoothing/densification constants are mostly guidance or future intent unless a caller explicitly uses them

## Related Geometry Helpers

Useful file:
- `src/engine/robot/path_preparation/geometry.py`

Relevant functions:
- `compute_pickup_rz_from_robot_path(...)`
- `compute_pickup_rz_from_robot_contour(...)`
- `compute_pickup_rz_from_robot_contour_with_direction(...)`
- `rebuild_pose_path_from_xy(...)`

These are not the pivot projection itself, but they are relevant when deciding whether orientation should be derived from local tangent, contour moments, or fixed offsets.

## When To Add Interpolation

Consider densification when:

- `rotation_delta_applied` is large between adjacent steps
- the robot visibly swings the workpiece too abruptly
- the first-contact point changes too much between consecutive projected poses
- debugging is difficult because the path has too few waypoints to explain the motion

## Safe Densification Strategy

If you implement interpolation, prefer this model:

1. Build the coarse projected pivot path first.
2. For each adjacent pair of executed poses:
   - split by max Cartesian step
   - split by max angular step on the active rotation component
3. Interpolate pose components with angle unwrapping.
4. Rebuild debug snapshots from the final executed path, not from the coarse preview.

This keeps the projection model stable while improving execution smoothness and debugging fidelity.

## What Not To Do

- Do not densify only the plotted snapshots while leaving the executed path coarse if the goal is robot/plot agreement.
- Do not change plane mappings just to hide coarse interpolation artifacts.
- Do not assume `snapshot[0]` defines the true contact point after densification.

## Debugging Checklist

When the user asks whether points are interpolated:

- confirm whether the question refers to source-path preparation or pivot projection
- inspect the pivot projection loop in `pivot_projection.py`
- inspect output waypoint count versus input waypoint count
- inspect whether any later execution layer inserts or removes poses
- state clearly whether interpolation is geometric, visual-only, or controller-side
