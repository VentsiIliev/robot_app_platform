# `src/applications/pick_target/` — PickTarget

`PickTarget` is a manual debug application for validating the full image-to-robot pickup chain without running the full pick-and-place workflow. It is intended for testing:

- homography output
- calibration-plane to pickup-plane mapping
- fixed pickup orientation assumptions
- camera/TCP offset compensation
- contour trajectory capture
- height correction (depth-map model and live laser measurement)

---

## Purpose

The application captures the latest vision contours, transforms them into robot-space targets, and allows the operator to:

- inspect transformed pickup points
- move the robot directly to those points
- execute a captured contour trajectory
- compare calibration-plane vs pickup-plane behavior
- test different pickup `rz` values quickly
- validate height correction before enabling it in production

---

## Wiring

**Factory:** `_build_pick_target_application(...)` in `application_wiring.py`

The app is built via `_build_glue_vision_resolver(robot_system)` which returns a shared `(base_transformer, resolver)` pair. The same helper is used by the dashboard and glue process driver, so all applications share the same calibrated homography and point registry.

```python
base_transformer, resolver = _build_glue_vision_resolver(robot_system)
service = PickTargetApplicationService(
    transformer=base_transformer,
    robot_config=robot_system._robot_config,
    navigation=robot_system._navigation,
    height_correction=HeightCorrectionService(height_service),
    height_measuring=height_service,
)
```

---

## UI Controls

| Control | Description |
|---------|-------------|
| `◉ Capture` | Capture latest contours, transform to robot space, display in log |
| `▶ Move` | Move to all captured targets in sequence |
| `⬡ Execute Trajectory` | Execute contour outlines as robot trajectories |
| `Target: CAMERA/TOOL/GRIPPER` | Select which end-effector point should land on the target |
| `Plane: CALIB/PICKUP` | Toggle calibration-plane vs pickup-plane (HOME frame) coordinates |
| `Pickup RZ` | Wrist orientation used for both calib and pickup-plane modes |
| `Z: DIRECT / Z: TWO-STEP` | Toggle between immediate Z correction and two-step mode |
| `↕ Apply Z Correction` | In two-step mode: apply depth-map Z correction to the last moved targets |
| `📏 Measure Height` | After moving to base Z, use the live laser to measure and adjust Z |
| `↩ Start` | Move to the mode-appropriate reference position |

**Start behavior:**
- calibration-plane mode → `CALIBRATION`
- pickup-plane mode → `HOME`

Trajectory execution is disabled while pickup-plane mode is active.

---

## Transform Chain

All transformations go through `VisionTargetResolver` from `src/engine/robot/targeting/`.
The service builds a `VisionPoseRequest`, resolves the selected target through `PointRegistry`, and calls `resolver.resolve(request, point, ...)`. The selected point is always one of the supported registry points: `camera`, `tool`, or `gripper`. When it needs the final robot pose it uses `result.robot_pose()`.

### Calibration-plane mode

```
pixel (px, py)
  → HomographyTransformer.transform()   [calibration-plane XY]
  → TCP-delta correction at current_rz
  → end-effector offset for selected target (camera/tool/gripper)
  → final robot XY
```

### Pickup-plane mode

```
pixel (px, py)
  → HomographyTransformer.transform()   [calibration-plane XY]
  → PlanePoseMapper (CALIBRATION → HOME)  [pickup-plane XY]
  → TCP-delta correction at current_rz
  → end-effector offset for selected target
  → final robot XY
```

In the current implementation there is one resolver. `_transform_point()` chooses the active frame, and `capture()` builds a `VisionPoseRequest(z_mm=_Z, ...)` when it needs the final move pose.

---

## Z Correction Modes

### DIRECT (default)

The resolver can include frame height correction in the returned pose when the active frame has a height-correction service configured.
That means the final `z` already comes back resolved in `result.robot_pose()`.

### TWO-STEP

1. `Move` calls `move_to_base()` — always `Z_BASE = 300 mm`, no live measurement
2. After all moves complete, `Apply Z Correction` re-runs the move path using corrected Z

### Measure Height

When the `📏 Measure Height` toggle is on, `Move` calls `move_to_with_live_height()`:

1. Move to `Z_BASE` (base Z, no correction)
2. Call `IHeightMeasuringService.measure_at(robot_x, robot_y)` — laser moves to calibrated measurement height, measures surface
3. Move to `Z_BASE + measured_z`

Live measurement and depth-map correction are mutually exclusive per move.

---

## Jog Widget Integration

A `RobotJogWidget` is embedded in a `DrawerToggle` panel on the right side of the view.

The jog widget enables the base widget's optional **Frame selector** combo box (`camera`, `tool`, `gripper`). Changing the frame selector also changes the active target for capture/move, keeping both selectors in sync. The existing `Target:` button on the control panel does the same thing.

The `JogController` handles live robot position polling and jog commands. In glue wiring, the jog service is target-aware: it converts jog requests into corrected Cartesian moves so the selected `camera/tool/gripper` point stays consistent with TCP-delta compensation. It is started in `controller.load()` and stopped in `controller.stop()`.

---

## Pickup-Plane Reference Delta

The mapped pickup-plane point is already correct at the reference `rz` (from `HOME` pose). Applying the full TCP offset again at that reference angle would move the robot away from the target.

Instead, only the **orientation-dependent change** from the reference is applied:

```text
delta(rz) = R(rz) · tcp_offset − R(ref_rz) · tcp_offset
target_xy = mapped_xy − delta(rz)
```

This correction is always applied relative to the mapper reference pose. The correction is zero when `rz == ref_rz`, preserving the known-good baseline.
