# Paint Percent-of-Profile Mode — Implementation Plan

## 1. Purpose

Add an optional paint trajectory speed mode in which the operator supplies one value:

```text
Paint speed = 1 ... 100%
```

In this mode, `100%` means the fastest validated, jerk-limited trajectory produced for the specific paint contour using the configured production joint limits. Lower percentages are deterministic time-scaled copies of that validated trajectory.

The mode must be removable and disabled by default. When it is disabled, the current velocity/acceleration behavior, request payload, ROS 2 planning path, optimizer selection, fallback behavior, and controller command must remain unchanged.

This plan covers changes in both repositories:

- Platform: `/home/ilv/Desktop/robot_app_platform`
- ROS 2 runtime: `/home/ilv/ros2_ws`

The mathematical background is described in `docs/paint_feed_manual_example_percent_only_bg-1.md`.

---

## 2. Scope

### In scope for the first production version

- An opt-in mode dedicated to paint-contour execution.
- A single operator paint-speed percentage.
- Generation of a trajectory-specific 100% profile by the existing Direct Contour IK → TOTG → Ruckig pipeline.
- Strict Ruckig success in the new mode.
- Deterministic scaling of an already validated 100% trajectory.
- Final dynamic and structural validation before dispatch.
- Explicit runtime diagnostics showing which mode was used.
- Unit, integration, simulation, and staged hardware verification.
- Immediate rollback by disabling the feature.

### Out of scope for the first version

- Displaying an exact source-contour feed in `mm/s`.
- Preserving `source_s_mm` through RTCP projection, IK, duplicate removal, and TOTG resampling.
- Replacing the generic trajectory optimizer architecture.
- Applying this mode to PTP, jog, pickup, drop-off, welding, or other non-paint motion.
- Dynamically changing the percentage after a trajectory has already been accepted by the controller.
- Treating `0%` as an infinitely slow trajectory.

---

## 3. Terminology and semantics

Use an explicit mode value rather than reinterpreting existing `vel` and `acc` fields:

```text
legacy
percent_profile
```

### `legacy`

The platform sends the existing request. ROS 2 follows the existing planning, optimization, fallback, and execution path without any new percentage-profile processing.

### `percent_profile`

ROS 2 builds and validates a 100% trajectory for the requested contour, then scales that completed trajectory using:

```text
p = paint_speed_percent / 100

time_from_start_p = time_from_start_100 / p
velocity_p        = velocity_100 * p
acceleration_p    = acceleration_100 * p^2
jerk_p            = jerk_100 * p^3
```

Jerk is not stored in `JointTrajectoryPoint`; its scaling follows from uniform time scaling of the same trajectory.

`paint_speed_percent` is valid in the range `1.0 ... 100.0`. A requested value of `0%` must be handled by the paint process as pause/stop/no-dispatch and must never be sent to the trajectory scaler.

The existing platform option `use_combined_paint_speed_control` is only a UI mapping from one slider to separate velocity and acceleration values. It is not equivalent to `percent_profile` mode. The two features must have distinct names and configuration fields.

---

## 4. Safety and compatibility invariants

The implementation is acceptable only if all of these invariants hold:

1. The feature is disabled by default on both sides.
2. An absent mode field is interpreted as `legacy`.
3. In `legacy`, the platform emits the same payload keys and values as before.
4. In `legacy`, ROS 2 calls the same functions with the same arguments as before.
5. Percentage-profile logic is not called from the legacy branch.
6. The new mode applies only to paint-contour execution.
7. Ruckig failure in the new mode rejects execution; it must not silently fall back to a non-jerk-limited TOTG trajectory.
8. Invalid percentage, missing velocities/accelerations, non-monotonic timestamps, limit violations, or non-finite values reject execution.
9. The unscaled 100% trajectory and every scaled trajectory retain the same ordered path endpoints.
10. Disabling the platform feature immediately restores the current operator controls and request behavior without requiring a ROS 2 rollback.

---

## 5. Proposed architecture

