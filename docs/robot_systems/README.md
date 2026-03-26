# `src/robot_systems/` — Robot Systems

The `robot_systems` package contains `BaseRobotSystem` (the abstract declaration contract), `SystemBuilder` (the wiring engine), and one concrete robot system per machine/domain. Each robot system declares what it needs via class-level specs; `SystemBuilder` constructs and injects everything.

For new robot-system development, start from:
- [ROBOT_SYSTEM_BLUEPRINT](/home/ilv/Desktop/robot_app_platform/src/robot_systems/ROBOT_SYSTEM_BLUEPRINT)
- [ROBOT_SYSTEM_GUIDE.MD](/home/ilv/Desktop/robot_app_platform/src/robot_systems/ROBOT_SYSTEM_BLUEPRINT/ROBOT_SYSTEM_GUIDE.MD)
- [settings/README.md](/home/ilv/Desktop/robot_app_platform/src/robot_systems/ROBOT_SYSTEM_BLUEPRINT/settings/README.md)

Reusability rule:
- new shared robot-system features should be proven in [ROBOT_SYSTEM_BLUEPRINT](/home/ilv/Desktop/robot_app_platform/src/robot_systems/ROBOT_SYSTEM_BLUEPRINT) first
- if a feature cannot be demonstrated cleanly in the blueprint demo, it is not yet standardized enough for platform-level reuse

---

## Architecture

```
SystemBuilder
  ├─ reads app_class.settings_specs → builds SettingsService (JSON files)
  ├─ builds MotionService → RobotService (+ RobotStateManager + publisher)
  ├─ iterates app_class.services:
  │    for each ServiceSpec, looks up a builder in _registry
  │    → calls builder(BuildContext) → service instance
  └─ app.start(services_dict, settings_service) → app.on_start()

RobotSystemBootstrapProvider
  ├─ selects the concrete robot driver
  ├─ selects the concrete robot-system class
  ├─ builds the robot-system-specific login view
  └─ builds the robot-system-specific authorization service

BaseRobotSystem (ABC)
  ├─ class-level specs: metadata, settings_specs, services, shell
  └─ instance: _resolved, _settings_service, _messaging_service, on_start(), on_stop()
```

---

## `BaseRobotSystem`

**File:** `base_robot_system.py`

```python
class BaseRobotSystem(ABC):
    metadata:       ClassVar[SystemMetadata]      = SystemMetadata(name="UnnamedApp")
    services:       ClassVar[List[ServiceSpec]] = []
    settings_specs: ClassVar[List[SettingsSpec]] = []
    work_areas:     ClassVar[List[WorkAreaDefinition]] = []
    dispense_channels: ClassVar[List[DispenseChannelDefinition]] = []
    movement_groups: ClassVar[List[MovementGroupDefinition]] = []
    target_points: ClassVar[List[RemoteTcpDefinition]] = []
    target_frames: ClassVar[List[TargetFrameDefinition]] = []
    work_area_observers: ClassVar[List[WorkAreaObserverBinding]] = []
    default_active_work_area_id: ClassVar[str] = ""
    shell:          ClassVar[ShellSetup]        = ShellSetup()

    def get_settings(self, name: str) -> Any: ...
    def get_settings_repo(self, name: str) -> ISettingsRepository: ...
    def get_service(self, name: str) -> Any: ...
    def get_optional_service(self, name: str) -> Optional[Any]: ...
    def get_work_area_definitions(self) -> list[WorkAreaDefinition]: ...
    def get_movement_group_definitions(self) -> list[MovementGroupDefinition]: ...
    def get_target_point_definitions(self) -> list[RemoteTcpDefinition]: ...
    def get_target_frame_definitions(self) -> list[TargetFrameDefinition]: ...
    def get_work_area_observer_bindings(self) -> list[WorkAreaObserverBinding]: ...
    def get_targeting_provider(self): ...
    def get_calibration_provider(self): ...
    def get_height_measuring_provider(self): ...
    def get_shared_vision_resolver(self): ...
    def invalidate_shared_vision_resolver(self) -> None: ...
    def start(self, services: Dict[str, Any], settings_service=None,
              system_manager=None, messaging_service=None) -> None: ...
    def stop(self) -> None: ...
    def is_running: bool  # property

    @abstractmethod
    def on_start(self) -> None: ...
    @abstractmethod
    def on_stop(self) -> None: ...

    @classmethod
    def describe(cls) -> str: ...   # human-readable spec summary
```

