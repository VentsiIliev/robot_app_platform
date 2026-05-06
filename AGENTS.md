# AGENTS.md

This file provides guidance for AI coding agents (Claude, OpenCode, etc.) when working with code in this repository.

## Commands

```bash
python src/bootstrap/main.py                          # run full application
python tests/run_tests.py                             # run all tests
python -m unittest tests/path/to/test_file.py -v     # single test file
python src/applications/<name>/example_usage.py      # standalone app dev runner
```

No `pyproject.toml`, `setup.py`, or `requirements.txt` — dependencies are managed via the `.venv` directory.

---

## Three-Level Architecture

```
Platform (src/engine/, src/bootstrap/, pl_gui/)
  └── RobotSystem (src/robot_systems/)     ← class-level specs + runtime composition hooks
        └── Application                    ← self-contained MVC screen
```

### Level 1 — Platform

Shared, reusable infrastructure. Knows nothing about glue, dispensing, or any specific robot task.

| Package | Responsibility |
|---|---|
| `src/engine/core/` | `MessageBroker` singleton — pub/sub and request/response |
| `src/engine/robot/` | Robot control stack (`IRobotService`, `MotionService`, `SafetyChecker`) |
| `src/engine/hardware/` | Hardware I/O (`ModbusActionService`, `WeightCellService`) |
| `src/engine/repositories/` | JSON settings persistence (`SettingsService`, `BaseJsonSettingsRepository`) |
| `src/engine/process/` | Thread-safe state machine (`BaseProcess`, `ProcessState`, `ProcessTopics`) |
| `src/bootstrap/` | Startup sequence, `ApplicationLoader`, `SystemBuilder` |
| `pl_gui/` | Qt shell (`AppShell`, `FolderLauncher`). Vendored locally in this repo. Treat it as shared platform code: only modify it when the task explicitly requires shell/framework changes. |

### Level 2 — RobotSystem

Declaration-heavy system definition plus runtime composition hooks. `SystemBuilder` reads the class-level specs, and the concrete robot system typically composes its runtime services in `on_start()`.

```python
class GlueRobotSystem(BaseRobotSystem):
    metadata       = SystemMetadata(name="GlueSystem", settings_root="storage/settings")
    settings_specs = [...]   # which JSON files to load + their serializers
    services       = [...]   # required/optional service contracts
    shell          = ShellSetup(
        folders      = [...],          # navigation folders in the GUI
        applications = [...],          # ApplicationSpec list — one per screen
    )
```

The actual implementation (e.g. `glue_robot_system.py`, `paint_robot_system.py`, `welding_robot_system.py`) also declares things like `movement_groups`, `target_points`, `work_areas`, `role_policy`, and implements `on_start()` / `on_stop()` lifecycle hooks. Runtime processes, targeting providers, calibration providers, and shared application services are commonly constructed there.

### Level 3 — Application

Isolated MVC screen. Entry point: `ApplicationSpec.factory(robot_system)` → `WidgetApplication` → `ApplicationFactory.build(service)`.

- Lives either in shared `src/applications/<name>/` or in robot-system-specific packages such as `src/robot_systems/<system>/applications/<name>/`
- Exposes one public entry point: `IMyService` interface + a factory function
- Has **no knowledge** of the RobotSystem, other applications, or the platform beyond `IMyService`
- Is built lazily when the user navigates to its folder

Data flows one way: `User action → View signal → Controller → Model → Service`
Live data flows: `Broker callback → Controller → View setter`

---

## Startup Sequence (`src/bootstrap/main.py`)

Uses a `BootstrapProvider` pattern (e.g. `GlueBootstrapProvider`, `PaintBootstrapProvider`) to select the active `RobotSystem`. See `_BOOTSTRAP_PROVIDER` in `main.py` — default is currently `PaintBootstrapProvider` (dev flag).

Ordered steps — order matters:

1. `EngineContext.build()` — creates the `MessagingService` singleton
2. `SystemBuilder().with_robot(_BOOTSTRAP_PROVIDER.build_robot()).with_messaging_service(ctx.messaging_service).build(_BOOTSTRAP_PROVIDER.system_class)` — wires all services and settings
3. `ShellConfigurator.configure(_BOOTSTRAP_PROVIDER.system_class)` — registers folder metadata with the shell
4. `QApplication(sys.argv)` + localization service init — Qt must exist before any widgets
5. `AppShell` — shell is created **before** application loading (with empty placeholder); login gate runs if `_DEV_SKIP_LOGIN` is `False`
6. `_load_apps_into_shell()` — `ApplicationLoader` iterates visible application specs (filtered by user role), calls `spec.factory(robot_app)`, registers each, then rebuilds the shell's folder page

---

## Hardware Transport Stack

All register-mapped devices (motors, generators, solenoid boards) share one protocol-agnostic interface:

```
IRegisterTransport                       ← src/engine/hardware/communication/i_register_transport.py
  └── ModbusRegisterTransport            ← implements all 4 ops via minimalmodbus (RTU)
        ├── ModbusMotorTransport(ModbusRegisterTransport, IMotorTransport)
        └── ModbusGeneratorTransport(ModbusRegisterTransport, IGeneratorTransport)
```

**Rules:**
- **Never use `minimalmodbus` directly** outside `ModbusRegisterTransport._make_instrument()` — it is an implementation detail of that one class
- `IMotorTransport` and `IGeneratorTransport` are semantic type aliases of `IRegisterTransport` — they add no new methods, they exist only to constrain injection sites
- New Modbus device transport: inherit both `ModbusRegisterTransport` and the device interface, docstring only:
```python
class ModbusMyDeviceTransport(ModbusRegisterTransport, IMyDeviceTransport):
    """Modbus RTU transport for my device boards."""
```
- Supports per-call sessions and persistent connections via `connect()` / `disconnect()`

**`IRegisterTransport` default method chain** (override only what you need):
- `write_register` → delegates to `write_registers([value])`
- `write_registers` → loops `write_register`
- `read_registers` → loops `read_register`
- `connect` / `disconnect` → no-ops by default; override for persistent sessions

---

## IHealthCheckable Pattern

`IHealthCheckable` (`src/engine/core/i_health_checkable.py`) — single-method interface. Implement on any service that has a meaningful connected/ready state:

```python
class IHealthCheckable(ABC):
    @abstractmethod
    def is_healthy(self) -> bool: ...
```

Current implementors:

| Service | `is_healthy()` semantics |
|---|---|
| `IRobotService` | `get_state()` not in `("error", "disconnected", "fault")` |
| `IMotorService` | `self._connected` flag — set by `open()` / cleared by `close()` — **no I/O** |
| `IWeightCellService` | `len(get_connected_cell_ids()) > 0` |

Non-`IHealthCheckable` hardware that still exposes health information:

| Service | Health access | Cost |
|---|---|---|
| `IGeneratorController` | `get_state().is_healthy` — `True` when last register read succeeded | **Blocking I/O** — use only on explicit user request, not as an availability gate |
| `ILaserControl` | None — write-only interface | — |
| `IVacuumPumpController` | None — write-only interface | — |

**`ServiceHealthRegistry`** (`src/engine/process/service_health_registry.py`) auto-wires health checks into `BaseProcess`:

```python
from src.engine.common_service_ids import CommonServiceID
from src.robot_systems.glue.component_ids import ServiceID

registry = ServiceHealthRegistry()
registry.register_service(CommonServiceID.ROBOT,  robot_service)   # auto-detects IHealthCheckable
registry.register_service(ServiceID.WEIGHT,       weight_service)  # auto-detects IHealthCheckable

process = GlueProcess(
    service_checker=registry.check,
    requirements=ProcessRequirements.requires(CommonServiceID.ROBOT),
)
```