```text
Paint UI / settings
    |
    | legacy: existing vel + acc
    | percent_profile: mode + paint_speed_percent
    v
Platform paint process
    v
Ros2Robot / HTTP client adapter
    v
POST /execute/path
    v
ROS 2 request parser and runtime gateway
    v
Paint contour planning
    v
Direct Contour IK
    v
TOTG seed at production limits
    v
Ruckig smoothing (required)
    v
100% trajectory validation
    v
deterministic time scaling
    v
scaled trajectory validation
    v
FollowJointTrajectory
```

The percentage-profile calculation belongs in ROS 2 because ROS 2 owns IK, robot-model limits, TOTG, Ruckig, collision checking, and controller execution. The platform owns operator intent, persistence, UI presentation, and selection of the opt-in mode.

---

## 6. Transport contract

Extend the `/execute/path` JSON contract with optional fields:

```json
{
  "speed_mode": "percent_profile",
  "paint_speed_percent": 70.0
}
```

Compatibility rules:

- Do not add these keys when the platform feature is disabled.
- Missing `speed_mode` means `legacy`.
- `speed_mode="legacy"` ignores `paint_speed_percent` and uses existing `vel`/`acc` semantics.
- `speed_mode="percent_profile"` requires `paint_speed_percent` in `[1.0, 100.0]`.
- Unknown modes return a validation error before planning.
- Keep `vel` and `acc` accepted for old clients. In the new mode they must not ambiguously define the operator percentage.

Prefer extending the existing endpoint over adding a second endpoint because the contour, RTCP, IK, cancellation, blocking/non-blocking response, and execution-observation machinery are already centralized there. The explicit mode branch provides the required isolation.

---

## 7. Platform changes

### 7.1 Configuration

Add paint-system configuration with conservative defaults:

```python
paint_trajectory_speed_mode: str = "legacy"
paint_percent_profile_minimum_percent: float = 1.0
paint_percent_profile_maximum_percent: float = 100.0
```

Keep this separate from `use_combined_paint_speed_control`. During initial rollout, enable the new UI presentation only when `paint_trajectory_speed_mode == "percent_profile"`.

Candidate locations:

- `src/robot_systems/paint/processes/paint/config.py`
- Paint settings serializer and mapper
- `src/robot_systems/paint/applications/dashboard/config.py` for visibility/presentation only

If the mode is intended to be a commissioning flag rather than an operator-editable setting, define it in robot-system composition and do not expose it in ordinary process settings.

### 7.2 UI

In `legacy`, preserve the current controls exactly.

In `percent_profile`:

- Show one `Paint speed` control in percent.
- Hide or disable the independently editable paint acceleration control for contour speed.
- Clamp the editable value to the configured minimum and maximum.
- Do not show calculated `mm/s` in the first version.
- Make the active mode visible in a diagnostics or commissioning view.
- Add English and Bulgarian catalog entries for all new labels and errors.

Do not reuse `_resolved_velocity()` / `_resolved_acceleration()` as the new algorithm. Those methods implement the current combined-slider mapping, not time scaling of a computed trajectory.

### 7.3 Process and service contract

Carry an explicit paint motion options object or named arguments through the paint execution path. Avoid adding percentage-profile policy to generic views or models.

Suggested platform-side value object:

```python
@dataclass(frozen=True)
class PaintTrajectorySpeed:
    mode: str = "legacy"
    percent: float | None = None
```

Only paint contour execution should construct `percent_profile`. Approach, pickup, drop-off, jog, and other robot operations continue to use their current velocity/acceleration inputs.

### 7.4 Robot driver and HTTP adapter

Extend the paint contour call path through:

- `src/engine/robot/drivers/ros2_robot.py`
- `src/engine/robot/drivers/client_adapters/http_websocket.py`
- `src/engine/robot/drivers/client_adapters/fake.py`

The generic driver API may accept optional `speed_mode=None` and `paint_speed_percent=None`, but it must omit both payload keys when they are `None`. This omission is necessary for byte-for-byte-compatible legacy payload structure.

Update fakes to record the optional fields so platform tests can verify both branches without a running ROS backend.

### 7.5 Platform tests

Add tests proving:

- Default configuration selects legacy behavior.
- Legacy UI and saved settings retain separate velocity/acceleration semantics.
- Legacy HTTP payload contains no new fields.
- Percent mode includes the two new fields with the selected value.
- Invalid percentage is rejected before transport.
- `0%` invokes process stop/pause/no-dispatch behavior.
- Non-paint motion never opts into the new mode.
- Fake client behavior matches the real client signature.

---

## 8. ROS 2 runtime changes

### 8.1 Request parsing and propagation

Extend the real request path through these existing seams:

- `rest/api_support.py::parse_execute_path_request`
- `runtime_api/handlers.py::execute_path`
- `runtime_gateway/base.py`
- `runtime_gateway/local.py`
- `backend/i_robot_backend.py`
- `backend/moveit_robot_backend.py`
- Motion strategy/planning entry point used by `execute_path`

Use a normalized enum or constants internally. Do not pass unvalidated free-form mode strings deep into motion planning.

The parser must default missing mode to `legacy`. Validate mode-specific fields before enabling drives or beginning a planning generation.

### 8.2 Isolated mode branch

Create a dedicated component, for example:

```text
motion/execution/percent_profile_scaler.py
```

Responsibilities:

- Validate the requested percentage.
- Accept a fully timed and validated 100% `RobotTrajectory`.
- Deep-copy it.
- Scale timestamps, velocities, and accelerations.
- Preserve positions and joint names.
- Return scaling diagnostics.

It must not perform IK, collision checking, controller dispatch, or HTTP parsing.

At the orchestration seam:

```python
if speed_mode is LEGACY:
    return existing_path(...)

return percent_profile_path(...)
```

Keep the existing legacy statements together rather than inserting mode checks throughout the optimizer.

### 8.3 Building the 100% trajectory

For the first version, define 100% as:

1. The joint path returned by Direct Contour IK for the requested contour and current seed state.
2. TOTG time parameterization at configured production velocity and acceleration limits.
3. Successful Ruckig smoothing using configured production jerk limits.
4. Successful collision, FK/path, and dynamic validation.

Do not implement a second manual `dq/ds` retimer in the first version. TOTG already performs path time parameterization against joint velocity and acceleration constraints; Ruckig adds jerk-limited smoothing.

### 8.4 Strict Ruckig result

The existing `/apply_ruckig` service can return its TOTG seed when Ruckig fails. The new mode needs to know whether Ruckig actually succeeded.

Preferred change: extend or replace the optimization response with status metadata:

```text
success
optimizer_applied       # "RUCKIG" or "TOTG_FALLBACK"
fallback_used
message
trajectory
```

If changing `ApplyIPP.srv`, rebuild the package and update every generated client. Alternatively, add a new strict service dedicated to percentage-profile generation and leave `ApplyIPP.srv` untouched. Choose the separate service if changing the existing response would create compatibility risk for deployed clients.

In `percent_profile`, accept only `optimizer_applied == "RUCKIG"`. In `legacy`, preserve the current fallback policy.

### 8.5 Time-scaling algorithm

For every trajectory point and `p = percent / 100`:

```text
t_scaled = t_100 / p
v_scaled = v_100 * p
a_scaled = a_100 * p^2
```

Requirements:

- Use integer nanosecond arithmetic when practical to avoid timestamp rounding inversions.
- Preserve the first timestamp if it is zero.
- Ensure every later timestamp is strictly greater than the previous timestamp.
- Preserve positions exactly.
- Require complete velocity and acceleration arrays; do not silently synthesize them in production mode.
- Deep-copy the input and never mutate the cached/reference 100% trajectory.
- Scaling must be idempotent relative to the 100% source: changing from 70% to 50% must rescale the original 100% trajectory, not the already scaled 70% result.

### 8.6 Validation

Validate both the 100% trajectory and the scaled result.

Structural validation:

- At least two points.
- Joint-name and array dimensions match.
- Positions, velocities, accelerations, and timestamps are finite.
- Strictly increasing timestamps.
- Start and end conditions satisfy controller requirements.

Dynamic validation:

- Joint positions are within limits.
- Absolute velocity is within effective production velocity limits.
- Absolute acceleration is within effective production acceleration limits.
- Numerically estimated jerk is within effective production jerk limits plus a documented numerical tolerance.
- No excessive local timing gaps.

