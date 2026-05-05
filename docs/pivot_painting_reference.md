# Pivot Painting Reference

This document explains how pivot painting is wired on the platform side, with emphasis on the `xy_z_rz` and `xz_y_ry` modes.

## Overview

The paint workflow has two distinct phases:

1. Pickup and staging
2. Pivot-path paint execution

These phases intentionally do not use the same reference frame in all cases.

## Key Files

- `src/robot_systems/paint/application_wiring.py`
- `src/robot_systems/paint/processes/paint/workpiece_path_executor.py`
- `src/robot_systems/paint/processes/paint/pivot_projection.py`
- `src/robot_systems/paint/processes/paint/config.py`
- `src/engine/robot/path_preparation/default_workpiece_path_preparation_service.py`

## Motion Planes

Two pivot-paint motion planes are supported:

- `xy_z_rz`
- `xz_y_ry`

The mapping is defined in `config.py`.

### `xy_z_rz`

- Active planar coordinates: `X`, `Y`
- Fixed orthogonal axis: `Z`
- Active rotation component: `RZ`

### `xz_y_ry`

- Active planar coordinates: `X`, `Z`
- Fixed orthogonal axis: `Y`
- Active rotation component: `RY`

## Base Positions

The platform uses separate base positions for pickup and paint execution.

### Pickup base

Pickup and path preparation always use the primary painting base:

- movement group: `PAINTING`

This preserves the established `xy_z_rz` pickup behavior.

### Paint execution base

Paint execution depends on the active motion plane:

- `xy_z_rz` uses `PAINTING`
- `xz_y_ry` uses `PAINTING_NEW`

This split is configured in `application_wiring.py`.

## High-Level Flow

### 1. Path preparation

`DefaultWorkpiecePathPreparationService` builds execution jobs from the workpiece geometry.

Important outputs:

- `execution_path`
- `pickup_xy`
- `pickup_rz`
- `workpiece_height_mm`

### 2. Pickup-to-pivot planning

`PaintWorkpiecePathExecutor._build_pickup_and_stage_poses()` computes:

- `pickup_approach_pose`
- `pickup_pose`
- `lift_pose`
- `change_plane_pose`
- `align_pose`
- `staged_pose`

For `xz_y_ry`, pickup still happens in the pickup base frame, but the later handoff uses the paint base and the projected first pivot pose.

### 3. Pickup execution

`execute_pickup_to_pivot()` currently runs:

1. pickup approach
2. pickup descend
3. lift
4. change plane
5. align
6. stage transitions if any
7. staged pivot pose

### 4. Pivot-path execution

`_execute_pivot_paths()` projects the source execution path into the selected pivot plane and sends it to ROS2 as a per-waypoint Cartesian path.

## How Projection Works

Projection is handled by `project_paint_motion_geometry()` in `pivot_projection.py`.

High-level behavior:

1. Convert the source path to the active 2D plane.
2. Canonicalize the closed contour near the pivot.
3. Align the first contour segment to the desired contact heading.
4. Translate the shape so the first point sits on the pivot.
5. For each source segment:
   - compute the segment heading
   - rotate the whole shape around the pivot to match the target contact heading
   - translate the whole shape along the configured translation axis by the source segment length
   - emit the centroid of the transformed shape as the robot pose

Important detail:

- The emitted robot pose is the centroid of the projected shape, not the contact point.

This is why projected XYZ length can be much larger than the original source path length.

## Translation Axis vs Side of Pivot

These are separate concepts.

### Translation axis

Configured through `pivot_translation_axis`.

For the current setup:

- `xz_y_ry` uses translation axis `x`

This controls travel direction along the pivoted path.

### Side of pivot

Configured through `pivot_side`.

This controls whether the projected shape lies on one side or the other of the pivot normal.

Current behavior:

- `xy_z_rz` uses `negative`
- `xz_y_ry` uses `positive`

That change was required to place the XZ/RY workpiece below the pivot instead of above it.

## Rotation Branching

A recurring failure mode in `xz_y_ry` is equivalent-angle branch selection.

Example:

- a projected `RY` near `-179.7` degrees is mathematically close to `180.3`
- but sending the wrong equivalent branch can cause the wrist to rotate unexpectedly

To reduce that risk, align-phase `RY` is unwrapped against the current paint-pivot `RY` before being used.

## Plane-Specific Align Logic

`align_pose` is plane-aware.

### In `xy_z_rz`

- `RX` comes from the paint pivot pose
- active rotation is applied on `RZ`

### In `xz_y_ry`

- `RX` comes from the paint pivot pose
- active rotation is applied on `RY`
- `RZ` is kept consistent with the paint-frame branch to avoid a Joint_6 flip caused by mixing pickup-frame and paint-frame orientation components

## Debug Artifacts

Two debug artifacts are written during execution.

### Text dump

`pivot_trajectory_execute_<pattern>_<plane>_<timestamp>.txt`

Contains:

- source path
- projected execution path
- pivot pose
- rotation diagnostics

### Plot

`pivot_trajectory_execute_<pattern>_<plane>_<timestamp>.png`

Contains three panels:

1. Source path
2. Projected execution path in the active plane
3. Rotation progression by waypoint

This is the fastest way to diagnose:

- wrong side of pivot
- wrong initial contact heading
- unexpected rotation accumulation
- centroid drift relative to the pivot

## Current XZ/RY-Specific Behavior

For `xz_y_ry`:

- pickup/path preparation stays on `PAINTING`
- paint projection/execution uses `PAINTING_NEW`
- projected path translates along `X`
- projected shape is placed on the `positive` side of the pivot normal
- align logic rotates through `RY`

## Practical Debug Checklist

If `xz_y_ry` behaves incorrectly:

1. Check the text dump and the PNG plot for the first projected pose.
2. Verify whether the projected shape is above or below the pivot marker.
3. Check whether the first projected `RY` starts on the expected branch.
4. Compare source XYZ length vs projected XYZ length.
5. Confirm whether the issue is:
   - wrong base group
   - wrong side of pivot
   - wrong contact heading
   - wrong rotation branch
   - expected centroid motion that only looks wrong visually

## Notes for Future Changes

- Do not casually unify pickup and paint base positions. The split is intentional.
- Do not assume `translation_axis` controls above/below-pivot placement. That is controlled by `pivot_side`.
- Do not mix pickup-frame orientation components with paint-frame orientation components in `xz_y_ry` unless the branch consequences are understood.
- When changing projection behavior, always inspect both the `.txt` dump and the `.png` plot from the same run.