### Spec Dataclasses

Declaration classes now live under:
- `src/shared_contracts/declarations/`

The intended split is:
- `src/shared_contracts/declarations/` holds shared system-description types
- `src/robot_systems/` declares concrete system instances
- `src/engine/` builds and runs them

| Class | Fields | Purpose |
|-------|--------|---------|
| `SystemMetadata` | `name`, `version`, `description`, `author`, `settings_root`, `translations_root` | App identity; `settings_root` is the base path for settings, `translations_root` is the robot-system translation catalog directory |
| `SettingsSpec` | `name`, `serializer`, `storage_key`, `required` | Declares one settings file; `name` = retrieval key; `storage_key` = relative JSON path |
| `ServiceSpec` | `name`, `service_type`, `required`, `description`, `builder` | Declares one service contract; optional `builder` overrides the default registry builder |
| `ShellSetup` | `folders: List[FolderSpec]`, `applications: List[ApplicationSpec]` | GUI shell structure |
| `FolderSpec` | `folder_id`, `name`, `display_name`, `translation_key` | One navigation folder in the shell |
| `ApplicationSpec` | `name`, `folder_id`, `icon`, `factory` | One application registered to a folder; `factory(robot_system) → IApplication` |
| `RemoteTcpDefinition` | `name`, `display_name` | Declares a named remote TCP that the system exposes |
| `DispenseChannelDefinition` | `id`, `label`, `weight_cell_id`, `pump_motor_address`, `default_glue_type` | Declares one logical dispense lane composed of one scale and one pump |
| `ToolDefinition` | `id`, `name` | Declares one tool/gripper identity exposed by the system |
| `ToolSlotDefinition` | `id`, `tool_id` | Declares one physical toolchanger slot and its default assignment |

### Additional Declarations

Robot systems can now declare reusable runtime semantics in addition to services and settings:

| Declaration | Purpose |
|-------|---------|
| `work_areas` | Stable work-area ids and capabilities used by `CameraSettings`, `Calibration`, and runtime vision |
| `dispense_channels` | Stable dispensing channel ids and pump/scale bindings used by glue-domain settings and dispensing services |
| `tools` | Canonical tool/gripper identities used by the shared toolchanger settings |
| `tool_slots` | Canonical slot ids, default slot-to-tool assignments, and declared pickup/dropoff movement-group bindings |
| `movement_groups` | Stable movement-group ids and editing semantics used by `RobotSettings` |
| `target_points` | Stable remote-TCP ids used by robot-system targeting providers and jog/vision resolution |
| `target_frames` | Stable targeting-frame ids and work-area bindings used by robot-system targeting providers |
| `work_area_observers` | Bind `area_id -> movement_group_id` so observation/navigation can be attached to work areas cleanly |
| `default_active_work_area_id` | Robot-system-owned startup default for the active work area |

Shared settings applications now split work-area ownership cleanly:
- `CameraSettings` tunes the vision stack
- `WorkAreaSettings` edits declared work-area ROIs
- `CalibrationSettings` owns calibration-related configuration
- `Calibration` consumes those declared work areas for height mapping

### Service Injection

On `app.start()`, `_validate_and_inject()`:
1. Iterates `services` class-var
2. Checks each `ServiceSpec` against the `services_dict` passed by `SystemBuilder`
3. For missing **required** services: raises `RuntimeError`
4. For missing **optional** services: logs debug, skips
5. Type-checks each provided service: raises `TypeError` if mismatch
6. Stores validated instances in `self._resolved[spec.name]`

Access after start:
```python
robot_service   = self.get_service("robot")           # raises if missing
weight_service  = self.get_optional_service("weight") # returns None if missing
robot_config    = self.get_settings("robot_config")   # raises if no settings service
```

---

## `SystemBuilder`

**File:** `system_builder.py`

```python
class SystemBuilder:
    def with_robot(self, robot: IRobot) -> SystemBuilder: ...
    def with_settings(self, settings_service) -> SystemBuilder: ...
    def with_tool_changer(self, tool_changer) -> SystemBuilder: ...
    def with_messaging_service(self, messaging: IMessagingService) -> SystemBuilder: ...
    def register(self, service_type: Type, builder: Callable) -> SystemBuilder: ...
    def build(self, app_class: Type[T]) -> T: ...
```

