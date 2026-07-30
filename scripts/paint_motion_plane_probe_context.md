# Paint Motion Plane Probe Context

## Purpose

The paint motion plane probe is a standalone PyQt6 wizard prototype in
`scripts/paint_motion_plane_probe.py`.

Its goal is to avoid hard-coding paint motion planes such as `xz_y_ry` for
different robot mounting orientations. Instead, the user performs a short
guided procedure from the actual paint pose, and the tool infers a structured
motion-plane object that can later be integrated into the paint system.

No production paint-system code has been changed for this prototype.

## Core Idea

The user teaches three things from the desired paint position/orientation:

1. The paint reference pose.
2. The preferred paint translation direction.
3. The intended pivot rotation axis.
4. The position axis that should stay constant during painting.

From those captures, the probe infers:

- translation axis, for example `x`
- translation direction, `forward` or `reverse`
- rotation axis, for example `ry`
- planar axes, for example `x/z`
- fixed axis, for example `y`
- suggested plane key, for example `xz_y_ry`
- structured plane object for future runtime configuration

The important design point is that the procedure starts from the actual paint
movement-group pose. This matters because the same physical robot behavior can
map to different platform axes when the tool orientation changes, for example
between `RX=180` and `RX=0` paint poses.

## Current Wizard Flow

1. **Move to Paint Position**
   - Shows current pose and stored paint pose.
   - Pressing `Move Current to Paint Position` asks for confirmation using the
     shared `styled_message_box.ask_yes_no`.
   - The dialog includes the full six-axis target pose.
   - `Next` is disabled until the move is confirmed.

2. **Capture Reference Pose**
   - Captures the current pose as the paint reference pose.
   - The jog drawer remains available.

3. **Move and Capture Translation**
   - User jogs along the intended paint translation axis.
   - Captured pose is read-only and updated from current pose.
   - The guide image highlights the detected selected translation axis after
     capture.
   - User can return to reference and redo the move.

4. **Move and Capture Rotation**
   - User jogs around the intended pivot rotation axis.
   - Captured pose is read-only and updated from current pose.
   - The guide image highlights the detected selected rotation axis after
     capture.
   - User can return to reference and redo the move.

5. **Constant Axis**
   - User selects which position axis should remain fixed during painting.
   - This prevents relying only on the detected rotation axis and makes the
     generated plane explicit.

6. **Inference**
   - Shows the inferred plane and JSON output.
   - The output includes both the old-style `pivot_motion_plane` key and a
     future-facing `pivot_motion_plane_config` object.

## Current Output Shape

Example output for an X/Z plane, fixed Y, rotating around RY:

```json
{
  "pivot_motion_plane": "xz_y_ry",
  "pivot_motion_plane_config": {
    "label": "xz_y_ry",
    "planar_axes": ["x", "z"],
    "fixed_axis": "y",
    "rotation_axis": "ry",
    "translation_axis": "x",
    "translation_direction": "forward",
    "axis_offsets_deg": {
      "x": 0.0,
      "z": 90.0
    }
  },
  "pivot_translation_axis": "x",
  "pivot_translation_direction": "forward",
  "axis_offsets_deg": {
    "x": 0.0,
    "z": 90.0
  },
  "orientation_overrides_deg": {}
}
```

## UI Notes

- The script uses `ConfigurableWizard` from the existing shell utilities.
- The jog control is integrated as a right-side drawer using the existing
  `DrawerToggle` and `RobotJogWidget`, matching the main shell behavior.
- The drawer is available on all steps.
- The drawer should not close automatically after jogging.
- Jogging consumes only one request per button press in the simulation to avoid
  runaway current-pose changes.
- Step completion gates the `Next` button.
- Confirmation dialogs should use existing shared components when present.

## Integration Direction

The future production integration should likely store a structured plane object
instead of requiring every possible named plane combination to exist in code.

Likely integration targets to revisit:

- `src/robot_systems/paint/processes/paint/config.py`
- `src/robot_systems/paint/processes/paint/execute/workpiece_path_executor.py`
- `src/robot_systems/paint/processes/paint/execute/pivot_projection/core.py`
- `src/robot_systems/paint/processes/paint/execute/execution_plane/strategies.py`
- `src/robot_systems/paint/application_wiring.py`

The existing paint projection appears to project in a canonical plane and then
adapt/swap axes based on the selected motion plane. A structured plane object
should make that mapping data-driven:

- position axis names map to pose indices: `x=0`, `y=1`, `z=2`
- rotation axis names map to pose indices: `rx=3`, `ry=4`, `rz=5`
- planar axes define which two position dimensions receive projected path data
- fixed axis defines which position component remains constant
- translation axis and direction define execution ordering and pivot movement

The difficult part to verify later is not just coordinate projection. Pickup,
pivot handoff, preflight, and execution-plane strategy behavior may still have
special assumptions around `xz_y_ry`.

## Assumptions

- The wizard is currently a simulator/prototype, not connected to a real robot.
- `Move Current to Paint Position` sets the simulated current pose to the stored
  paint pose.
- In production, that action should call the existing motion service/movement
  group mechanism for the paint position.
- A missing `orientation_overrides_deg` means the generated path should use the
  taught paint base pose orientation.
- An override value of `0.0` means force exactly `0.0`; it is not the same as
  leaving the override absent.