Path validation:

- Collision/state validity remains accepted for the joint positions.
- FK samples remain within the configured position and orientation tolerance of the intended contour.
- Confirm the effect of TOTG joint-space resampling and controller spline interpolation on TCP deviation.

Because uniform time scaling with `p <= 1` lowers velocity, acceleration, and jerk, the scaled trajectory should remain dynamically feasible if the 100% trajectory is valid. Validation is still required to detect malformed data and rounding errors.

### 8.7 Execution diagnostics

Include in logs and the execution response where possible:

```text
speed_mode
requested_percent
optimizer_applied
fallback_used
duration_100_s
duration_scaled_s
point_count
maximum velocity/acceleration/estimated jerk ratio by joint
validation result
```

Do not claim an `mm/s` feed until source-distance provenance is implemented.

### 8.8 ROS 2 tests

Unit tests for the scaler:

- 100% returns equivalent timing and dynamics.
- 50% doubles timestamps, halves velocity, and quarters acceleration.
- Positions and joint names are unchanged.
- Scaling always starts from the 100% input.
- `0`, negative, greater-than-100, NaN, and infinite inputs fail.
- Timestamp rounding remains strictly monotonic.
- Missing velocity or acceleration arrays fail.
- The input trajectory is not mutated.

Request/branch tests:

- Missing mode follows legacy behavior.
- Explicit legacy follows legacy behavior.
- Unknown mode is rejected.
- Percent mode requires a percentage.
- Legacy accepts existing clients and payloads.
- Ruckig failure remains a legacy fallback but is a percent-mode rejection.

Integration tests:

- Direct Contour IK → strict Ruckig → 100% validation → scaling → controller goal.
- Cancellation works during scaled execution.
- Blocking and non-blocking API responses retain their existing contract.
- Fake hardware and real-hardware backends report mode consistently.

---

## 9. Paint segment boundary decision

Before implementation, confirm what the current path request contains:

- Paint contour only, or
- Approach + paint contour, or
- Approach + paint contour + departure.

The percentage must apply only to motion during which paint feed semantics are intended. If the current request combines phases, choose one of these designs:

1. Split approach/paint/departure into separate controller goals, accepting a stop or controlled handoff at boundaries.
2. Preserve one controller goal but carry segment boundary indices and scale only the paint interval, then recompute dynamically valid transitions.
3. Explicitly define the percentage as applying to the complete combined motion.

Option 1 is simplest but may introduce an unwanted stop. Option 2 preserves continuity but is a separate trajectory-retiming problem and should not be hidden inside the initial implementation. Do not proceed until the desired production behavior at paint-on and paint-off boundaries is agreed.

---

## 10. Production limits

The first version should treat the effective limits loaded by the ROS robot model as production limits. This keeps one source of truth for TOTG and Ruckig.

Do not use illustrative limits from the background document as robot configuration. For example, the current Fairino configuration uses approximately `3.15–3.20 rad/s` maximum joint velocity, not the document's illustrative J6 value of `15 rad/s`.

If independent production margins are later required:

```text
velocity margin
acceleration margin
jerk margin
```

pass explicit effective limit maps to the available MoveIt TOTG and Ruckig overloads. The existing `ApplyIPP` request exposes velocity and acceleration scaling only, so an independent runtime jerk margin requires a ROS-side contract or implementation change.

---

## 11. Rollout phases

### Phase 0 — Baseline capture

- Record representative legacy request payloads.
- Save resulting trajectory duration, point count, optimizer logs, and controller goals.
- Select straight, curved, sharp RTCP-turn, short, and long paint contours.
- Record current failure/fallback behavior.

Exit criterion: repeatable baseline artifacts exist for regression comparison.

### Phase 1 — ROS 2 scaler and validation, no platform exposure

- Implement the isolated trajectory scaler.
- Add strict optimizer-result reporting.
- Add unit tests and an internal test/commissioning entry point.
- Keep the public mode disabled.

Exit criterion: offline trajectories pass scaling and validation tests at 100%, 70%, 50%, and the configured minimum.