### Build Sequence

```
SystemBuilder.build(AppClass)
  1. Validate: robot and messaging_service must be set
  2. Build SettingsService from app_class.settings_specs (if any)
  3. Build MotionService(robot, SafetyChecker(settings))
  4. Assemble _BuildContext(robot, motion, settings, tool_changer, messaging_service)
  5. Merge app-level spec.builders into registry (override defaults)
  6. For each ServiceSpec in app_class.services:
       builder = registry.get(spec.service_type)
       if builder is None: skip optional / raise for required
       instance = builder(ctx)
       if instance is None: skip optional / raise for required
       services[spec.name] = instance
  7. app = AppClass()
  8. app.start(services, settings_service, system_manager, messaging_service)
  9. return app
```

### Default Service Registry

| Service Type | Default Builder | Notes |
|-------------|----------------|-------|
| `IRobotService` | `build_robot_service` | Builds `RobotStatePublisher → RobotStateManager → RobotService`; starts state monitoring |
| `NavigationService` | `build_navigation_service` | Builds `NavigationService(motion, robot_config, movement_groups)` using `CommonSettingsID.ROBOT_CONFIG` and `CommonSettingsID.MOVEMENT_GROUPS` |
| `IWorkAreaService` | `build_work_area_service` | Builds the shared work-area storage + active-area context using `CommonSettingsID.WORK_AREA_SETTINGS`, robot-system `work_areas`, and `default_active_work_area_id` |
| `IToolService` | `build_tool_service` | Shared default builder; requires `CommonSettingsID.TOOL_CHANGER_CONFIG`, `CommonSettingsID.ROBOT_CONFIG`, and `CommonSettingsID.MOVEMENT_GROUPS` |
| `IVisionService` | `build_vision_service` | Shared default builder; requires `CommonSettingsID.VISION_CAMERA_SETTINGS` and standard robot-system storage layout |

Custom services (e.g., `IWeightCellService`) are registered via `ServiceSpec.builder` on the app class.

### Default Validation

`SystemBuilder` now fails early when a robot system declares only one side of a
shared default-builder contract.

Current validation rules:

- `IVisionService` requires `CommonSettingsID.VISION_CAMERA_SETTINGS`
- `CommonSettingsID.VISION_CAMERA_SETTINGS` requires `IVisionService`
- `IToolService` requires `CommonSettingsID.TOOL_CHANGER_CONFIG`
- `IToolService` requires `CommonSettingsID.ROBOT_CONFIG`
- `IToolService` requires `CommonSettingsID.MOVEMENT_GROUPS`
- `NavigationService` requires `CommonSettingsID.MOVEMENT_GROUPS`
- `IWorkAreaService` requires `CommonSettingsID.WORK_AREA_SETTINGS`
- `CommonSettingsID.WORK_AREA_SETTINGS` requires `IWorkAreaService`
- `CommonSettingsID.TOOL_CHANGER_CONFIG` requires `IToolService`
- `CommonSettingsID.ROBOT_CALIBRATION` requires:
  - `IRobotService`
  - `IVisionService`
  - `NavigationService`
  - `CommonSettingsID.ROBOT_CONFIG`
- `CommonSettingsID.HEIGHT_MEASURING_SETTINGS` requires:
  - `IRobotService`
  - `IVisionService`
  - `CommonSettingsID.ROBOT_CONFIG`
  - `CommonSettingsID.HEIGHT_MEASURING_CALIBRATION`
  - `CommonSettingsID.DEPTH_MAP_DATA`

This keeps robot-system declarations coherent and avoids partial default wiring.

### Usage

```python
from src.robot_systems.system_builder import SystemBuilder
from src.robot_systems.glue.glue_robot_system import GlueRobotSystem
from src.engine.robot.drivers.fairino.fairino_robot import FairinoRobot

robot = FairinoRobot(ip="192.168.58.2")
app   = (
    SystemBuilder()
    .with_robot(robot)
    .with_messaging_service(messaging_service)
    .build(GlueRobotSystem)
)
```

---

## Design Notes