Service names are **Enum values** (e.g. `CommonServiceID.ROBOT`, `ServiceID.MOTOR`), not strings.
`ProcessRequirements.requires(CommonServiceID.ROBOT)` blocks `RUNNING` transitions until `registry.check(CommonServiceID.ROBOT)` returns `True`. An unregistered service name → always `False`.
Non-`IHealthCheckable` services registered via `register_service()` default to `lambda: True` (always healthy).

---

## Strict Layer Import Rules

| Layer | May import | Must NOT import |
|---|---|---|
| `IApplication` / `WidgetApplication` | `IMyService`, factory | `ISettingsService`, `IRobotService` directly |
| `IMyService` | stdlib only | anything platform |
| `MyApplicationService` | platform services (`ISettingsService`, `IRobotService`) | Qt, model, view, controller |
| `MyModel` (`IApplicationModel`) | `IMyService`, stdlib | Qt, view, controller |
| `MyView` (`IApplicationView`) | Qt, `pl_gui` | model, service, broker, controller |
| `MyController` (`IApplicationController`) | model, view, `IMessagingService` | services, `ISettingsService` |
| `MyApplicationFactory` (`ApplicationFactory`) | model, view, controller, service | broker directly |

---

## Critical Patterns

### MessageBroker — weak refs, no lambdas, always unsubscribe
- `MessageBroker` uses `WeakMethod` — dead subscribers are auto-cleaned
- **Never** pass `lambda` or bare `.emit` as a broker callback — GC silently drops them
- Always use named bound methods: `broker.subscribe(topic, self._on_event)`
- Inject `IMessagingService`; never import `MessageBroker` directly
- **Every `subscribe` in `load()` must have a matching `unsubscribe` in `stop()`.**
  The controller stays alive via `view._controller` — weak references do NOT auto-clean it.
  Without `unsubscribe`, callbacks fire on deleted Qt widgets → `RuntimeError: wrapped C/C++ object … has been deleted`.
  ```python
  def load(self) -> None:
      self._messaging.subscribe(SomeTopic.EVENT, self._on_event)

  def stop(self) -> None:
      self._messaging.unsubscribe(SomeTopic.EVENT, self._on_event)
  ```
- `ApplicationFactory.build()` automatically wires `view.clean_up → controller.stop()`.
  `stop()` is therefore guaranteed to run when the shell destroys the widget — never omit it.
  Subclasses must implement `stop()` even if it currently has nothing to do — subscriptions may be added later.

### Signal forwarding in views — named methods only
```python
# ✓ correct — named bound method
self._btn.clicked.connect(self._on_click)
def _on_click(self): self.save_requested.emit(self._input.text())

# ✗ wrong — lambda is GC'd, connection silently dies
self._btn.clicked.connect(lambda: self.save_requested.emit(self._input.text()))
```

### GC fix in ApplicationFactory
- `ApplicationFactory.build()` assigns `view._controller = controller` automatically
- This keeps the controller alive as long as the view lives
- **Never write this line yourself** in a factory subclass — the base class owns it

### Cross-thread broker callbacks — `_Bridge(QObject)` pattern
Use when broker callbacks (e.g. weight readings) arrive from background threads and must update Qt widgets:
```python
class _Bridge(QObject):
    data_updated = pyqtSignal(int, float)

class MyController(IApplicationController):
    def __init__(self, model, view, messaging_service):
        self._bridge = _Bridge()                              # must be stored — strong ref
        self._bridge.data_updated.connect(self._view.set_value)

    def _subscribe(self):
        cb = self._on_data                                    # named bound method
        self._messaging_service.subscribe("some/topic", cb)
        self._subs.append(("some/topic", cb))

    def _on_data(self, data):
        self._bridge.data_updated.emit(data.id, data.value)  # thread-safe via Qt queue
```
Reference: `GlueCellSettingsController`