### Phase 2 — Transport and platform feature flag

- Add optional transport fields.
- Propagate the mode through the runtime API and backend.
- Add platform configuration and fake-client coverage.
- Keep default mode `legacy`.

Exit criterion: legacy payload and execution regression tests are unchanged; opt-in requests reach the new branch.

### Phase 3 — UI integration

- Present a single paint-speed percentage only when the new mode is enabled.
- Add persistence, localization, and diagnostics.
- Ensure running-setting update rules remain explicit; do not silently retime an active controller goal.

Exit criterion: restart persistence and English/Bulgarian runtime language switching work, with no legacy UI changes when disabled.

### Phase 4 — Simulation/fake-hardware qualification

- Run representative contours.
- Compare 100%, 70%, and 50% durations and sampled dynamics.
- Verify cancellation, errors, and strict Ruckig rejection.
- Measure FK deviation along the timed/resampled trajectory.

Expected duration relationship, within timestamp tolerance:

```text
duration_70 ~= duration_100 / 0.70
duration_50 ~= duration_100 / 0.50
```

Exit criterion: all acceptance checks pass without controller warnings or fallback.

### Phase 5 — Staged hardware qualification

- Start with no paint flow and a conservative maximum percentage.
- Verify straight and low-curvature contours.
- Add sharp turns and representative production poses.
- Compare commanded and measured joint velocity/acceleration.
- Verify paint-on/off boundary behavior.
- Increase the allowed maximum only after review of logged limits and tracking error.

Exit criterion: approved production envelope and documented rollback procedure.

---

## 12. Acceptance criteria

### Legacy compatibility

- Feature default is off.
- Existing platform tests pass.
- Existing ROS 2 tests pass.
- Captured legacy request JSON is unchanged.
- Resulting legacy optimizer selection, fallback behavior, and controller goal are unchanged within existing nondeterminism.

### Percentage mode

- Only one operator percentage controls the paint trajectory.
- 100% is generated per concrete contour and seed state.
- Ruckig success is mandatory.
- Scaled timestamps and derivatives obey the defined equations.
- Dynamic, collision, and path validation pass before dispatch.
- No value is advertised as source `mm/s`.
- Invalid percentage or optimizer degradation fails safely with an actionable error.

### Operational rollback

- Switching configuration back to `legacy` requires no data migration.
- Old platform versions continue to work with the extended ROS 2 runtime.
- New platform versions work with legacy behavior when optional fields are omitted.

---

## 13. Verification commands

Platform:

```bash
python3 -m py_compile <each touched Python module>
python -m unittest <targeted platform test modules> -v
python tests/run_tests.py
```

ROS 2 workspace:

```bash
source /opt/ros/jazzy/setup.bash
cd /home/ilv/ros2_ws/eRob_moveit
colcon build --packages-select erob_moveit_runtime fairino5_v6_moveit2_config
colcon test --packages-select erob_moveit_runtime
colcon test-result --verbose
```

If a `.srv` contract changes, perform a clean package-level rebuild sufficient to regenerate interfaces, then verify that Python clients import the regenerated service successfully.

---

## 14. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Legacy behavior changes unintentionally | Default to legacy, omit new payload fields, branch once at the orchestration seam, add captured-payload regression tests |
| Ruckig silently falls back to TOTG | Return optimizer status and reject fallback in percent mode |
| Percentage is applied to approach/drop-off | Restrict construction of the mode to paint contour execution and decide segment boundaries before coding |
| Timestamp rounding creates duplicate times | Use nanosecond arithmetic and validate strict monotonicity |
| Controller spline deviates from the intended TCP path | FK-sample the timed path and qualify controller tracking on representative contours |
| 100% is too aggressive for production | Put conservative limits in the robot model and cap the UI maximum during rollout |
| Existing combined-speed UI is mistaken for the new mode | Use distinct configuration names and do not reuse its velocity/acceleration mapping as the algorithm |
| Active trajectory is retimed unexpectedly | Apply changes only to the next planned trajectory unless a separately designed live-speed override is introduced |
| Exact `mm/s` cannot be reconstructed | Do not display it in version 1; create a later source-provenance phase if required |

