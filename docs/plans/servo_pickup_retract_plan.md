# Servo Pickup Retract and Continuation Plan

## Objective

Remove the idle planning interval after servo pickup without weakening the existing ordered-motion gates.

The change is limited to the servo operation, which currently sits outside the ordered motion sequence. No additional process or continuation lifecycle states are required.

## Target sequence

```text
Existing ordered approach
    -> servo down until pickup condition
    -> stop downward servo
    -> blocking PTP retract to the selected retract reference Z
    -> ordered continuation built from that pose
```

The caller supplies an explicit, configured retract reference pose. For the
initial implementation:

- Magazine pickup uses the configured magazine pose.
- Paint/calibration-table pickup uses the configured calibration pose.

These are intentionally simple first choices. Smarter retract-pose selection
may be added later without changing the servo procedure contract.

For this Z-axis servo strategy, the selected reference contributes the retract
Z only. The live pickup X, Y, Rx, Ry, and Rz remain unchanged. The continuation
must be built or trimmed from that resulting live pose; it must not execute an
older lift waypoint that would move the robot downward again after retraction.

## Procedure contract

Extend `ServoUntilConditionProcedure` with optional retract configuration. A successful result must mean all of the following:

1. The pickup condition was detected.
2. Downward servo motion was stopped.
3. Blocking PTP retraction completed.
4. The configured retract position was reached within tolerance.

The caller must not execute the continuation unless the procedure returns success.

Conceptual caller flow:

```python
result = procedure.run(
    config=servo_config,
    retract_pose=retract_reference_pose,
)

if not result.success:
    stop_motion()
    return False

return execute_continuation_from(retract_reference_pose)
```

## Retract behavior

For the current Z-axis pickup:

- Use the Z coordinate of the caller-supplied retract reference pose as the
  servo retract target.
- Keep X, Y, Rx, Ry, and Rz unchanged throughout servo descent and the PTP retract.
- Start a blocking PTP retract immediately after successful contact detection
  and confirmed downward servo stop.
- Build the PTP target from the live contact pose, replacing only its Z with the
  selected retract reference Z.
- Verify the final Z against a configurable tolerance.
- Enforce a maximum retract distance and retract timeout.
- Keep vacuum enabled throughout a successful pickup and retract.

The procedure must not attempt Cartesian correction of X, Y, or orientation.
Before retracting, verify that the target Z is above the detected contact Z and
that the retract distance is within the configured maximum. The configured
reference pose's X, Y, and orientation are not servo targets and must not cause
Cartesian correction during this procedure.

## Failure handling

Any failure must prevent the continuation from executing.

Failure cases include:

- downward servo start failure;
- pickup-condition timeout;
- pickup-condition read failure;
- cancellation, pause, or stop request;
- downward servo-stop failure or unconfirmed stop;
- PTP retract start/execution failure;
- current-position read failure during retract;
- retract timeout;
- maximum retract distance exceeded;
- final retract-position mismatch.

On failure:

1. Request `stop_servo_jog()` unconditionally when servo may be active.
2. Call `stop_motion()` if servo stopping fails or cannot be confirmed.
3. Cancel or discard any prepared continuation.
4. Return failure to the existing pickup/process flow.
5. Do not execute lateral transfer, calibration motion, or the remaining pickup sequence.

### Contact-timeout recovery policy

The default policy should be to stop at the current position and enter the existing error/recovery flow.

An optional controlled upward recovery may return the robot to the selected
retract reference pose, but it must still return pickup failure. Successful
recovery motion must never authorize the continuation because pickup contact
was not confirmed.

## Continuation preplanning

Preplanning is an optimization to add after safe PTP retraction works reliably.

- Prepare the continuation from the selected retract reference pose while servo
  pickup is active.
- The preparation API must be plan-only: it must not queue, authorize, or start robot execution.
- Keep the prepared result local to the active pickup call when practical.
- If servo pickup or retract fails, cancel or discard the prepared result.
- If servo pickup and retract succeed, execute the prepared continuation.
- If preparation is incomplete, wait at the selected retract reference pose.

The existing ordered-motion gates and endpoint verification remain unchanged.

## Diagnostics

Add focused timing and result logs for:

- downward servo start;
- pickup-condition detection;
- downward servo-stop request and result;
- retract start;
- retract target Z;
- live/final retract Z;
- PTP retract result;
- total procedure time;
- final success or precise failure reason;
- whether a prepared continuation was used or discarded.

## Verification

### Automated and simulated checks

Verify:

1. Successful contact retracts to the configured retract reference pose.
2. Magazine pickup uses the configured magazine pose.
3. Paint/calibration-table pickup uses the configured calibration pose.
4. Contact timeout never starts the continuation.
5. Sensor-read failure never starts the continuation.
6. Downward servo or PTP retract failure never starts the continuation.
7. Retract timeout or position mismatch never starts the continuation.
8. Stop or pause during descent stops servo motion.
9. Stop or pause during retract stops servo motion.
10. A discarded preplan cannot be reused by a later pickup.
11. The first continuation segment starts from the selected retract reference
    pose and does not descend to an obsolete lift waypoint.

### Hardware verification order

1. Test downward servo stop without retraction.
2. Test blocking PTP retraction at reduced speed and clearance.
3. Verify stopping accuracy at the selected retract reference Z.
4. Test magazine pickup without continuation execution.
5. Test calibration pickup without continuation execution.
6. Enable the continuation after successful retract verification.
7. Add concurrent plan-only preparation and measure the remaining idle time.
8. Inject or simulate failures and confirm that no continuation motion starts.

## Implementation order

1. Define retract configuration and extend the servo procedure result contract.
2. Implement guarded blocking PTP retraction and final-position verification.
3. Pass the configured magazine pose from the magazine pickup caller.
4. Pass the configured calibration pose from the paint/calibration pickup
   caller.
5. Build or trim each continuation from its selected retract reference pose and
   remove any obsolete post-contact lift that would command downward motion.
6. Verify every servo/retract failure returns before the continuation.
7. Add targeted tests and controlled hardware checks.
8. Add plan-only continuation preparation if an idle interval remains.
9. Update engine and paint robot-system documentation for the final implemented behavior.