### Blocking service calls — `QThread + _Worker` pattern
Use for any blocking operation (port scan, HTTP request) to avoid freezing the GUI:
```python
class _Worker(QObject):
    finished = pyqtSignal(object)
    def __init__(self, fn): self._fn = fn
    def run(self): self.finished.emit(self._fn())

class MyController(IApplicationController):
    def __init__(self, model, view):
        self._active: List[Tuple[QThread, _Worker]] = []     # must hold both — strong refs

    def _run_blocking(self, fn, on_done):
        thread = QThread()
        worker = _Worker(fn)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(on_done)
        worker.finished.connect(thread.quit)
        self._active.append((thread, worker))                 # prevents GC
        thread.start()
```
Reference: `ModbusSettingsController`

### View Styling — always use the shared style system

All views **must** import style constants from `pl_gui.settings.settings_view.styles` — never hard-code hex colours in a view.

```python
from pl_gui.settings.settings_view.styles import (
    BG_COLOR,          # #F8F9FA — widget / content background
    BORDER,            # #E0E0E0 — borders, dividers
    PRIMARY,           # #905BA9 — primary accent colour
    PRIMARY_DARK,      # darker shade for hover/pressed
    GROUP_STYLE,       # QGroupBox stylesheet
    ACTION_BTN_STYLE,  # filled primary button (44px tall, 8px radius, 11pt bold)
    GHOST_BTN_STYLE,   # outlined primary button — secondary actions
    SAVE_BUTTON_STYLE, # large save/confirm button (52px tall)
    LABEL_STYLE,       # bold 11pt label
)
```

| Element | Rule |
|---------|------|
| Widget background | `self.setStyleSheet(f"background-color: {BG_COLOR};")`  |
| `QGroupBox` | `box.setStyleSheet(GROUP_STYLE)` |
| Primary action button | `btn.setStyleSheet(ACTION_BTN_STYLE)` |
| Secondary action button | `btn.setStyleSheet(GHOST_BTN_STYLE)` |
| Save / confirm button | `btn.setStyleSheet(SAVE_BUTTON_STYLE)` |
| Semantic status buttons (ON=green / OFF=red) | Define local `_BTN_ON` / `_BTN_OFF` constants that **match the same dimensions** as `ACTION_BTN_STYLE` (`border-radius: 8px`, `font-size: 11pt`, `font-weight: bold`, `min-height: 44px`, `padding: 0 16px`) using `#2E7D32` / `#C62828` |
| All clickable buttons | `btn.setCursor(Qt.CursorShape.PointingHandCursor)` |

Reference: `ModbusSettingsView` (imports + ACTION/GHOST usage), `DeviceControlView` (semantic ON/OFF pattern).

### Localization — initial translation and retranslation

The platform has an engine-level localization service under `src/engine/localization/`. Use it consistently.

Rules:
- Catalogs live per robot system under `src/robot_systems/<system>/storage/translations/`
- Widget-owned static text should use `self.tr("...")`
- Long-lived widgets must handle `QEvent.LanguageChange` and call `retranslateUi()`
- Controller-owned or config-driven text must be retranslated explicitly
- If text is not created by `self.tr(...)`, do an explicit initial `_retranslate()` after view initialization

Example for a widget:
```python
def retranslateUi(self) -> None:
    self._save_btn.setText(self.tr("Save"))

def changeEvent(self, event) -> None:
    if event.type() == QEvent.Type.LanguageChange:
        self.retranslateUi()
    super().changeEvent(event)
```

Example for a controller:
```python
def _initialize_view(self) -> None:
    ...
    self._retranslate()   # required initial pass for raw/config-driven labels

def _retranslate(self) -> None:
    self._view.set_action_button_text("reset", self._t("Reset Errors"))

@staticmethod
def _t(text: str) -> str:
    translated = QCoreApplication.translate("MyContext", text)
    return translated or text
```

Notes:
- `QCoreApplication.translate(...)` can return `""` for a miss with the custom translator, so always use `translated or source_text`
- Initial render and runtime language change are different paths; verify both
- If a controller/view exposes a language-change signal, connect it to the controller `_retranslate()` for dynamic text