---

## 15. Final outcome: rejected and removed (2026-09-16)

This experiment is closed. The percent-profile mode was not robust enough for
production and has been removed from both the platform and the ROS 2 runtime.
Paint execution now has one speed path again: the pre-existing velocity and
acceleration percentage behavior. There is no `paint_trajectory_speed_mode`,
`speed_mode`, `paint_speed_percent`, nominal-100 feed setting, special
percent-profile IK policy, or percent-profile retimer left in the live code.

Unrelated work completed during the investigation—especially the cycle-start
Joint 6 unwind and navigation changes—was deliberately retained.

### Trial record

| Approach | Observed result | Decision |
|---|---|---|
| Ruckig as the 100% seed | Large Joint 6 rotations produced pathological timing, including a 5.476 s local interval, and fell back to TOTG. | Rejected for this contour. |
| TOTG seed plus percentage scaling | Safe scaling was simple, but it preserved the unwanted feed difference between straight and curved portions. | Insufficient. |
| Constant-feed retiming after TOTG | MoveIt's resampling changed the number of points, causing `constant feed requires matching IK and Cartesian samples`. | Rejected. |
| Direct Contour IK plus Cartesian arc-length timing | Produced nearly constant TCP feed while preserving IK positions, but exposed strong acceleration/jerk sensitivity at noisy curve and corner samples. | Promising visually, not robust physically. |
| Global sampled-jerk enforcement | A worst-sample correction of 4.487x reduced median feed to 12.846 mm/s. | Rejected as far too slow. |
| J6 derating to effective 0.8 rad/s and 0.8 rad/s² | Avoided the captured fault but took about 29.35 s and achieved only 28.849 mm/s median feed. | Rejected; production target is about 8 s. |
| Intermediate J6 limits around 1.2 rad/s and 1.2 rad/s² | Roughly 24.20 s at 37.747 mm/s median feed. | Rejected as too slow. |
| Relaxed bounded post-IK smoothing (0.50 mm / 0.50°) | Reduced curvature and reached 15.49 s / 65.17 mm/s median feed, but J6 peaked at 1.889 rad/s and faulted with `0x2214`, then `0x8400`. | Rejected as unsafe/unreliable. |
| Cubic controller interpolation (positions and velocities, no commanded accelerations) | Removed noisy quintic acceleration boundary conditions and some contours completed in 12–14 s, but difficult contours still faulted; one 10.50 s run reached J6 2.103 rad/s and jerk ratio 78.882. | Rejected as inconsistent. |
| Fritsch–Carlson reversal-aware cubic velocities with global acceleration correction | Prevented velocity overshoot at reversals, but one local constraint caused a 14.439x global stretch: 143.77 s and 3.169 mm/s median feed. | Rejected. |
| Local/neighbor-coupled interval correction | The initial local solver did not converge on the real 854-pose contour. A neighbor-coupled variant was implemented but not sufficiently qualified before the experiment was stopped. | Removed with the mode. |
| Circular/Bezier reconstruction | Considered as a way to regularize vision-created corners. The existing input already passes through adaptive cubic Bézier interpolation, and reliable arc recognition/reconstruction would be a separate geometry project rather than a timing-mode fix. | Not implemented. |

### Conclusions

- A percentage multiplier cannot create constant surface feed when its seed
  timing already slows differently on curves and straights.
- Dense vision-derived samples can turn a visually smooth curve into small
  direction changes. Retiming those samples alone shifts the problem into
  acceleration, jerk, vibration, and drive load.
- Meeting an approximately 8 s cycle while avoiding J6 over-current/tracking
  faults needs a better continuous geometric/rotation command upstream of IK,
  validated against explicit contact and orientation error bounds. It should be
  treated as a new path-quality project, not revived as this speed mode.
- Software limit compliance did not guarantee acceptable physical behavior:
  the table vibration and repeated J6 `0x2214`/`0x8400` faults are the decisive
  reasons the experiment was stopped.

## 16. Historical implementation and experiment notes

### Optimizer amendment

