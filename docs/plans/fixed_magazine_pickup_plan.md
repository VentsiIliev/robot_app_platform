# Fixed Magazine Pickup Plan

## Objective

Add a configurable, camera-independent magazine pickup mode for guaranteed
workpiece placement while preserving the current vision-targeted magazine
pickup as the default.

The fixed mode will use a dedicated, taught movement group as the complete
servo-descent starting pose. It will not capture a magazine image, select a
contour, calculate a centroid, or calculate pickup orientation.

This change is limited to the magazine-loading phase. The calibration-table
capture and pickup flow must remain unchanged.

## Required behavior

Expose one magazine pickup mode selector with only valid workflows:

```text
vision_planned             Existing vision target followed by planned descent
vision_servo_contact       Existing vision target followed by servo-contact descent
fixed_group_servo_contact  Taught movement-group pose followed by servo-contact descent
```

The default and missing-setting behavior must be `vision_planned` so existing settings
files and deployed behavior remain backward compatible.

Magazine target and contact choices are intentionally combined so the settings
UI cannot create invalid or confusing combinations. Calibration pickup remains
a separate strategy:

```text
Magazine Load       Magazine Pickup Mode
Calibration Pickup  planned | servo_contact | height_measure
Servo Contact       Shared descent, sensor, timeout, and retract tuning
```

## Movement-group ownership

Add or teach a dedicated movement group, initially named:

```text
Magazine Fixed Pickup
```

Its configured six-axis pose has one precise meaning:

> The robot TCP pose at which it is safe to begin downward servo pickup.

The group contains X, Y, safe starting Z, Rx, Ry, and Rz. Its Z is not the
expected contact height. The existing servo minimum-Z, timeout, sensor-read,
and retract constraints continue to bound the descent.

Do not reuse the existing `Magazine` group for this purpose. That group remains
the vision observation/navigation pose and may have different camera and tool
geometry.

Add settings similar to:

```python
MAGAZINE_PICKUP_MODE_VISION_PLANNED = "vision_planned"
MAGAZINE_PICKUP_MODE_VISION_SERVO_CONTACT = "vision_servo_contact"
MAGAZINE_PICKUP_MODE_FIXED_GROUP_SERVO_CONTACT = "fixed_group_servo_contact"

@dataclass(frozen=True)
class PaintMagazineLoadConfig:
    pickup_mode: str = MAGAZINE_PICKUP_MODE_VISION_PLANNED
    fixed_pickup_group_id: str = "Magazine Fixed Pickup"
    fixed_pickup_position_tolerance_mm: float = 2.0
    fixed_pickup_orientation_tolerance_deg: float = 1.0
```

Final tolerances must be validated on the real robot. They must be configurable
and must not be loosened automatically after a verification failure.

## Target process sequences

### Existing vision mode

```text
move to Magazine observation group
    -> wait for camera settle
    -> capture magazine snapshot
    -> select contour
    -> calculate centroid and pickup Rz
    -> resolve robot pickup target
    -> execute configured magazine contact strategy
    -> transfer and release at calibration
```

This sequence and its defaults must remain behaviorally unchanged.

### New fixed-group mode

```text
resolve Magazine Fixed Pickup group pose
    -> validate mode, group pose, pump, sensor, tool/user, and descent bounds
    -> move to Magazine Fixed Pickup group
    -> read fresh live pose
    -> verify live pose matches the group pose
    -> enable vacuum
    -> read and verify fresh live pose again
    -> servo downward until pickup condition
    -> stop and retract
    -> verify the workpiece remains detected
    -> transfer and release at calibration
```

Fixed mode must not call the magazine snapshot service or vision pickup-target
resolver.

### Calibration flow after magazine release

Both modes rejoin before the calibration phase:

```text
release magazine workpiece at calibration
    -> move to calibration capture position
    -> wait for camera settle
    -> capture calibration workpiece
    -> prepare workpiece and build paint plan
    -> perform the existing calibration-table pickup
```

The calibration capture, centroid calculation, target resolution, and
`pickup_contact_mode` behavior are out of scope and must not be altered by the
new magazine targeting mode.

## Mandatory start-pose safety invariant

Downward servo motion in fixed-group mode is authorized only when a fresh live
robot pose matches the configured fixed-pickup movement-group pose.

Calculate translational error using the three-dimensional Euclidean distance:

```text
position_error = sqrt(dx^2 + dy^2 + dz^2)
```

Calculate orientation error per axis using shortest wrapped angular distance,
then use the maximum error:

```text
axis_error = abs((actual - expected + 180) % 360 - 180)
orientation_error = max(rx_error, ry_error, rz_error)
```

