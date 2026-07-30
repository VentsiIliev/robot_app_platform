# Paint Cycle Motion Optimization Plan

## Goal

Reduce the paint cycle toward 10-12 seconds without removing MoveIt from the variable workpiece paint path.

The workpiece can change each cycle and can be picked/dropped in different poses, so full joint trajectory caching is not a reliable primary strategy. The better direction is to overlap planning with execution, merge safe non-paint motions, and carry predicted joint branches between phases.

## Current Bottleneck Pattern

The current cycle is mostly serialized:

```text
execute move A
wait until reached
read current state
plan move B
execute move B
wait
plan move C
...
```

This creates avoidable idle time between phases, especially before paint path execution and during post-paint return.

## Target Pattern

Use predicted final states to plan ahead while the robot is still moving:

```text
plan segment A
execute segment A
while A is executing:
    plan segment B using A's expected final joint state
when A finishes:
    if live state matches predicted start:
        execute B immediately
    else:
        discard B and replan normally
```

The key requirement is to use the accepted trajectory's final joint positions as the predicted start state for the next plan, not only the Cartesian goal pose. This preserves the expected Joint 6 branch.

## Motion Phases

Keep semantic phase boundaries even if planning/execution is optimized:

```text
Segment A: approach / setup / plane change, tool off
Segment B: paint contour, tool on
Segment C: retract / restore original plane, tool off
Segment D: return / calibration / unwind, tool off
```

Tool state changes remain hard boundaries. The optimization is to remove planning and controller gaps around those boundaries where safe.

## Pump State Invariant

The vacuum pump state must remain a hard process constraint and must not be hidden inside motion optimization.

Required behavior:

```text
before pickup contact:
    pump ON

pickup -> transfer -> paint -> return/dropoff:
    pump stays ON

only after dropoff pose is reached and confirmed:
    pump OFF
```

Safe phase model:

```text
Pre-pickup approach:         pump OFF
Pickup contact/acquire:      pump ON before contact
All carried-workpiece moves: pump ON
Paint execution:             pump ON, paint tool state controlled separately
Dropoff reached:             pump OFF
Post-dropoff return/calib:   pump OFF
```

Any merged or prefetched motion that happens while the workpiece is held must preserve pump ON. Combining unwind/calibration return is safest after dropoff, when the workpiece is no longer held. Pump state changes should be explicit process phase events, not side effects of trajectory planning.

## Implementation Steps

1. Map current cycle timing
   - Add or inspect timing markers for pickup, pivot, plane change, move to paint start, paint path planning, paint execution, restore plane, unwind, and calibration return.
   - Separate robot execution time from planning time.

2. Define a predicted-final-state contract
   - For each accepted planned trajectory, expose:
     ```text
     final_joint_state
     final_tcp_pose
     final_joint6_branch
     duration
     ```
   - Store this state with the trajectory result.

3. Add prefetch planning
   - While one segment executes, plan the next segment from the previous segment's predicted final joint state.
   - Store the planned trajectory together with its expected start state.

4. Add execution guardrails
   - Before executing a prefetched trajectory, compare live robot state to the expected start state.
   - Execute immediately only when the state matches within tolerance.
   - Otherwise discard the prefetched plan and fall back to current blocking planning.

5. Start with low-risk prefetch
   - First target:
     ```text
     while moving to paint start -> pre-plan paint path
     ```
   - This can save most of the paint path planning time without changing the physical motion.

6. Prefetch post-paint return
   - While painting, plan the restore/return segment from the predicted final paint joint state.
   - Guard execution against actual final-state mismatch.

7. Merge safe setup motions
   - Combine:
     ```text
     pivot / change-plane / move-to-first-paint-point
     ```
     into one pre-paint setup trajectory where the tool is off.
   - Preserve the final paint-start pose exactly.

8. Merge safe exit motions
   - Combine:
     ```text
     last paint point -> restore plane/orientation -> return target
     ```
     where clearance permits.
   - Later, consider folding Joint 6 unwind into the return segment by choosing the calibration IK solution on the canonical Joint 6 branch.

9. Carry Joint 6 explicitly
   - Use the previous predicted final Joint 6 branch as the next segment start branch.
   - For calibration return, prefer a final IK solution with Joint 6 already unwound.
   - Reject prefetched execution if Joint 6 live state is not on the expected branch.

10. Measure incrementally
    - Step 1: prefetch paint path only.
    - Step 2: prefetch post-paint return while painting.
    - Step 3: merge setup motions.
    - Step 4: merge exit/unwind/calibration where safe.
    - Compare cycle timing and physical behavior after each step.

## Guardrails

Reject a prefetched plan and fall back to current behavior if any of these changed:

```text
live start joints differ too much
TCP pose differs too much
Joint 6 branch mismatch
workobject changed
tool changed
contour changed
planning scene changed
required pump state does not match the current process phase
pause/cancel occurred
robot reported an execution error
```

Suggested initial tolerances:

```text
joint start tolerance: 0.01-0.03 rad
TCP position tolerance: 1-2 mm
TCP orientation tolerance: 1-2 deg
Joint 6 branch tolerance: stricter than general joints
```

These values should be validated on hardware before relying on prefetch execution.

## Expected Payoff

Approximate savings if implemented safely:

```text
Prefetch paint planning:        ~1.5-3.0s
Prefetch post-paint return:     ~0.5-1.5s
Merge setup/exit motions:       ~2.0-4.0s
Combine unwind with return:     ~1.0-2.0s
```

This is the most realistic route toward a 10-12 second cycle while still allowing variable workpieces and variable pickup/dropoff poses.