Hardware logs showed that Ruckig is unsuitable for the long Joint 6 rotations in
the production paint contour: it expanded a local interval to 5.476 seconds and
fell back to the valid seeded TOTG result. Percent-profile base generation has
therefore been changed to TOTG at 100%, followed by the same deterministic
percentage scaling. Earlier strict-Ruckig requirements in this planning document
are superseded by this amendment. Ruckig remains available for ordinary motion
outside percent-profile paint paths.

### Constant-feed amendment

Production testing showed that scaling TOTG preserved large TCP-feed differences
between straight and curved portions. Ordered percent-profile paint paths now use
the dense source-distance to Direct Contour IK correspondence directly. The
active ROS profile defines a stable nominal 100% TCP cruise feed. Percent-profile
paint no longer inherits TOTG interval timing. It parameterizes the unchanged IK
positions by Cartesian arc length, estimates `q'(s)` and `q''(s)` over a physical
millimetre window, and applies joint velocity/acceleration constraints through
forward and backward scalar-feed passes. This naturally creates start/stop ramps
and local curvature slowdowns without classifying lines, arcs, or corners. The
smoothed derivatives are used only for timing; every original IK joint position
is preserved. Final interval-rate and modeled-acceleration validation fails
closed. The operator percentage is applied only after this safe 100% profile is
built. Direct Contour IK is mandatory in this mode,
including for short contours, and failure is fatal because a Cartesian fallback
would lose the required source-distance correspondence.

The first vertical slice is implemented on both supported paint execution routes:

- Standalone `/execute/path` requests carry the optional mode and percentage;
  their current implementation retains the TOTG percentage profile.
- Production ordered motion chains carry the fields only on paint-contact `path`
  segments; attach, pickup, unwind, and return moves retain their existing timing.
- Legacy mode omits the new payload fields and follows the pre-existing optimizer
  behavior.
- Ordered percent-profile paint generates a nearly constant TCP-feed profile at
  100% and scales time, velocity, and acceleration once before dispatch.
- Concatenation preserves the independently timed paint member and does not
  re-time the combined attach/contact trajectory.
- First and unmatched second passes use the same mode.

The ROS runtime package was rebuilt and its installed ordered-planning files were
verified to contain the new path. Hardware qualification remains outstanding.

The current production log failure around 92.7% is a Direct Contour IK failure
that happens before optimization and percentage scaling. This mode makes no
claim to fix that separate path-feasibility issue.

### Hardware-smoothing amendment

The first arc-length hardware runs produced nearly constant TCP feed, but the
robot felt jerky at curves and corners. The retimer now estimates acceleration
change between consecutive timed IK samples and reports `jerk_ratio` and
`jerk_enforced`. A hardware trial of global sampled-jerk enforcement produced a
`4.487x` contour-wide correction and reduced median feed to `12.846 mm/s`, even
though final velocity and acceleration ratios were only `0.135` and `0.056`.
Dense vision/IK sampling noise therefore makes the single worst sampled jerk an
unsuitable global timing constraint. Enforcement is disabled while measurement
remains available. Velocity and acceleration remain hard constraints, and every
IK position remains unchanged. A future jerk solution must act locally or smooth
the geometric source rather than scaling the entire contour from one sample.

Separate hardware faults on Joint 6 showed that satisfying the previous
software limit was not sufficient for the physical drive. The active
`paint_contact` profile initially limited Joint 6 velocity to `3.0 rad/s`. A
later hardware run used 99.6% of the allowed acceleration and produced enough
vibration to shake the whole table. Joint 6 subsequently faulted at a measured
`1.507 rad/s`: drive error `0x2214` (motor over-current), followed by `0x8400`
(velocity error exceeds the limit). The profile now caps Joints 1–5 at
`2.5 rad/s²`. A safe-baseline run with effective Joint 6 caps of `0.8 rad/s`
and `0.8 rad/s²` completed the captured portion without a drive fault, but took
`29.35 s` and reached only `28.849 mm/s` median TCP feed. The next qualification
step raises Joint 6 to `1.5 rad/s` and `1.5 rad/s²` before margin, giving
effective caps of `1.2 rad/s` and `1.2 rad/s²`. This remains 20% below the
observed `1.507 rad/s` fault point. These limits affect paint-contact timing only;
legacy mode and non-paint motions keep their existing behavior. Hardware
qualification of these values remains required.