Servo descent is allowed only when:

```text
position_error <= fixed_pickup_position_tolerance_mm
and
orientation_error <= fixed_pickup_orientation_tolerance_deg
```

The verifier must also confirm:

- the movement group exists and provides exactly six finite numeric values;
- a fresh live robot pose can be read and contains six finite numeric values;
- the expected pickup tool and user frame are active or explicitly selected by
  the servo procedure;
- the actual starting Z is above `servo_contact_min_z_mm` with a defensible
  clearance;
- the pickup condition can be read during servo preflight;
- the process is not paused, stopping, or cancelled;
- the vacuum pump and pickup sensor are enabled for the process.

Perform the pose check after reaching the group and again immediately before
starting servo descent. Keep the final check adjacent to the servo call so a
future state-machine refactor cannot bypass it.

On mismatch, return a precise error containing the group name, measured
position and orientation errors, and allowed tolerances. Do not start downward
motion. For example:

```text
Magazine servo descent refused: robot is not at 'Magazine Fixed Pickup'
(position error 4.8 mm, allowed 2.0 mm; orientation error 0.3 deg, allowed 1.0 deg)
```

## Pause, resume, and manual displacement

Pause or stop during servo descent must retain the existing unconditional
servo-stop behavior.

Fixed pickup must not resume downward movement from an arbitrary current pose.
After a pause, cancellation, manual jog, failed descent, or interrupted group
move:

1. Stop active robot motion.
2. Return through the existing process recovery path.
3. Move back to the configured fixed-pickup group before a new servo attempt.
4. Repeat both fresh-pose verification gates.

Do not treat an earlier successful verification as valid after any interruption
or state transition that permits robot movement.

## State-machine integration

Branch on the snapshotted `PaintMagazineLoadConfig.pickup_mode` before
the camera-settle and capture states.

Prefer explicit fixed-mode preparation/execution handlers or a small
target-strategy seam over fabricating a contour or injecting fake centroid
coordinates into `_resolve_pickup_target()`.

The fixed-mode context should carry:

```text
fixed pickup group ID
expected group pose
last verified live pose
verification result/diagnostics
```

The servo executor must receive the expected start pose and tolerances as
required inputs. It must not infer authorization merely because an earlier
navigation call returned success.

Preserve the current cycle-level configuration snapshot so UI or settings
changes made during a running cycle cannot change the pickup mode or group.

## Calibration release decoupling

The current magazine flow uses the magazine snapshot frame dimensions while
resolving the calibration work-area center release pose. Fixed mode deliberately
has no magazine snapshot, so this dependency must be removed before fixed mode
can be camera-independent.

Preferred solution:

```text
Use a dedicated, taught calibration release movement group or named robot target.
```

An initial name could be:

```text
Magazine Calibration Release
```

The release target must remain distinct from the later `CALIBRATION` camera
observation group. If a resolver-based release target is retained instead, it
must obtain calibrated image dimensions from configuration rather than from a
fresh magazine capture.

Do not retain a hidden capture solely to obtain frame dimensions; that would
violate the fixed mode's camera-independent contract.

## Settings and UI work

1. Extend `PaintMagazineLoadConfig` with pickup mode, fixed group ID, and pose
   tolerances.
2. Preserve `vision` defaults in `PaintProcessConfigSerializer` so old JSON
   remains valid without migration.
3. Extend `PaintProcessSettingsMapper` for complete round-trip behavior.
4. Add the target-mode selector and fixed-group/tolerance fields to the paint
   process settings schema.
5. Validate unsafe combinations in both the settings controller and runtime;
   UI validation is convenience, not a safety boundary.
6. Add English and Bulgarian catalog entries for all new UI strings.
7. Add the taught movement-group entry through the existing movement-group
   settings mechanism rather than embedding a raw pose in paint process JSON.

If the settings UI can enumerate movement groups, use a constrained selector.
Otherwise use the existing group-ID editing pattern and perform strict runtime
resolution.

## Failure policy

Every fixed-mode configuration or verification failure is fail-closed.

The following must prevent downward servo motion and transfer continuation:

- unknown magazine pickup mode;
- fixed mode combined with a non-servo contact mode;
- missing fixed group ID;
- missing or malformed movement-group pose;
- non-finite target or live-pose values;
- stale or unavailable live robot pose;
- start-pose position or orientation mismatch;
- unsafe relationship between start Z and minimum descent Z;
- pump or pickup-sensor prerequisite failure;
- servo preflight read failure;
- pause, stop, or cancellation;
- servo start, contact detection, stop, retract, or post-retract verification
  failure.