### Process state machine (`BaseProcess`)
- Override `_on_start`, `_on_pause`, `_on_resume`, `_on_stop`
- Hooks are called **while the lock is held** — must be non-blocking
- `ProcessRequirements.requires(CommonServiceID.ROBOT)` gates transitions on service availability

### Settings

JSON files live under each robot system's `metadata.settings_root`, which is currently `storage/settings` for the active systems in this repo. Each key is declared as a `SettingsSpec` with a `SettingsSerializer` (`get_default()`, `to_dict()`, `from_dict()`). Access at runtime: `settings_service.get("key")`.

---

## Adding a New Application — 13-Step Checklist

1. Copy `src/applications/APPLICATION_BLUEPRINT/` → `src/applications/my_application/`
2. Replace every `My`/`my`/`APPLICATION_BLUEPRINT` occurrence (files, imports, class names)
3. `IMyService` — define all queries (return data) and commands (return `None`)
4. `StubMyService` — implement every method with `print` + hardcoded values; used in tests
5. `MyApplicationService` — only file allowed to import platform services (`ISettingsService`, `IRobotService`)
6. `MyModel(IApplicationModel)` — holds in-memory state, delegates I/O to service; zero Qt
7. `MyView(IApplicationView)` — one `pyqtSignal` per user action, one setter per data push; zero logic
8. `MyController(IApplicationController)` — wires signals in `__init__`, populates view in `load()`, unsubscribes in `stop()`
9. `MyApplicationFactory(ApplicationFactory)` — implement only `_create_model`, `_create_view`, `_create_controller`
10. `__init__.py` — expose only `MyApplication` + `IMyService`; nothing else
11. Settings — declare dataclass + `ISettingsSerializer` subclass if persistence needed
12. Wire in the target robot system — add `_build_my_application()` in that system's `application_wiring.py` and add an `ApplicationSpec` in the corresponding robot system class
13. Verify standalone: `python src/applications/my_application/example_usage.py` using `StubMyService`

Full walkthrough: `src/applications/APPLICATION_BLUEPRINT/APPLICATION_GUIDE.MD`

### Factory wiring pattern (step 12)
```python
def _build_my_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.my_application.my_application_factory import MyApplicationFactory
    from src.applications.my_application.service.my_application_service import MyApplicationService

    service = MyApplicationService(settings_service=robot_system._settings_service)
    factory = MyApplicationFactory()
    return WidgetApplication(
        widget_factory=lambda _ms: factory.build(service)       # no broker needed
        # widget_factory=lambda ms: factory.build(service, ms)  # broker needed
    )
```

### Standalone runner pattern (step 13)
```python
def run_standalone():
    app = QApplication(sys.argv)
    widget = MyApplicationFactory().build(StubMyService())
    window = QMainWindow()
    window.setCentralWidget(widget)
    window.resize(1280, 900)
    window.show()
    sys.exit(app.exec())
```

---

## Real Application Examples

| Application | Special pattern | Broker needed |
|---|---|---|
| `RobotSettings` | Plain MVC, no threading | No |
| `ModbusSettings` | `QThread + _Worker` for port scan / connection test | No |
| `GlueCellSettings` | `_Bridge(QObject)` for cross-thread weight readings | Yes |
| `GlueDashboard` | `ProcessRequirements`, `SystemManager` integration | Yes |
| `DeviceControl` | `QThread + _Worker` for all 8 device commands (motor ramp blocks ~1s); `IMotorService.is_healthy()` as availability gate | No |

---

## Adding a New Robot System

Subclass `BaseRobotSystem`, declare `metadata`, `settings_specs`, `services`, and `shell` as class variables, then compose runtime dependencies in `on_start()` / `on_stop()`. Wire it in `src/bootstrap/main.py` through a `BootstrapProvider` and the selected `_BOOTSTRAP_PROVIDER`.

If the robot system supports localization:
- set `metadata.translations_root`
- add `en.json` and any other catalogs under `storage/translations/`
- keep context names stable once published