The production target remains approximately eight seconds, so a 24-second
limit-derived trajectory is not an acceptable final result. The net Joint 6
rotation is compatible with that target; the limiting factor is high-frequency
curvature in the dense vision/projection/IK command. Percent-profile Direct
Contour IK therefore has a separate bounded smoothing policy: eight passes at
`alpha=0.25`, with every adjusted sample FK-validated within `0.50 mm` and
`0.50 deg` of its requested pose. A violation rejects the candidate rather than
silently changing the path. This policy applies only to percent-profile paint;
legacy retains two passes and its existing `0.05 mm / 0.10 deg` smoothing bound.
The hardware trial reduced joint curvature from `0.03004` to `0.01693` and cut
duration to `15.49 s`, but produced `jerk_ratio=38.901`, a `1.889 rad/s` Joint 6
peak, and another `0x2214` over-current followed by `0x8400`. The relaxed
smoothing trial is therefore rejected and the percent-profile values are reset
to the established two-pass `0.05 mm / 0.10 deg` bounds. Reaching the eight-second
target requires regularizing the pivot projection's rotation sequence before IK,
with an explicit contact-error bound; post-IK deviation and limit increases are
not acceptable substitutes.

### Controller interpolation correction

The `1.889 rad/s` Joint 6 peak is not itself abnormal: the same hardware log
completed non-paint Joint 6 motions at `3.295` and `3.570 rad/s`. The paint
trajectory differed by supplying modeled acceleration at every one of more than
1,200 dense points, with a diagnostic jerk ratio of `38.901`. Jazzy's
`joint_trajectory_controller` uses quintic interpolation when position,
velocity, and acceleration are present, so those noisy acceleration boundary
conditions were converted into high-frequency torque demand. Percent-profile
retiming now still computes and validates acceleration internally, but sends
positions and smoothed velocities only. This selects cubic Hermite interpolation
in the controller. Path positions and timestamps are unchanged; legacy behavior
is unchanged. Hardware qualification is required before interpreting any
remaining drive fault as a velocity threshold.

The first cubic trial exposed a second boundary-condition issue: controller
velocities were still taken from a smoothed geometric derivative, which can stay
nonzero across a real joint direction reversal. Percent-profile output now uses
nonuniform Fritsch–Carlson knot velocities derived from the final timed joint
positions. A reversing joint receives exactly zero velocity at the reversal;
same-direction intervals use a weighted harmonic slope that prevents cubic
overshoot. Dynamics correction validates the actual start and end acceleration
of every cubic Hermite interval rather than only the smoothed path model.

The first implementation applied the worst cubic acceleration correction to the
entire contour. One isolated reversal therefore produced a `14.439x` global
stretch, `3.169 mm/s` median feed, and a `143.77 s` trajectory. This is rejected.
Cubic validation now iteratively stretches only violating intervals (and the
adjacent interval when a shared knot changes). Unaffected contour sections keep
their requested feed; the final velocity and cubic endpoint acceleration ratios
remain hard validated.

## 17. Superseded operational questions

1. Should `0%` mean pause, controlled stop, or simply remain unavailable in the UI?
2. Should a percentage change while running apply only to the next contour, the next pass, or require live speed override support?
3. What initial production cap should be used during hardware rollout: 25%, 50%, or another validated value?
4. Are current robot-model limits already production-safe, or do they require explicit derating before defining them as 100%?

---

## 18. Superseded later phase: source-feed reporting

If exact `F_100(s)` in `mm/s` becomes a requirement, implement it as a separate project. It requires:

- A precise definition of source arc length during RTCP orientation-only motion.
- `source_s_mm` or equivalent provenance on every projected pose.
- Preservation/remapping through IK smoothing and duplicate removal.
- Mapping through TOTG resampling.
- FK-based reconstruction or an explicit monotonic interpolation map.
- Tests for zero-source-distance orientation changes.

This later phase is not required to deliver meaningful operator percentage control and should not delay the isolated first version.
