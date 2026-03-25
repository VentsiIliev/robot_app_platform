# `src/engine/robot/` — Robot Module Overview

The `robot` package is the heart of the motion control system. It implements the full robot service stack from the physical driver layer up to high-level navigation and tool management, all behind well-defined interfaces.

---

## Package Structure

```
robot/
├── interfaces/            ← Abstract contracts for all robot subsystems
├── configuration/         ← Settings dataclasses (RobotSettings, RobotCalibrationSettings)
├── targeting/             ← Generic target-point registry, resolver math, and robot-system targeting provider
├── plane_pose_mapper.py   ← Generic rigid XY frame mapping between robot pose frames
├── enums/                 ← RobotAxis, Direction, ImageToRobotMapping
├── safety/                ← SafetyChecker (workspace bounds enforcement)
├── features/              ← NavigationService (named positions), RobotToolService
├── calibration/           ← Generic calibration builders + calibration provider contract
├── height_measuring/      ← Generic height-measuring builders + provider contract
├── services/              ← MotionService, RobotStateManager, RobotService, factory
├── drivers/
│   └── fairino/           ← FairinoRobot, TestRobotWrapper
├── tool_changer.py        ← ToolChanger (slot ↔ gripper mapping)
└── tool_manager.py        ← ToolManager (pick-and-place logic)
```

---

## Architecture

### Service Composition Hierarchy

```
IRobotService (public contract — what applications see)
└── RobotService
      ├── IMotionService → MotionService
      │     ├── IRobot → FairinoRobot (production) / TestRobotWrapper (dev)
      │     └── ISafetyChecker → SafetyChecker
      └── IRobotStateProvider → RobotStateManager
            ├── IRobot (same instance as above)
            └── IStatePublisher → RobotStatePublisher → IMessagingService
```

All inter-layer communication goes through interfaces. `RobotService` never knows about `FairinoRobot`; `MotionService` never knows about `RobotStateManager`. This allows each layer to be tested and replaced independently.

### Optional Tool Service

```
RobotService.tools: Optional[IToolService]
└── RobotToolService
      └── ToolManager
            ├── IMotionService (shared with motion layer)
            └── IToolChanger → ToolChanger (slot ↔ tool ID registry)
```

Tool service is only wired if a `tool_changer` is provided to `create_robot_service()`.

---

## Full Interface Hierarchy

```
IRobotLifecycle
  enable_robot() / disable_robot()
      │
      ┤ (also inherits)
      │
IMotionService
  move_ptp() / move_linear() / start_jog() / stop_motion() / get_current_position()
      │
      └── IRobotService   ← the single interface applications import
              + get_current_velocity()
              + get_current_acceleration()
              + get_state() / get_state_topic()
              + validate_pose(start_position, target_position, tool=0, user=0)
              + enable_safety_walls() / disable_safety_walls()
              + are_safety_walls_enabled() / get_safety_walls_status()
```

---

## Wiring

All components are assembled by `create_robot_service()` in `services/robot_service_factory.py`:

```python
from src.engine.robot.services.robot_service_factory import create_robot_service

robot_service = create_robot_service(
    robot=FairinoRobot(ip="192.168.58.2"),
    messaging_service=messaging,
    settings_service=settings,  # optional — enables safety checks
    tool_changer=None,           # optional — enables tool service
)
```

The factory:
1. Creates `SafetyChecker(settings_service)`
2. Creates `MotionService(robot, safety_checker)`
3. Creates `RobotStatePublisher(messaging_service)`
4. Creates `RobotStateManager(robot, publisher)` and starts its monitoring thread
5. Optionally creates `RobotToolService`
6. Returns `RobotService(motion, robot, state_manager, tool_service)`

---

## Robot Availability States

`RobotStateManager` publishes `RobotStateSnapshot` on `RobotTopics.STATE`.

The important `snapshot.state` values are:

| State | Meaning |
|---|---|
| `idle` | Robot transport is reachable and no higher-level fault is being reported |
| `disconnected` | The underlying robot transport/bridge is unavailable |
| `error` | State polling itself failed unexpectedly |

For the ROS bridge driver:
- [FairinoRos2Client](/home/ilv/Desktop/robot_app_platform/src/engine/robot/drivers/fairino/fairino_ros2_client.py) no longer raises during startup when `http://localhost:5000` is unavailable
- instead it reports `disconnected`
- `RobotStateManager` publishes that state through the normal broker topic

For motion stop requests against the ROS bridge:
- the bridge now returns an explicit `stop_state`
- `STOPPED` and `NO_ACTIVE_MOTION` are treated as benign stop outcomes by the platform client
- `STOP_REQUESTED_BUT_UNCONFIRMED` and `ERROR` are treated as failed stop outcomes and can trigger retries or operator warnings

For queued motion requests against the ROS bridge:
- queueable motion types are:
  - single-target linear/PTP moves
  - multi-waypoint trajectory execution
- both share one server-side motion queue, so mixed ordering is preserved:
  - single move -> trajectory
  - trajectory -> single move
- `jog` is explicitly not queueable
- the platform motion layer treats `ret >= 0` as an accepted motion command:
  - `0` = started immediately
  - `>0` = accepted and queued by the bridge

This means application startup can continue even when the bridge is down, and subscribers should treat `disconnected` as a first-class availability state, not as an exception path.

