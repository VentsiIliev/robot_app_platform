# Flange To TCP Calibration Plan

## Purpose

Implement calibration for the physical robot tool center point relative to the robot flange / MoveIt `ee_link`.

This is not camera-to-TCP calibration. Camera offsets such as `CAMERA_TO_TCP_X_OFFSET` and `CAMERA_TO_TCP_Y_OFFSET` remain separate and should not be reused for this feature.

Current behavior:

- The system effectively uses flange TCP / `tcp0` when `TOOL_0` is selected.
- ROS2 MoveIt accepts a numeric `tool` argument.
- The MoveIt runtime maps that numeric tool ID through `TOOL_ID_MAP` and `TOOL_REGISTRY`.
- The robot_app_platform stores the selected numeric tool in `ROBOT_TOOL`.

Target behavior:

- Calibrate the physical TCP offset from flange / `ee_link`.
- Store the calibrated transform in the ROS2 runtime tool registry.
- Select the calibrated tool from robot_app_platform through `ROBOT_TOOL`.
- All existing motion APIs continue passing `tool` normally.

## Terminology

| Term | Meaning |
|---|---|
| Flange | Robot mechanical end flange. In the MoveIt runtime this is treated as `ee_link` / `tcp0`. |
| TCP | Physical tool center point that should follow programmed paths. |
| `T_base_flange` | Current flange pose in robot base coordinates. |
| `T_flange_tcp` | Calibrated tool transform from flange to physical TCP. |
| Pivot point | Fixed sharp point in the robot base frame touched by the physical TCP during calibration. |
| Tool registry | ROS2 runtime `TOOL_REGISTRY` in `runtime.yaml`. |

## Existing Integration Points

### ROS2 MoveIt Runtime

Primary files:

- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/fairino5_v6_moveit2_config/config/runtime.yaml`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/robot_controller.py`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/backend/moveit_robot_backend.py`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/motion/planning/planner_utils.py`

Relevant current behavior:

- `TOOL_REGISTRY` stores `[x, y, z, rx, ry, rz]` tool transforms in millimeters and degrees.
- `TOOL_ID_MAP` maps numeric API IDs to registry keys.
- `MoveItRobotBackend.move_liner()` and `move_ptp()` call `node.get_tool_transform(tool)`.
- Planning removes the tool offset before solving for `ee_link`.

### robot_app_platform

Primary files:

- `src/engine/robot/configuration/robot_settings.py`
- `src/engine/robot/interfaces/i_robot_service.py`
- `src/engine/robot/services/motion_service.py`
- `src/applications/robot_settings/`
- target robot-system wiring under `src/robot_systems/<system>/`

Relevant current behavior:

- `RobotSettings.robot_tool` selects the numeric tool ID.
- Motion calls already pass `tool` to the robot service.
- No platform-level flange-to-TCP calibration service currently exists.

## Calibration Method

Use pivot calibration.

The operator keeps the real tool tip touching one fixed physical point, then captures multiple robot flange poses with different wrist orientations.

For every sample:

```text
T_base_flange_i = [R_i, t_i]
```

The fixed pivot constraint is:

```text
R_i * p_flange_tcp + t_i = p_base_pivot
```

Unknowns:

```text
p_flange_tcp = [x, y, z]
p_base_pivot = [x, y, z]
```

Linear least-squares form:

```text
[R_i  -I] [p_flange_tcp] = -t_i
          [p_base_pivot]
```

Use at least 6 samples. Prefer 8-12 samples with meaningful wrist-angle variation.

Initial implementation should solve translation only:

```text
T_flange_tcp = [x, y, z, 0, 0, 0]
```

Do not invent orientation calibration unless the fixture and measurement workflow provide enough information to solve it reliably.

## Implementation Steps

### 1. Confirm Current Pose Semantics

Status: Complete.

Verify what `/position/current` returns when different tools are selected.

Required answer:

- Does it return flange / `ee_link` pose?
- Or does it return the currently selected TCP pose?

If it returns current TCP pose, add or expose a ROS2 runtime endpoint that always returns flange pose.

Finding:

- `/position/current` returns the selected runtime TCP pose, not raw flange pose.
- In the Fairino backend, `/cartesian_position` is sourced from the native flange pose.
- `RobotMonitor` then applies `T_ee_link @ T_tool` before storing `cartesian`, so callers see the selected TCP.
- This means pivot TCP calibration must not use `/position/current` when a calibrated/nonzero tool is active.

Implemented:

- `RobotMonitor` now stores the unmodified source pose as `cartesian_source`.
- `MoveItRobotBackend.get_current_flange_position()` returns `cartesian_source`.
- REST now exposes `GET /position/flange`.
- Existing `GET /position/current` behavior is unchanged.

Changed files:

- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/status/robot_monitor.py`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/backend/i_robot_backend.py`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/backend/moveit_robot_backend.py`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/rest_server.py`

Suggested endpoint:

```text
GET /position/flange
```

Response:

```json
{
  "success": true,
  "position": [x, y, z, rx, ry, rz]
}
```

This endpoint should ignore `TOOL_REGISTRY` and report the raw flange / `ee_link` pose.

### 2. Add ROS2 Runtime Tool Registry Update Support

Status: Complete.

Add a runtime API for reading and updating tool transforms.

Suggested endpoints:

```text
GET /tool/registry
POST /tool/registry/<tool_id>
```

Example update payload:

```json
{
  "name": "TOOL_1",
  "transform": [12.34, -4.56, 78.9, 0.0, 0.0, 0.0],
  "persist": true
}
```

Rules:

- Validate transform length is exactly 6.
- Validate all values are finite numbers.
- Persist only to the active robot runtime YAML/profile.
- Reload or update the in-memory `TOOL_REGISTRY` used by `RobotController.get_tool_transform()`.
- Return the final tool mapping after update.

Do not require a ROS2 restart for in-memory use. A restart may still be acceptable for verifying persisted config.

Implemented:

- Added `config.get_tool_registry_snapshot()`.
- Added `config.update_tool_registry(tool_id, name, transform, persist=False)`.
- Added `GET /tool/registry`.
- Added `POST /tool/registry/<tool_id>`.
- Updates mutate the in-memory `TOOL_REGISTRY` and `TOOL_ID_MAP` dictionaries in place, so `RobotController.get_tool_transform()` sees the new transform immediately.
- When `persist=true`, the active runtime config path is written:
  - active profile `runtime.yaml` when `ACTIVE_PROFILE` is configured
  - base `runtime.yaml` otherwise

Validation now enforced:

- `tool_id` must be a non-negative integer.
- `name`, when provided, must be non-empty and contain only letters, numbers, and underscores.
- `transform` must be exactly six finite numeric values.

Implemented API:

```text
GET /tool/registry
```

Returns:

```json
{
  "success": true,
  "tool_registry": {
    "TOOL_0": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "TOOL_1": [12.34, -4.56, 78.9, 0.0, 0.0, 0.0]
  },
  "tool_id_map": {
    "0": "TOOL_0",
    "1": "TOOL_1"
  },
  "active_runtime_config_path": "/path/to/runtime.yaml"
}
```

```text
POST /tool/registry/<tool_id>
```

Example payload:

```json
{
  "name": "TOOL_1",
  "transform": [12.34, -4.56, 78.9, 0.0, 0.0, 0.0],
  "persist": true
}
```

Changed files:

- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/config.py`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/rest_server.py`

Verification:

- `python3 -m py_compile` passed for the touched ROS2 runtime files.
- A standalone helper import/runtime check could not run in the current shell because `python3` cannot import the existing `yaml` dependency, even after sourcing the ROS workspace. This appears to be an environment issue outside this change because `config.py` already depended on PyYAML before Step 2.

Finding:

- Persistence uses a targeted text update for only the top-level `TOOL_REGISTRY` and `TOOL_ID_MAP` blocks. Comments and formatting elsewhere in the active runtime YAML are preserved.
- Comments inside the replaced `TOOL_REGISTRY` or `TOOL_ID_MAP` blocks are not preserved. Keep explanatory comments immediately above those blocks.
- The ROS workspace had unrelated dirty files before/during this step. Step 2 intentionally touched only `config.py` and `rest_server.py`.

