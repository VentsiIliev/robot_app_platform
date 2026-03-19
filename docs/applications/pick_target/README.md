# `src/applications/pick_target/` — PickTarget

`PickTarget` is a manual debug application for validating the full image-to-robot pickup chain without running the full pick-and-place workflow. It is intended for testing:

- homography output
- calibration-plane to pickup-plane mapping
- fixed pickup orientation assumptions
- camera/TCP offset compensation
- contour trajectory capture

---

## Purpose

The application captures the latest vision contours, transforms them into robot-space targets, and allows the operator to:

- inspect transformed pickup points
- move the robot directly to those points
- execute a captured contour trajectory
- compare calibration-plane vs pickup-plane behavior
- test different pickup `rz` values quickly

This is especially useful when validating whether a transformed point aligns:

- with the camera center
- with the TCP
- or only with one reference wrist orientation

---

## Wiring

**Factory:** `_build_pick_target_application(...)` in [application_wiring.py](/home/ilv/Desktop/robot_app_platform/src/robot_systems/glue/application_wiring.py)

The app is built with:

- `vision_service`
- `robot_service`
- `HomographyTransformer`
- `robot_config`
- `GlueNavigationService`

The `HomographyTransformer` is constructed with the calibrated camera-to-TCP offsets from `robot_config`:

- `camera_to_tcp_x_offset`
- `camera_to_tcp_y_offset`

The application service also receives `robot_config` directly so it can apply pickup-plane TCP compensation during manual testing.

---

## UI Controls

The control panel currently provides:

- `Capture`: capture latest contours and transform them into robot-space points
- `Move`: move through the captured target list
- `Execute Trajectory`: execute the captured contour trajectory
- `Target: CAMERA/TOOL/GRIPPER`: choose which physical point should land on the target for both point pickup and contour execution
- `Plane: CALIB/PICKUP`: choose calibration-plane coordinates vs pickup-plane coordinates
- `Pickup RZ`: test pickup-plane wrist orientation values directly
- `Start`: move to the mode-appropriate reference position

`Start` behavior:

- calibration-plane mode: move to `CALIBRATION`
- pickup-plane mode: move to `HOME`

Trajectory execution is intentionally disabled while pickup-plane mode is enabled. The pickup-plane mode is used for manual point validation first; contour execution remains tied to the simpler calibration-plane path until the same correction model is moved into the real process.

---

## Transform Chain

### Calibration-plane mode

`Capture` uses:

1. contour centroid in image pixels
2. `TargetPointTransformer` with no mapper
3. target-point resolution in the calibration frame:
   - `camera_center`
   - `tool`
   - `gripper`

### Pickup-plane mode

Pickup-plane mode uses:

1. contour centroid in image pixels
2. homography transform into calibration-plane robot XY
3. `PlanePoseMapper` to convert into pickup-plane / `HOME` frame XY
4. mapped-pose reference-angle correction using calibrated `camera_to_tcp_*`
5. target-point resolution through `TargetPointTransformer`

---

## Pickup-Plane Reference Delta

The important debug finding was:

- the mapped pickup-plane point is already correct at `rz = 90`
- applying the full calibrated TCP offset again moves the robot away from the target

So the app does **not** apply the full TCP offset in pickup-plane mode. Instead, it applies only the orientation-dependent change from the known-good mapped-pose reference:

```text
delta(rz) = R(rz) * c - R(90) * c
target_xy = mapped_xy - delta(rz)
```

where:

- `c = (camera_to_tcp_x_offset, camera_to_tcp_y_offset)` from robot settings
- `mapped_xy` is the point after homography + calibration-to-pickup mapping

In the default pickup-plane setup, that reference is the `HOME` pose `rz`, which keeps the known-good baseline unchanged while compensating when the wrist angle changes during testing.

That correction is only applied in pickup-plane mode when the selected target is `camera_center`. When `tool` or `gripper` is selected, the app resolves those target-point offsets through `TargetPointTransformer` on top of the mapped point instead of using the older binary TCP toggle behavior.

---

## Why This App Exists

This application is the shortest path to answering questions like:

- Does homography alone align only at one wrist angle?
- Does the pickup-plane mapper preserve the expected XY reference?
- Are the calibrated TCP offsets correct in sign and frame?
- Is the miss caused by plane mapping, TCP compensation, or final pickup orientation?

It should remain a focused debug tool, not a second implementation of the full pick-and-place process.