`RobotStateSnapshot.extra` may include transport diagnostics such as:
- `server_url`
- `last_error`

## Remote Safety Walls

`IRobotService` now also exposes optional control of the remote ROS/MoveIt safety-wall system:

- `enable_safety_walls() -> bool`
- `disable_safety_walls() -> bool`
- `are_safety_walls_enabled() -> Optional[bool]`
- `get_safety_walls_status() -> dict`

Important distinction:

- `ISafetyChecker`
  - platform-side Cartesian limit checking before commands are sent
- remote safety walls
  - ROS/MoveIt planning-scene walls enforced by the ROS bridge

These are related but separate safety layers. The platform contract keeps both:
- local safety checks remain in `MotionService` through `ISafetyChecker`
- remote wall control is exposed through `IRobotService`

Current driver support:

- `FairinoRos2Robot`
  - backed by the REST endpoints:
    - `GET /safety/walls/enabled`
    - `GET /safety/walls/status`
    - `POST /safety/walls/enable`
    - `POST /safety/walls/disable`
- non-ROS drivers inherit safe default no-op implementations from `IRobot`

## Pose Reachability Validation

`IRobotService` now also exposes a reusable planning-only reachability primitive:

- `validate_pose(start_position, target_position, tool=0, user=0) -> dict`

Purpose:

- simulate whether a target pose is reachable from an explicit start pose
- reuse the same ROS/MoveIt planning path without physically moving the robot
- support higher-level workflows such as Calibration area-grid prechecks

Current driver support:

- `FairinoRos2Robot`
  - backed by the REST endpoint:
    - `POST /reachability/pose`

Expected response fields include:

- `reachable`
- `fraction`
- `reason`
- `start_position`
- `target_position`

Important distinction:

- `validate_pose(...)`
  - planning-only simulation from a supplied start state
- `move_ptp(...)` / `move_linear(...)`
  - live execution from the robot's actual current state

The Calibration application uses `validate_pose(...)` only for precheck simulation. Real motion still plans from the live robot state at execution time.

---

## Subpackage Documentation

| Subpackage | Key Classes | Docs |
|-----------|------------|------|
| `interfaces/` | `IRobot`, `IMotionService`, `IRobotService`, `ISafetyChecker`, `IRobotStateProvider`, `IStatePublisher`, `IToolChanger`, `IToolService` | [interfaces/](interfaces/README.md) |
| `configuration/` | `RobotSettings`, `SafetyLimits`, `MovementGroup`, `RobotCalibrationSettings` | [configuration/](configuration/README.md) |
| `targeting/` | `PointRegistry`, `VisionTargetResolver`, `JogFramePoseResolver`, `RobotSystemTargetingProvider` | [targeting/](targeting/README.md) |
| `calibration/` | `build_robot_system_calibration_service`, `RobotSystemCalibrationProvider` | [calibration/](calibration/README.md) |
| `height_measuring/` | `IHeightMeasuringService`, `IHeightCorrectionService`, `HeightCorrectionService`, `build_robot_system_height_measuring_services` | [height_measuring/](height_measuring/README.md) |
| `path_interpolation/` | `interpolate_path_linear`, `interpolate_path_spline_with_lambda`, `interpolate_path_two_stage` | [path_interpolation/](path_interpolation/README.md) |
| `../../robot_systems/default_service_builders.py` | `build_tool_service`, `build_vision_service` | centralized shared default builders used by `SystemBuilder` |
| `plane_pose_mapper.py` | `PlanePose`, `PlanePoseMapper` | reusable 2D rigid frame transform between robot pose frames |
| `enums/` | `RobotAxis`, `Direction`, `ImageToRobotMapping` | [enums/](enums/README.md) |
| `safety/` | `SafetyChecker` | [safety/](safety/README.md) |
| `features/` | `NavigationService`, `RobotToolService` | [features/](features/README.md) |
| `services/` | `MotionService`, `RobotStateManager`, `RobotService`, `create_robot_service` | [services/](services/README.md) |
| `drivers/fairino/` | `FairinoRobot`, `TestRobotWrapper` | [drivers/fairino/](drivers/fairino/README.md) |

---

## Design Notes

- **No Qt in `robot/`**: Every class in this package is pure Python. Qt widgets subscribe to topics on the messaging bus to receive robot state updates.
- **State monitoring runs in a daemon thread**: `RobotStateManager` polls the robot at 0.5s intervals. The thread is daemonized and doesn't block process exit.
- **Position format**: All positions are `List[float]` with 6 elements: `[x, y, z, rx, ry, rz]` in mm and degrees.
- **Return codes vs booleans**: `IRobot` methods return `int` (`0` = started immediately, `>0` = accepted and queued, negative = error). `IMotionService` wraps these and returns `bool` (`True` = accepted motion command). This distinction is maintained at the interface boundary.
- **Blocking waits are pose-aware**: when `wait_to_reach=True`, the default `MotionService` waits for Cartesian convergence and, for 6D targets, orientation convergence with wrapped-angle handling. This prevents orientation-only moves from being acknowledged early.
- **Bridge-down is not bootstrap-fatal**: for the ROS bridge transport, unavailable hardware should surface as `robot/state = disconnected`, allowing the rest of the platform to boot and show degraded availability.