### 3. Add Platform Tool TCP Calibration Data Types

Status: Complete.

Add narrow data structures under engine robot calibration.

Suggested file:

```text
src/engine/robot/calibration/tool_tcp_calibration_data.py
```

Suggested types:

```python
@dataclass(frozen=True)
class ToolTcpSample:
    pose: list[float]


@dataclass(frozen=True)
class ToolTcpCalibrationResult:
    tool_offset: list[float]
    pivot_point: list[float]
    residual_rms_mm: float
    residual_max_mm: float
    sample_count: int
```

Keep these data types free of Qt and robot-system-specific imports.

Implemented:

- Added `ToolTcpSample`.
- Added `ToolTcpCalibrationResult`.
- Added `Pose6` and `Point3` type aliases.
- Added construction helpers that normalize numeric sequences to immutable tuples.
- Added `to_dict()` methods for UI/API serialization.
- Validation rejects wrong-length poses/points and non-finite values.

Changed files:

- `src/engine/robot/calibration/tool_tcp_calibration_data.py`

Verification:

- `python3 -m py_compile src/engine/robot/calibration/tool_tcp_calibration_data.py` passed.

### 4. Add Platform Solver

Status: Complete.

Add the numeric least-squares solver in engine code.

Suggested file:

```text
src/engine/robot/calibration/tool_tcp_pivot_solver.py
```

Responsibilities:

- Convert `[x, y, z, rx, ry, rz]` flange poses into rotation matrices and translations.
- Build the least-squares system.
- Solve for `p_flange_tcp` and `p_base_pivot`.
- Calculate per-sample residuals.
- Return RMS and max residual.

Validation:

- Require at least 4 samples technically, but enforce 6 as the product default.
- Reject degenerate samples with insufficient orientation variation.
- Reject non-finite input.
- Return clear error messages for operator correction.

Implemented:

- Added `solve_tool_tcp_pivot(samples, min_samples=6)`.
- Accepts either `ToolTcpSample` instances or raw 6-value pose sequences.
- Uses `R = Rz * Ry * Rx` for `[rx, ry, rz]` degrees, matching the existing tool-frame motion convention.
- Solves `[R_i -I] [p_flange_tcp, p_base_pivot] = -t_i` via `np.linalg.lstsq`.
- Returns `ToolTcpCalibrationResult` with:
  - `tool_offset = [x, y, z, 0, 0, 0]`
  - `pivot_point`
  - RMS residual
  - max residual
  - sample count
- Rejects fewer than 6 samples by default.
- Rejects rank-deficient/degenerate orientation sets.
- Rejects non-finite pose values.

Changed files:

- `src/engine/robot/calibration/tool_tcp_pivot_solver.py`
- `tests/engine/robot/test_tool_tcp_pivot_solver.py`

Verification:

- `python3 -m unittest tests/engine/robot/test_tool_tcp_pivot_solver.py -v` passed.
- `python3 -m py_compile src/engine/robot/calibration/tool_tcp_calibration_data.py src/engine/robot/calibration/tool_tcp_pivot_solver.py tests/engine/robot/test_tool_tcp_pivot_solver.py` passed.

### 5. Add Platform Calibration Service

Status: Complete.

Add an engine-level service that owns the calibration workflow.

Suggested file:

```text
src/engine/robot/calibration/tool_tcp_calibration_service.py
```

Responsibilities:

- Depend on `IRobotService` for pose capture.
- Depend on a small tool-registry client/adapter for saving to ROS2 runtime.
- Store captured samples in memory for the current session.
- Provide methods:

```python
start(tool_id: int) -> None
capture_sample() -> ToolTcpSample
clear_samples() -> None
solve() -> ToolTcpCalibrationResult
save(result: ToolTcpCalibrationResult) -> tuple[bool, str]
stop() -> None
```

The service should not import Qt.

Implemented:

- Added `ToolTcpCalibrationService`.
- The service manages one manual calibration session:
  - `start(tool_id)` validates and selects the target tool ID.
  - `capture_sample()` reads the current flange pose and stores a `ToolTcpSample`.
  - `clear_samples()` resets captured samples and any solved result.
  - `solve()` calls `solve_tool_tcp_pivot(...)` and stores the latest result.
  - `save(result=None)` writes the solved offset through an injected tool-registry adapter.
  - `stop()` marks the session stopped and asks the robot service to stop motion when available.
- The service is Qt-free and ROS-free.
- The concrete ROS2 REST adapter is intentionally deferred to Step 6.
- Flange-pose capture supports:
  - explicit `flange_pose_provider` callable, preferred for the real `/position/flange` path
  - `robot_service.get_current_flange_position()` when available
  - `robot_service.get_current_position()` fallback for tests or flange-only robots

Changed files:

- `src/engine/robot/calibration/tool_tcp_calibration_service.py`
- `tests/engine/robot/test_tool_tcp_calibration_service.py`

Verification:

- `python3 -m unittest tests/engine/robot/test_tool_tcp_calibration_service.py tests/engine/robot/test_tool_tcp_pivot_solver.py -v` passed.
- `python3 -m py_compile src/engine/robot/calibration/tool_tcp_calibration_data.py src/engine/robot/calibration/tool_tcp_pivot_solver.py src/engine/robot/calibration/tool_tcp_calibration_service.py tests/engine/robot/test_tool_tcp_calibration_service.py tests/engine/robot/test_tool_tcp_pivot_solver.py` passed.

Finding:

- The existing platform `IRobotService` does not expose a flange-pose method. The service therefore accepts a narrow `flange_pose_provider` so the upcoming ROS2 REST client can use `GET /position/flange` without changing the global robot service interface yet.

### 6. Add ROS2 Tool Registry Client In Platform

Status: Complete.

Create a small adapter for the ROS2 REST API.

Suggested file:

```text
src/engine/robot/calibration/ros_tool_registry_client.py
```

Responsibilities:

- Call `GET /tool/registry`.
- Call `POST /tool/registry/<tool_id>`.
- Return typed success/failure results.
- Keep network errors explicit.

Do not hide save failures. A calibration result that cannot be persisted must be reported as not saved.

Implemented:

- Added `RosToolRegistryClient`.
- Supports:
  - `get_tool_registry()` -> `GET /tool/registry`
  - `update_tool(tool_id, name, transform, persist=...)` -> `POST /tool/registry/<tool_id>`
  - `get_current_flange_position()` -> `GET /position/flange`
- Normalizes posted transform values to floats.
- Returns `(False, message)` for save/network/server failures.
- Returns `None` for unavailable or invalid registry/flange-pose reads.
- Keeps network errors explicit through logging and return values.

Changed files:

- `src/engine/robot/calibration/ros_tool_registry_client.py`
- `tests/engine/robot/test_ros_tool_registry_client.py`

Verification:

- `python3 -m unittest tests/engine/robot/test_ros_tool_registry_client.py tests/engine/robot/test_tool_tcp_calibration_service.py -v` passed.
- `python3 -m py_compile src/engine/robot/calibration/ros_tool_registry_client.py src/engine/robot/calibration/tool_tcp_calibration_service.py tests/engine/robot/test_ros_tool_registry_client.py tests/engine/robot/test_tool_tcp_calibration_service.py` passed.

Finding:

- The adapter includes `get_current_flange_position()` so `ToolTcpCalibrationService` can receive `flange_pose_provider=client.get_current_flange_position` during wiring.

### 7. Add Calibration App Tool TCP Tab

Status: Complete.

Decision:

- Do not add a separate `ToolTcpCalibration` application.
- Add a dedicated Tool TCP tab/panel inside the existing Calibration application.

Reason:

- The operator already uses Calibration for robot/camera calibration workflows.
- Flange-to-TCP pivot calibration is another calibration workflow, not a standalone production tool.
- Reusing the existing Calibration app avoids another shell entry and keeps related calibration actions together.

Follow the application MVC pattern:

- extend the existing calibration service interface narrowly
- model delegates Tool TCP actions to the service
- view emits user actions only
- controller runs blocking save/solve operations off the UI thread if needed
- no Qt in model/service

