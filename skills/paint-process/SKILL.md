---
name: paint-process
description: Use this skill when working on the paint process under src/robot_systems/paint/processes/paint, especially pickup-to-pivot flow, pivot projection geometry, motion-plane configuration, staged pose alignment, debug plots, and path interpolation or densification behavior.
---

# Paint Process

Use this skill for code and debugging work in `src/robot_systems/paint/processes/paint`. It is for failures where the painted trajectory, staged pose, pivot contact point, debug plot, or robot motion do not agree.

## When To Use

Use this skill when the task involves:

- `workpiece_path_executor.py`
- `pivot_projection.py`
- `config.py`
- pickup or staged-pose ordering
- `xy_z_rz` vs `xz_y_ry` plane behavior
- `RZ` vs `RY` alignment mistakes
- debug plot mismatches versus real robot execution
- interpolation, densification, or waypoint smoothing in paint motion

## Working Rules

- Start from the actual executed path, not just the preview path.
- Treat `xy_z_rz` and `xz_y_ry` as different kinematic interpretations, not as a cosmetic axis rename.
- Separate three concepts when reasoning:
  - source contour geometry
  - executed robot TCP/centroid path
  - plotted workpiece boundary snapshots
- When debugging first contact, verify all three:
  - the staged pose the robot moves to before trajectory execution
  - the first waypoint of the executed pivot path
  - the boundary point nearest the pivot in the transformed snapshot

## Workflow

1. Read `src/robot_systems/paint/processes/paint/workpiece_path_executor.py` first.
2. Confirm the active motion plane and runtime flags in `src/robot_systems/paint/processes/paint/config.py`.
3. Trace the geometry build in `src/robot_systems/paint/processes/paint/pivot_projection.py`.
4. If the bug is visible on the robot, compare against the final executed path, not just `project_paint_motion_geometry(...)` output.
5. If the bug looks like orientation drift or point mismatch before pivot paint starts, inspect pickup ordering and staged pose construction before changing projection math.
6. If motion is too coarse, inspect interpolation or densification assumptions before changing the plane mapping.

## Decision Guide

- For pivot/contact mismatch:
  Read `references/geometry.md`.
- For wrong axis, wrong rotation component, or plane-specific behavior:
  Read `references/configuration.md`.
- For jerkiness, missing intermediate points, or rotation applied in large discrete jumps:
  Read `references/interpolation.md`.

## Repo-Specific Expectations

- Preserve the platform/application/system boundaries from `AGENTS.md`.
- Do not modify `pl_gui/`.
- Use `apply_patch` for file edits.
- If you change code under `src/robot_systems/`, ask whether `docs/robot_systems/` should be updated.

## Key Files

- `src/robot_systems/paint/processes/paint/workpiece_path_executor.py`
- `src/robot_systems/paint/processes/paint/pivot_projection.py`
- `src/robot_systems/paint/processes/paint/config.py`
- `src/robot_systems/paint/processes/paint/pickup_planner.py`
- `src/engine/robot/path_preparation/geometry.py`

## What Good Analysis Looks Like

- Identify whether the issue is in pose generation, transform ordering, or visualization.
- State which frame each value belongs to: source contour, pickup frame, pivot plane, or executed robot pose.
- Use concrete references to `plan.staged_pose`, first pivot waypoint, `rotation_index`, `planar_coordinate_indices`, and source coordinate indices.
- Prefer small, testable changes over broad rewrites of the projection model.
