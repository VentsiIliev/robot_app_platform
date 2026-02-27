# `src/robot_systems/` — Robot Applications

The `robot_apps` package is the application layer of the platform. It contains `BaseRobotSystem` (the abstract declaration contract), `SystemBuilder` (the wiring engine), and one concrete app per robot type. Each robot system declares what it needs via class-level specs; `SystemBuilder` constructs and injects everything.

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

BaseRobotSystem (ABC)
  ├─ class-level specs: metadata, settings_specs, services, shell
  └─ instance: _resolved, _settings_service, on_start(), on_stop()
```

---

## `BaseRobotSystem`

**File:** `base_robot_system.py`

```python
class BaseRobotSystem(ABC):
    metadata:       ClassVar[SystemMetadata]      = SystemMetadata(name="UnnamedApp")
    services:       ClassVar[List[ServiceSpec]] = []
    settings_specs: ClassVar[List[SettingsSpec]] = []
    shell:          ClassVar[ShellSetup]        = ShellSetup()

    def get_settings(self, name: str) -> Any: ...
    def get_settings_repo(self, name: str) -> ISettingsRepository: ...
    def get_service(self, name: str) -> Any: ...
    def get_optional_service(self, name: str) -> Optional[Any]: ...
    def start(self, services: Dict[str, Any], settings_service: ...) -> None: ...
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

| Class | Fields | Purpose |
|-------|--------|---------|
| `SystemMetadata` | `name`, `version`, `description`, `author`, `settings_root` | App identity; `settings_root` is the base path for all JSON files |
| `SettingsSpec` | `name`, `serializer`, `storage_key`, `required` | Declares one settings file; `name` = retrieval key; `storage_key` = relative JSON path |
| `ServiceSpec` | `name`, `service_type`, `required`, `description`, `builder` | Declares one service contract; optional `builder` overrides the default registry builder |
| `ShellSetup` | `folders: List[FolderSpec]`, `applications: List[ApplicationSpec]` | GUI shell structure |
| `FolderSpec` | `folder_id`, `name`, `display_name`, `translation_key` | One navigation folder in the shell |
| `ApplicationSpec` | `name`, `folder_id`, `icon`, `factory` | One application registered to a folder; `factory(robot_system) → IApplication` |

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

**File:** `app_builder.py`

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
  8. app.start(services, settings_service)
  9. return app
```

### Default Service Registry

| Service Type | Default Builder | Notes |
|-------------|----------------|-------|
| `IRobotService` | `_build_robot_service` | Builds `RobotStatePublisher → RobotStateManager → RobotService`; starts state monitoring |
| `NavigationService` | `_build_navigation` | Builds `NavigationService(motion, settings)` |
| `IToolService` | `_build_tool_service` | Requires `tool_changer` and `settings`; skipped if either is `None` |

Custom services (e.g., `IWeightCellService`) are registered via `ServiceSpec.builder` on the app class.

### Usage

```python
from src.robot_systems.app_builder import SystemBuilder
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
- **`SystemBuilder.register()`**: Allows overriding or extending the default service registry at the call site. Use when a service requires dependencies not available in the standard context.
- **`required=False` in `ServiceSpec`**: The app starts successfully even if an optional service fails to build. `on_start()` uses `get_optional_service()` and checks for `None` before using optional services.
- **`describe()`**: Class method that prints a human-readable summary of all specs. Useful for debugging and onboarding.

→ Subpackages: [glue/](glue/README.md)