Do not automatically fall back to vision, planned descent, or a different
movement group. A fallback could move the robot according to geometry the
operator did not authorize for that cycle.

## Diagnostics

Log at least:

- selected magazine pickup mode;
- fixed pickup group ID and resolved expected pose;
- first and final fresh live poses used for verification;
- measured position and orientation errors and configured tolerances;
- selected tool/user and servo minimum Z;
- whether vacuum activation succeeded;
- explicit authorization or refusal of servo descent;
- servo result, detected contact, timeout, and retract result;
- pause/resume recovery and re-verification decisions;
- confirmation that the calibration capture path starts after release.

Avoid logging a successful group move as proof of start-pose verification; log
the live-pose comparison separately.

## Automated verification

Add focused tests covering:

1. Missing target-mode settings deserialize to `vision`.
2. Vision mode follows the current camera-settle, capture, contour, centroid,
   orientation, and resolver path.
3. Fixed mode never calls magazine `capture_snapshot()`.
4. Fixed mode never calls `_resolve_pickup_target()`.
5. Fixed mode resolves and moves to the configured movement group.
6. Fixed mode refuses a missing, short, nonnumeric, NaN, or infinite group pose.
7. Fixed mode refuses any contact mode other than `servo_contact`.
8. Servo descent does not start when the fresh pose cannot be read.
9. Servo descent does not start when translation exceeds tolerance.
10. Servo descent does not start when wrapped orientation error exceeds
    tolerance.
11. Wrapped angles such as `179` and `-179` compare correctly.
12. Servo descent starts only after both live-pose checks pass.
13. Displacement between the first and second check prevents descent.
14. Vacuum or sensor prerequisite failure prevents descent.
15. Minimum-Z, timeout, sensor-read, stop, and retract failures retain existing
    fail-closed behavior.
16. Pause/resume requires returning to and re-verifying the fixed group.
17. Fixed mode reaches the calibration release target without a magazine frame.
18. The later calibration snapshot and normal workpiece preparation still run.
19. Calibration pickup continues to use `pickup_contact_mode`, not the
    magazine-specific targeting mode.
20. Settings and UI mapping round-trip all new fields without changing existing
    values.

## Hardware verification order

Use reduced speed and generous initial clearance. Keep an operator at the stop
control throughout these checks.

1. Teach and visually verify `Magazine Fixed Pickup` without enabling servo.
2. Exercise the fresh-pose verifier while exactly at the group.
3. Deliberately offset X, Y, Z, and each rotation and confirm servo is refused.
4. Verify wrapped-angle behavior near `-180/180` degrees.
5. Enable vacuum and confirm the second pose check still passes when stationary.
6. Introduce movement between the two checks and confirm descent is refused.
7. Test a short servo descent with the workpiece absent and verify timeout/stop.
8. Test pickup detection and retract without transfer continuation.
9. Test pause and stop during descent and verify a new attempt returns to the
   fixed group and rechecks the pose.
10. Test transfer to the camera-independent calibration release target.
11. Confirm the subsequent calibration capture and pickup behave exactly as in
    vision mode.
12. Run alternating vision and fixed-group cycles to verify the config switch
    and absence of stale context data.

## Implementation order

1. Finalize the taught group names and decide the camera-independent calibration
   release target ownership.
2. Add target-mode constants and backward-compatible configuration fields.
3. Add serializer, mapper, settings UI, validation, and localization coverage.
4. Implement a reusable fresh-pose comparison helper with wrapped-angle tests.
5. Add the fixed-mode state-machine branch before camera settle/capture.
6. Resolve and validate the fixed movement-group pose before motion.
7. Move to the group using existing pause/resume-aware navigation.
8. Add the mandatory pre-servo pose gates and runtime prerequisite checks.
9. Reuse the existing servo-contact procedure and retract safeguards.
10. Decouple calibration release targeting from the magazine snapshot.
11. Rejoin the unchanged calibration capture flow after release.
12. Add targeted unit/state-machine tests and compile touched Python modules.
13. Validate English and Bulgarian JSON catalogs and key coverage.
14. Perform the staged hardware verification above.
15. Update `docs/robot_systems/` with the final configuration, group semantics,
    safety invariant, recovery behavior, and operator teaching procedure.

## Out of scope

- Changing calibration-table vision capture or centroid calculation.
- Changing calibration-table pickup targeting or contact strategy.
- Automatically teaching or updating movement-group poses.
- Falling back between fixed and vision modes during a cycle.
- Generalizing fixed-group targeting to other robot systems before the paint
  magazine implementation is verified.
