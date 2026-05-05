# Configuration

## Purpose

This reference explains how paint-process configuration changes geometry meaning. The most important rule is that `xy_z_rz` and `xz_y_ry` are not interchangeable.

## Main File

- `src/robot_systems/paint/processes/paint/config.py`

## Motion Plane Specs

Defined in `_PAINT_MOTION_PLANE_SPECS`.

### `xy_z_rz`

- source planar axes: `(0, 1)`
- executed planar axes: `(0, 1)`
- fixed orthogonal axis: `Z`
- active rotation component: `RZ`

This is conceptually standard in-plane XY motion with yaw-like rotation.

### `xz_y_ry`

- source planar axes: `(0, 1)` from the source path data
- executed planar axes: `(0, 2)`
- fixed orthogonal axis: `Y`
- active rotation component: `RY`
- orientation override: `RX = 90`

This is not a simple relabel of the XY case. The geometry is interpreted in a different plane and written back into different robot pose components.

## Fields That Matter Most

From `PaintSimulationConfig`:

- `motion_plane`
- `translation_axis`
- `paint_side`
- `translation_direction`
- `planar_coordinate_indices`
- `source_planar_coordinate_indices`
- `orthogonal_position_index`
- `rotation_index`
- `orientation_overrides_deg`
- `paint_axis_offset_deg`
- `side_sign`
- `direction_sign`

When behavior looks mirrored or rotated incorrectly, inspect these before patching math.

## Runtime Behavior Flags

From `PaintProcessConfig`:

- `pivot_motion_plane`
- `pivot_translation_axis`
- `pivot_translation_direction`
- `flip_xz_ry_execution_rotation_direction`
- `enable_xz_ry_preflight`
- `apply_camera_to_tcp_for_pickup`

### `flip_xz_ry_execution_rotation_direction`

This flag is narrow in scope. It affects the executed pivot paint path in `xz_y_ry` mode by mirroring each waypoint’s `RY` around the starting `RY`.

Use it when:
- the pivot paint direction is geometrically correct except for handedness of `RY`

Do not assume it fixes:
- pickup alignment
- staging mismatch
- wrong boundary contact point before pivot execution starts

## Pickup / Align / Plane-Change Semantics

If the flow is:
- pickup
- align
- change plane
- move to staged pose

then the align step must still be expressed in the pickup frame. In practice this means:

- before plane change, `RZ` is the stable alignment component
- `RY` should not be used as the direct pickup-frame alignment actuator
- after plane change, the pivot plane may use `RY`, but that does not mean pre-plane-change alignment should also be performed in `RY`

If the flow is instead:
- pickup
- change plane
- align

then using the pivot-plane rotation component may be appropriate.

Always align the pose-construction logic with the actual move ordering.

## Configuration Debug Checklist

When the motion is wrong in `xz_y_ry`:

1. Confirm `rotation_index == 4`.
2. Confirm `planar_coordinate_indices == (0, 2)`.
3. Confirm which orientation component is used before plane change.
4. Confirm whether execution flips `RY` after the path is built.
5. Confirm that debug plots are built from the final executed path when comparing against the robot.