Minimal controls:

- Tool ID selector
- Start / Clear
- Capture Sample
- Solve
- Save To Tool Registry
- Result display: `x`, `y`, `z`, RMS residual, max residual

Implemented:

- Extended the existing calibration app service interface with Tool TCP actions:
  - `start_tool_tcp_calibration(tool_id)`
  - `capture_tool_tcp_sample()`
  - `solve_tool_tcp_calibration()`
  - `save_tool_tcp_calibration()`
  - `clear_tool_tcp_calibration()`
- Added model delegation for those actions.
- Added a dedicated Tool TCP tab to the existing Calibration application:
  - tool ID selector
  - start
  - capture sample
  - solve
  - save
  - clear
  - result label for offset and residuals
- Routed view signals through the existing controller.
- Kept capture/solve/save calls off the UI thread through the existing `QThread + _Worker` pattern.
- Added a dedicated solve result handler because solve returns `(ok, message, payload)`.
- Added application-service delegation to the engine `ToolTcpCalibrationService` when configured.
- Added compatibility implementations in `calibration_v2` service classes because they inherit the shared calibration service interface.
- Do not add a new `ApplicationSpec`.

Changed files:

- `src/applications/calibration/service/i_calibration_service.py`
- `src/applications/calibration/model/calibration_model.py`
- `src/applications/calibration/service/calibration_application_service.py`
- `src/applications/calibration/service/stub_calibration_service.py`
- `src/applications/calibration/view/calibration_phase_tabs.py`
- `src/applications/calibration/view/calibration_controls_panel.py`
- `src/applications/calibration/view/calibration_view.py`
- `src/applications/calibration/controller/calibration_controller.py`
- `src/applications/calibration_v2/service/calibration_application_service.py`
- `src/applications/calibration_v2/service/stub_calibration_service.py`
- `tests/applications/calibration/test_calibration_model.py`
- `tests/applications/calibration/test_calibration_service.py`

Verification:

- `python3 -m py_compile` passed for the touched Calibration modules.
- `python3 -m unittest tests.applications.calibration.test_calibration_model tests.applications.calibration.test_calibration_service tests.engine.robot.test_tool_tcp_pivot_solver tests.engine.robot.test_tool_tcp_calibration_service tests.engine.robot.test_ros_tool_registry_client -v` passed, 57 tests.

Findings:

- The active Paint/Glue/Welding robot-system wiring uses legacy `src.applications.calibration`, not `src.applications.calibration_v2`.
- Step 7 was therefore implemented as a new `Tool TCP` tab in the existing legacy Calibration app.
- The Tool TCP controls are visible now, but they will report "Tool TCP calibration is not configured" until Step 8 wires `ToolTcpCalibrationService` into the target robot system's existing Calibration application service.
- A sample table was deferred. The current UI logs each captured flange pose and shows the solved result/residuals. A table can be added later if operators need sample-by-sample review or deletion.

### 8. Wire Into Target Robot System

Status: In progress.

For the active system, update existing Calibration application wiring under:

```text
src/robot_systems/<system>/application_wiring.py
```

Use the existing robot service:

```python
robot_service = robot_system.get_optional_service(CommonServiceID.ROBOT)
```

Use robot settings for the default target tool:

```python
robot_config = robot_system.get_settings(CommonSettingsID.ROBOT_CONFIG)
default_tool_id = int(robot_config.robot_tool)
```

Additional active-tool requirement:

- `ROBOT_TOOL` must be pushed to the ROS2 runtime as the active status TCP before platform code trusts `get_current_position()`.
- Motion requests already pass numeric `tool`, but many platform paths use current pose as the start/reference pose.
- Therefore `/position/current` and motion requests must use the same active tool.
- For Fairino, calibrated registry tools represent `flange -> TCP`, not `ee_link -> TCP`.
- The runtime must use `flange -> TCP` directly for `/position/current`, and convert it to `ee_link -> TCP` only when building MoveIt planning requests.

Implemented current-pose synchronization fix:

- Added ROS2 runtime active-tool selection:
  - `GET /tool/active`
  - `POST /tool/active` with `{"tool_id": 1}` or `{"tool_name": "TOOL_1"}`
- `POST /tool/active` resolves numeric IDs through `TOOL_ID_MAP` and calls `RobotController.set_tool(...)`.
- `RobotController.set_tool(...)` now records `active_tool_name`.
- Updating a tool registry entry refreshes the monitor transform when that tool is already active.
- Platform `FairinoRos2Client` now calls `POST /tool/active` before `move_cartesian`, `move_liner`, and `move_ptp`.
- Platform `create_robot_service(...)` pushes configured `ROBOT_TOOL` to the robot driver before starting state monitoring, so `/position/current` is aligned from startup.
- Fairino runtime adapter now separates:
  - monitor transform: `flange -> TCP`
  - planning transform: `ee_link -> TCP = inverse(flange -> ee_link) * flange -> TCP`
- `RobotController` now tracks both `T_monitor_tool` and planning `T_tool`.

Changed files:

- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/config.py`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/backend/runtime_adapter.py`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/robot_controller.py`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/rest_server.py`
- `src/engine/robot/interfaces/i_robot.py`
- `src/engine/robot/drivers/fairino/fairino_ros2_client.py`
- `src/engine/robot/services/robot_service_factory.py`
- `tests/engine/robot/test_fairino_ros2_client.py`

Verification:

- `python3 -m py_compile` passed for the touched ROS2 runtime files.
- `python3 -m py_compile` passed for the touched platform files.
- `python3 -m unittest tests.engine.robot.test_fairino_ros2_client tests.applications.calibration.test_calibration_model tests.applications.calibration.test_calibration_service tests.engine.robot.test_tool_tcp_pivot_solver tests.engine.robot.test_tool_tcp_calibration_service tests.engine.robot.test_ros_tool_registry_client -v` passed, 64 tests.

### 9. Persist Selected Tool In robot_app_platform

Status: In progress.

After saving calibrated `TOOL_1`, set platform robot config:

```json
"ROBOT_TOOL": 1
```

This can initially remain manual through the existing Robot Settings UI.

Later improvement:

- The calibration app can offer `Set As Active Tool`, which updates `ROBOT_TOOL` through `SettingsService`.

Jog/current-pose correction:

- Platform jog must not use camera/tool target-point dropdowns or target-point offsets.
- With calibrated Tool TCP active, `get_current_position()` already represents the configured tool TCP.
- Jog now reads the current configured-tool TCP pose, applies the requested delta in that pose's tool frame, and commands the resulting TCP pose with the configured `ROBOT_TOOL`.
- The reusable jog frame selector is no longer populated or used.
- `RobotJogService` now reports no available jog frames and ignores `set_frame(...)`.
- App-level jog no longer uses the driver's native incremental jog preference; it always commands the resolved current-pose-plus-delta TCP target.
- Targeting definitions remain available for path planning/pick workflows, but no longer influence jog commands.

Changed files:

- `src/applications/base/robot_jog_service.py`
- `src/applications/base/robot_jog_service_builder.py`
- `src/applications/base/jog_controller.py`
- `src/applications/base/robot_jog_widget.py`
- `tests/applications/base/test_robot_jog_service.py`

Verification:

- `python3 -m py_compile src/applications/base/robot_jog_service.py src/applications/base/robot_jog_service_builder.py src/applications/base/jog_controller.py src/applications/base/robot_jog_widget.py tests/applications/base/test_robot_jog_service.py` passed.
- `python3 -m unittest tests.applications.base.test_robot_jog_service tests.engine.robot.test_motion_service tests.engine.robot.test_fairino_ros2_client -v` passed, 34 tests.

ZeroErr frame finding:

- `EE_LINK` is still the correct MoveIt planning/FK/IK link and should remain `ee_link`.
- `COLLISION_TIP_LINK` is only used by collision/dynamics monitoring; it does not drive TCP calibration or `/position/current`.
- The ZeroErr paint URDF has `Link_6 -> ee_link` as a fixed frame rotation and `ee_link -> tool0` as an identity fixed tool frame.
- `zeroerr_state_publisher.py` previously hardcoded `/cartesian_position` from `base_link -> ee_link`.
- Link_6 is co-located with `ee_link`, but its axes are rotated. With the current `TOOL_1` values, interpreting the offset in `Link_6` made the visualized TCP point back toward the robot base.
- Paint runtime therefore keeps `CARTESIAN_SOURCE_LINK: ee_link`, and the active ZeroErr paint tool registry is treated as `ee_link -> TCP`.
- `ZeroErrRuntimeAdapter` still supports flange-based registry transforms when `CARTESIAN_SOURCE_LINK` is explicitly set to `WRIST_LINK`, but the paint profile does not use that mode.
- Launch files now read `COLLISION_TIP_LINK` from runtime config instead of hardcoding `tool0`.

Changed files:

- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/zeroerr/scripts/zeroerr_state_publisher.py`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/zeroerr/config/runtime.yaml`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/zeroerr/config/paint/runtime.yaml`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/zeroerr/launch/demo.launch.py`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/zeroerr/launch/ethercat_only.launch.py`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/config.py`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/backend/runtime_adapter.py`

Verification:

- `python3 -m py_compile /home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/zeroerr/scripts/zeroerr_state_publisher.py /home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/zeroerr/launch/demo.launch.py /home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/zeroerr/launch/ethercat_only.launch.py /home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/config.py /home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/backend/runtime_adapter.py` passed.

Active TCP RViz visualization:

- The runtime now publishes the current active TCP as a TF frame named `active_tcp`.
- The runtime also publishes `/active_tool_markers` as a `visualization_msgs/MarkerArray`.
- The marker includes:
  - yellow sphere at the active TCP
  - red/green/blue axis lines showing active TCP orientation
  - text label with the active tool name, for example `TOOL_1 active TCP`
- The marker now also includes:
  - grey sphere at the Cartesian source frame
  - yellow line from source frame to active TCP
  - text suffix with the source-to-TCP distance in millimeters
- This visualization uses the same monitored current TCP pose returned by `/position/current`, so it reflects the active configured tool.
- The ZeroErr RViz config now includes an `Active TCP` display for `/active_tool_markers`.

Changed files:

- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/robot_controller.py`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/config.py`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/zeroerr/config/moveit.rviz`

Verification:

- `python3 -m py_compile /home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/robot_controller.py /home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/config.py` passed.
- `python3 -m py_compile /home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/robot_controller.py` passed after adding the source-to-TCP diagnostic markers.

First-jog active-tool safety fix:

- Finding: platform jog read `get_current_position()` before the configured tool had necessarily been activated in ROS2.
- This meant the first jog after startup could compute a target from Tool 0 current pose, then execute it as Tool 1 when `move_ptp(... tool=1 ...)` activated the tool.
- `FairinoRos2Robot.set_active_tool()` now delegates to `FairinoRos2Client.set_active_tool()`. Before this, startup active-tool sync called the interface default and did nothing.
- `IRobotService` and `RobotService` now expose `set_active_tool(tool)`.
- `RobotService.set_active_tool()` refreshes the cached state immediately after the driver accepts the active tool.
- `RobotJogService` now activates the configured tool before reading current position and aborts the jog if activation fails.
- ROS2 `RobotMonitor.set_tcp_transform(...)` recomputes the cached current TCP immediately from the last source pose when `/tool/active` changes the active tool.

Changed files:

- `src/applications/base/robot_jog_service.py`
- `src/engine/robot/interfaces/i_robot_service.py`
- `src/engine/robot/services/robot_service.py`
- `src/engine/robot/services/robot_state_manager.py`
- `src/engine/robot/drivers/fairino/fairino_ros2_robot.py`
- `tests/applications/base/test_robot_jog_service.py`
- `tests/engine/robot/test_robot_service.py`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/status/robot_monitor.py`
- `/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/robot_controller.py`

Verification:

- `python3 -m py_compile src/applications/base/robot_jog_service.py src/engine/robot/interfaces/i_robot_service.py src/engine/robot/services/robot_service.py src/engine/robot/services/robot_state_manager.py src/engine/robot/drivers/fairino/fairino_ros2_robot.py tests/applications/base/test_robot_jog_service.py tests/engine/robot/test_robot_service.py` passed.
- `python3 -m py_compile /home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/status/robot_monitor.py /home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/erob_moveit_runtime/scripts/robot_controller.py` passed.
- `python3 -m unittest tests.applications.base.test_robot_jog_service tests.engine.robot.test_robot_service tests.engine.robot.test_fairino_ros2_client -v` passed, 28 tests.

Initial state active-tool retry fix:

- Finding: the first fix still allowed initial platform state to report the wrong tool if the one-shot startup sync happened before ROS2 accepted the active tool.
- The one-shot factory call also failed silently when the robot bridge was not ready.
- `RobotStateManager` now owns configured active-tool synchronization through an `active_tool_getter`.
- Before each state poll publishes or caches a pose, it activates the configured tool if it has not already synced that tool.
- If ROS2 rejects the configured tool, the state becomes `tool_mismatch`, the cached pose is cleared, and no Tool 0 pose is published as if it were valid for Tool 1.
- The state manager retries active-tool synchronization on subsequent polls.
- `create_robot_service(...)` passes a live `ROBOT_TOOL` getter and performs one synchronous refresh before starting the background monitor.

Changed files:

- `src/engine/robot/services/robot_state_manager.py`
- `src/engine/robot/services/robot_service_factory.py`
- `tests/engine/robot/test_robot_state_manager.py`

Verification:

- `python3 -m py_compile src/engine/robot/services/robot_state_manager.py src/engine/robot/services/robot_service_factory.py tests/engine/robot/test_robot_state_manager.py` passed.
- `python3 -m unittest tests.engine.robot.test_robot_state_manager tests.applications.base.test_robot_jog_service tests.engine.robot.test_robot_service tests.engine.robot.test_fairino_ros2_client -v` passed, 43 tests.

### 10. Verification

#### Unit Tests

Add solver tests using synthetic data.

Suggested tests:

- known offset with noise-free samples solves exactly
- known offset with small noise produces low RMS residual
- insufficient samples are rejected
- degenerate orientation set is rejected
- non-finite values are rejected

#### Runtime Checks

1. Start ROS2 runtime.
2. Confirm `TOOL_0` is zero.
3. Capture samples while physical TCP touches fixed pivot.
4. Solve and inspect residuals.
5. Save to `TOOL_1`.
6. Set `ROBOT_TOOL = 1`.
7. Command a small Cartesian move and verify the physical TCP, not flange, follows the target.
8. Restart ROS2 runtime and confirm persisted `TOOL_1` is still loaded.

#### Acceptance Criteria

- Calibration result persists in the ROS2 runtime tool registry.
- Platform motion commands do not need new tool-specific APIs.
- `ROBOT_TOOL` selects the calibrated tool.
- Residual RMS is visible to the operator.
- Failed or low-quality calibration cannot be silently saved.

## Safety Notes

- Capture samples slowly.
- Require robot enabled and healthy before capture.
- Do not move automatically during initial implementation; the operator positions the robot manually or through existing jog controls.
- If automated sample poses are added later, validate all poses through existing safety and reachability checks before motion.
- Do not disable safety walls as part of TCP calibration unless explicitly required and documented for the physical setup.

## Open Decisions

- Which target robot system should own the first UI wiring: `paint`, `glue`, or shared?
- Should ROS2 runtime YAML be edited directly, or should the tool registry endpoint persist through a dedicated config writer?
- Should the first implementation support only translation, or should orientation calibration be postponed explicitly?
- Should `ROBOT_TOOL` be updated automatically after save, or left as a manual Robot Settings step?

## Recommended First Implementation Slice

1. Add the solver and unit tests in robot_app_platform.
2. Add a manual script or temporary CLI to feed captured flange poses and print the solved TCP offset.
3. Add ROS2 runtime tool-registry read/update endpoints.
4. Add the `ToolTcpCalibration` app.
5. Wire the app into the target robot system.
6. Add automated persistence and active-tool selection only after the manual workflow is verified on hardware.
