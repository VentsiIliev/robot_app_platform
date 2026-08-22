# Servo Pickup Retract and Continuation Plan

## Objective

Remove the idle planning interval after servo pickup without weakening the existing ordered-motion gates.

The change is limited to the servo operation, which currently sits outside the ordered motion sequence. No additional process or continuation lifecycle states are required.

## Target sequence

```text
Existing ordered approach
    -> servo down until pickup condition
    -> stop downward servo
    -> servo up to a known retract pose
    -> existing ordered continuation
```

The known retract pose is also the planning start pose for the existing continuation:

- Magazine pickup uses the magazine approach pose.
- Calibration pickup uses the calibration approach pose.

## Procedure contract

Extend `ServoUntilConditionProcedure` with optional retract configuration. A successful result must mean all of the following:

1. The pickup condition was detected.
2. Downward servo motion was stopped.
3. Upward servo retraction completed.
4. The configured retract position was reached within tolerance.

The caller must not execute the existing continuation unless the procedure returns success.

Conceptual caller flow:

```python
result = procedure.run(
    config=servo_config,
    retract_pose=approach_pose,
)

if not result.success:
    stop_motion()
    return False

return execute_existing_continuation()
```

## Retract behavior

For the current Z-axis pickup:

- Use the Z coordinate of the supplied retract pose as the servo retract target.
- Keep X, Y, Rx, Ry, and Rz unchanged throughout downward and upward servo motion.
- Start upward servo motion immediately after successful contact detection and downward servo stop.
- Monitor the live robot Z position while retracting.
- Stop upward servo motion when the retract Z is reached.
- Verify the final Z against a configurable tolerance.
- Enforce a maximum retract distance and retract timeout.
- Keep vacuum enabled throughout a successful pickup and retract.

The procedure must not attempt Cartesian correction of X, Y, or orientation. If those coordinates no longer match the known approach pose, return failure and leave recovery to the existing process error handling.

## Failure handling

Any failure must prevent the existing continuation from executing.

Failure cases include:

- downward servo start failure;
- pickup-condition timeout;
- pickup-condition read failure;
- cancellation, pause, or stop request;
- downward servo-stop failure or unconfirmed stop;
- upward servo start failure;
- current-position read failure during retract;
- retract timeout;
- maximum retract distance exceeded;
- upward servo-stop failure;
- final retract-position mismatch.

On failure:

1. Request `stop_servo_jog()` unconditionally when servo may be active.
2. Call `stop_motion()` if servo stopping fails or cannot be confirmed.
3. Cancel or discard any prepared continuation.
4. Return failure to the existing pickup/process flow.
5. Do not execute lateral transfer, calibration motion, or the remaining pickup sequence.

### Contact-timeout recovery policy

The default policy should be to stop at the current position and enter the existing error/recovery flow.

An optional controlled upward recovery may return the robot to the approach pose, but it must still return pickup failure. Successful recovery motion must never authorize the continuation because pickup contact was not confirmed.

## Continuation preplanning

Preplanning is an optimization to add after safe servo retraction works reliably.

- Prepare the existing continuation from the known retract pose while servo pickup is active.
- The preparation API must be plan-only: it must not queue, authorize, or start robot execution.
- Keep the prepared result local to the active pickup call when practical.
- If servo pickup or retract fails, cancel or discard the prepared result.
- If servo pickup and retract succeed, execute the prepared continuation.
- If preparation is incomplete, wait at the known retract pose.

The existing ordered-motion gates and endpoint verification remain unchanged.

## Diagnostics

Add focused timing and result logs for:

- downward servo start;
- pickup-condition detection;
- downward servo-stop request and result;
- retract start;
- retract target Z;
- live/final retract Z;
- upward servo-stop result;
- total procedure time;
- final success or precise failure reason;
- whether a prepared continuation was used or discarded.

## Verification

### Automated and simulated checks

Verify:

1. Successful contact retracts to the configured known pose.
2. Magazine pickup uses the magazine approach pose.
3. Calibration pickup uses the calibration approach pose.
4. Contact timeout never starts the continuation.
5. Sensor-read failure never starts the continuation.
6. Downward or upward servo failure never starts the continuation.
7. Retract timeout or position mismatch never starts the continuation.
8. Stop or pause during descent stops servo motion.
9. Stop or pause during retract stops servo motion.
10. A discarded preplan cannot be reused by a later pickup.

### Hardware verification order

1. Test downward servo stop without retraction.
2. Test upward servo retraction at reduced speed and clearance.
3. Verify stopping accuracy at the known retract Z.
4. Test magazine pickup without continuation execution.
5. Test calibration pickup without continuation execution.
6. Enable the existing continuation after successful retract verification.
7. Add concurrent plan-only preparation and measure the remaining idle time.
8. Inject or simulate failures and confirm that no continuation motion starts.

## Implementation order

1. Define retract configuration and extend the servo procedure result contract.
2. Implement guarded upward servo retraction and final-position verification.
3. Pass the magazine approach pose from the magazine pickup caller.
4. Pass the calibration approach pose from the calibration pickup caller.
5. Verify every servo/retract failure returns before the existing continuation.
6. Add targeted tests and controlled hardware checks.
7. Add plan-only continuation preparation if an idle interval remains.
8. Update engine and paint robot-system documentation for the final implemented behavior.