---

## Code Quality Standards

All code must follow **SOLID principles**:

- **Single Responsibility** — each class does one thing; no fat controllers, no god models
- **Open/Closed** — extend via subclassing or composition, not by modifying base classes
- **Liskov Substitution** — `StubMyService` must honour every contract of `IMyService`
- **Interface Segregation** — keep interfaces narrow; don't force unused method implementations
- **Dependency Inversion** — always depend on abstractions (`IMyService`, `IMessagingService`), never concrete classes across layer boundaries

Additional requirements:
- **Unit-testable in isolation** — use `StubMyService` for application tests, never real services
- Prefer **composition over inheritance** beyond the mandatory base classes
- No business logic in views; no Qt imports in models, services, or controllers
- Every public method must have a clear, single contract

### Execution Principles

These guidelines complement the architecture rules above. They do **not** override them.

- Prefer the **simplest solution that fully respects the platform architecture**
- Make **surgical changes** — every changed line should trace directly to the task
- **State assumptions explicitly** when hardware behavior, threading, process semantics, or ownership is uncertain
- If there are multiple reasonable interpretations, **surface the tradeoff** instead of silently choosing one
- Prefer **existing patterns over new abstractions** unless the current structure directly causes the bug
- Treat "quick fixes" that break layer boundaries as **incorrect**, even if they seem to work
- When fixing bugs, define a **clear verification path** first:
  - reproduce the issue, or name the exact failure mode being addressed
  - implement the smallest defensible change
  - verify with the smallest meaningful test, runtime check, or targeted manual path
- Add defensive handling when justified by real robot, hardware, I/O, or threading risk; do **not** add speculative complexity for impossible scenarios
- If you notice unrelated cleanup opportunities, **mention them separately**; do not fold them into the same change unless asked

---

## Key Files

| File | Purpose |
|---|---|
| `src/bootstrap/main.py` | Startup sequence, BootstrapProvider pattern, login gate |
| `src/robot_systems/ROBOT_SYSTEM_BLUEPRINT/my_robot_system.py` | Canonical robot-system template |
| `src/robot_systems/ROBOT_SYSTEM_BLUEPRINT/ROBOT_SYSTEM_GUIDE.MD` | Full robot-system implementation guide |
| `src/robot_systems/paint/paint_robot_system.py` | Current default bootstrap target in `main.py` |
| `src/robot_systems/glue/glue_robot_system.py` | Rich example of a mature robot-system implementation |
| `src/robot_systems/paint/application_wiring.py` and `src/robot_systems/glue/application_wiring.py` | Representative application wiring patterns |
| `src/applications/APPLICATION_BLUEPRINT/` | Canonical template — copy, don't hand-write |
| `src/applications/APPLICATION_BLUEPRINT/APPLICATION_GUIDE.MD` | Full 13-step implementation walkthrough |
| `src/shared_contracts/events/` | All topic strings and payloads (`ProcessTopics`, `WeightTopics`, etc.) |
| `src/engine/core/message_broker.py` | Singleton pub/sub with weak references |
| `src/engine/core/i_health_checkable.py` | `IHealthCheckable` — implement on any connectable service |
| `src/engine/process/service_health_registry.py` | Maps service names → health callables for `BaseProcess` |
| `src/engine/hardware/communication/i_register_transport.py` | Protocol-agnostic register I/O base |
| `src/engine/hardware/communication/modbus/modbus_register_transport.py` | `minimalmodbus` RTU implementation — sole entry point for serial Modbus |

---

## Documentation Update Triggers

When changing code in these paths, ask the user whether docs need updating:
- `src/engine/` → `docs/engine/`
- `src/applications/` → `docs/applications/` (+ `APPLICATION_GUIDE.MD` if a shared pattern changes)
- `src/robot_systems/` → `docs/robot_systems/`
- `src/shared_contracts/` → `docs/shared_contracts/` — topic/payload changes affect **all** publishers and subscribers throughout the codebase
