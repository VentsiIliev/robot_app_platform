# Geometry

## Purpose

This reference explains how the paint process converts a source contour into a pivot-executed robot trajectory, and where mismatches usually come from.

## Main Geometry Pipeline

Primary file:
- `src/robot_systems/paint/processes/paint/pivot_projection.py`

Entry point:
- `project_paint_motion_geometry(path, pivot_pose, config)`

The projection has these stages:

1. Select source 2D points from the source path using `config.source_planar_coordinate_indices`.
2. Resolve the target pivot plane using `config.planar_coordinate_indices`, `config.orthogonal_position_index`, and `config.rotation_index`.
3. Canonicalize the contour start and traversal direction with `_canonicalize_closed_source_path(...)`.
4. Rotate the source shape so the first segment matches the configured contact heading.
5. Translate the rotated shape so its first point sits on the physical pivot/base position.
6. For each source segment:
   - compute segment length
   - compute heading error against the desired contact heading
   - apply one discrete whole-shape rotation around the pivot
   - apply one discrete whole-shape translation along the configured pivot axis
   - emit one robot pose using the shape centroid

Important consequence:
- The emitted pivot path represents the workpiece centroid/TCP pose.
- The snapshots represent transformed boundary geometry.
- `snapshot[0]` is a contour vertex, not automatically the executed TCP.

## Critical Distinction

There are three different “first points” that are easy to confuse:

1. First source contour point
2. First executed robot pose in the pivot path
3. Boundary point of the transformed workpiece that is nearest the pivot

When debugging “wrong first touch”, always determine which of these is wrong.

## How The Executed Pose Is Built

The robot pose is composed in `_compose_pose(...)`.

Key properties:
- planar coordinates come from the transformed contour centroid
- orthogonal axis is held fixed from pivot configuration
- rotation is written into `rotation_index`
- other orientation components may be overridden by plane config

This means the robot is not executing the boundary polyline directly. It is executing a center pose sequence whose orientation is intended to carry the workpiece boundary through the desired motion.

## Contact / Heading Logic

Key values:
- `paint_axis_heading`
- `translation_heading`
- `contact_segment_heading`
- `rotation_delta_raw`
- `rotation_delta_applied`

Interpretation:
- `paint_axis_heading` is the axis used for projected translation.
- `contact_segment_heading` is the target heading for the contour’s active first segment.
- For each source segment, the delta between current segment heading and desired contact heading becomes the applied rotation.

This is not continuous rotation interpolation. It is discrete rotate-then-translate per source segment.

## Closed-Contour Canonicalization

`_canonicalize_closed_source_path(...)` is important when the source is a loop.

It:
- chooses a start point near the actual pivot
- chooses forward or reverse ordering
- tries to align contour orientation to the desired travel direction and requested side

If the wrong part of the workpiece reaches the pivot first, inspect this function before changing interpolation.

## Where Robot/Plot Mismatch Comes From

Typical causes:

- plotting preview snapshots instead of execution-aligned snapshots
- staged pose differs from first executed pivot path pose
- `xz_y_ry` execution applies a later rotation-direction flip
- alignment is performed in the wrong frame or wrong axis component
- debug plot labels a contour point as “contact” when the executed TCP is actually the centroid pose

## Practical Debug Method

When a user reports “the robot touches with a different point than the plot”:

1. Log and inspect `plan.staged_pose`.
2. Log the first waypoint of `pivot_path`.
3. Plot or compute the transformed contour snapshot at that exact executed pose.
4. Mark:
   - pivot position
   - executed TCP/centroid
   - nearest contour point to pivot
5. Only after that decide whether the bug is:
   - geometry construction
   - pickup alignment
   - plane-change ordering
   - plotting