- **Class-level specs**: `metadata`, `services`, `settings_specs`, and `shell` are `ClassVar` — they describe the *type*, not any instance. This allows `SystemBuilder` to inspect them before instantiation.
- **`translations_root` is robot-system owned**: The engine localization service is generic, but the actual catalogs live with the robot system. Bootstrap resolves the active robot system's translation directory from `metadata.translations_root`.
- **Language persistence uses robot-system storage**: Bootstrap also stores the selected language under the active robot system's `settings_root`, so localization state follows the robot system instead of using a hardcoded global file.
- **Bootstrap stays generic**: startup-specific composition such as concrete robot driver selection, login/auth wiring, and authorization/permissions wiring should live in a robot-system bootstrap provider, not directly in `src/bootstrap/main.py`.
- **`SystemBuilder.register()`**: Allows overriding or extending the default service registry at the call site. Use when a service requires dependencies not available in the standard context.
- **Common vs robot-system settings ids**: Shared infrastructure ids now live in [`CommonSettingsID`](/home/ilv/Desktop/robot_app_platform/src/engine/common_settings_ids.py). Robot-system [`component_ids.py`](/home/ilv/Desktop/robot_app_platform/src/robot_systems/ROBOT_SYSTEM_BLUEPRINT/component_ids.py) files should keep only system-specific `SettingsID` values.
- **Common vs robot-system service ids**: Shared infrastructure service names now live in [`CommonServiceID`](/home/ilv/Desktop/robot_app_platform/src/engine/common_service_ids.py). Robot-system [`component_ids.py`](/home/ilv/Desktop/robot_app_platform/src/robot_systems/ROBOT_SYSTEM_BLUEPRINT/component_ids.py) files should keep only system-specific `ServiceID` values.
- **Default builders vs providers**:
  - use shared default builders for truly common services such as `IVisionService` and `IToolService`
  - use robot-system providers when only part of the assembly is system-specific, such as targeting, calibration, and height measuring
- **Dashboard standardization**:
  - keep the dashboard UI behind a narrow robot-system service interface
  - let the dashboard model depend only on that interface
  - delegate the real start/stop/pause/resume logic to the system coordinator/process behind that service
  - if the dashboard view uses `DashboardWidget`, use the shared dashboard camera-feed mixin so live vision frames are wired automatically through `VisionTopics.LATEST_IMAGE`
  - if the dashboard service exposes `get_process_id()`, use the shared dashboard process-state mixin so `ProcessTopics.ACTIVE` is wired automatically too
  - use the blueprint dashboard package as the starting pattern for new systems
- **Robot system blueprint**:
  - use [ROBOT_SYSTEM_BLUEPRINT](/home/ilv/Desktop/robot_app_platform/src/robot_systems/ROBOT_SYSTEM_BLUEPRINT) as the starting template
  - the blueprint now includes targeting registry/frames/settings adapter skeletons plus calibration, height-measuring, bootstrap provider, and dashboard skeletons
  - treat the blueprint demo as the proof-of-reusability target for new shared robot-system patterns before depending on them in concrete systems
- **System-specific settings pattern**:
  - define robot-system-specific persisted settings under the robot system's `settings/` package
  - register them through `SettingsID` in `component_ids.py`
  - keep shared reusable settings in `src/engine/`, not in the robot system
- **Movement groups are a dedicated shared settings domain**:
  - `robot/config.json` should stay robot-oriented
  - named positions and path groups now live in `robot/movement_groups.json`
  - robot systems declare ids and semantics; settings files store only values
- **Work-area observation is a binding, not embedded geometry**:
  - keep area identity in `work_areas`
  - bind observation/navigation through `work_area_observers`
  - do not embed raw robot poses into work-area definitions
- **Work-area storage is robot-system owned, not vision owned**:
  - ROI polygons now live in `CommonSettingsID.WORK_AREA_SETTINGS`
  - `CameraSettings` and `Calibration` edit the same shared work-area data
  - `IVisionService` consumes the active work area; it no longer owns area persistence
- **Active area is shared runtime state**:
  - initialize it from `default_active_work_area_id`
  - switch it through the shared work-area service
  - do not couple vision logic to area names such as `pickup` / `spray`
- **`required=False` in `ServiceSpec`**: The app starts successfully even if an optional service fails to build. `on_start()` uses `get_optional_service()` and checks for `None` before using optional services.
- **`describe()`**: Class method that prints a human-readable summary of all specs. Useful for debugging and onboarding.

→ Subpackages: [glue/](glue/README.md)
