# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run the application:**
```bash
python src/bootstrap/main.py
```

**Run all tests:**
```bash
python tests/run_tests.py
```

**Run a single test file:**
```bash
python -m unittest tests/path/to/test_file.py -v
```

**Run an application standalone (development without the full platform):**
```bash
python src/applications/<app_name>/example_usage.py
```

No `pyproject.toml`, `setup.py`, or `requirements.txt` — dependencies are managed via the `.venv` directory.

---

## Three-Level Abstraction

The codebase is structured around three distinct levels. Understanding the boundary between each is essential.

```
Platform
  └── RobotSystem          ← declares what this robot does
        └── Application    ← one self-contained MVC screen
```

### Level 1 — Platform (`src/engine/`, `src/bootstrap/`, `pl_gui/`)

Shared, reusable infrastructure. Knows nothing about glue, dispensing, or any specific robot task.

| Package | Responsibility |
|---------|---------------|
| `src/engine/core/` | `MessageBroker` singleton — pub/sub and request/response |
| `src/engine/robot/` | Robot control stack (`IRobotService`, `MotionService`, `SafetyChecker`) |
| `src/engine/hardware/` | Hardware I/O (`ModbusActionService`, `WeightCellService`) |
| `src/engine/repositories/` | JSON settings persistence (`SettingsService`, `BaseJsonSettingsRepository`) |
| `src/engine/process/` | Thread-safe state machine (`BaseProcess`, `ProcessState`, `ProcessTopics`) |
| `src/bootstrap/` | Startup sequence, `ApplicationLoader`, `SystemBuilder` |
| `pl_gui/` | Qt shell (`AppShell`, `FolderLauncher`). **Treat as read-only external package.** |

### Level 2 — RobotSystem (`src/robot_systems/`)

A `RobotSystem` is a pure **declaration** — no logic, only class-level specs. It answers: *"what does this robot need?"*

`BaseRobotSystem` defines four class-level attributes that every subclass must provide:

```python
class GlueRobotSystem(BaseRobotSystem):
    metadata       = SystemMetadata(name="glue", settings_root="glue")
    settings_specs = [...]   # which JSON files to load + their serializers
    services       = [...]   # required/optional service contracts
    shell          = ShellSetup(
        folders      = [...],          # navigation folders in the GUI
        applications = [...],          # ApplicationSpec list — one per screen
    )
```

`SystemBuilder` reads these specs and constructs the live instance: loads settings, builds `MotionService → RobotService → NavigationService`, then calls `system.start(services, settings_service)`.

### Level 3 — Application (`src/applications/`)

A self-contained MVC screen registered with a RobotSystem via `ApplicationSpec`. Each application:

- Lives entirely in `src/applications/<name>/`
- Exposes one public entry point: `IMyService` interface + a factory function
- Has **no knowledge** of the RobotSystem, other applications, or the platform beyond `IMyService`
- Is built lazily when the user navigates to its folder

```
ApplicationSpec.factory(robot_system)
  └── WidgetApplication(IApplication)
        └── MyApplicationFactory(ApplicationFactory).build(service)
              ├── MyModel(IApplicationModel)      ← state + I/O, no Qt
              ├── MyView(IApplicationView)         ← pure Qt, no logic
              └── MyController(IApplicationController) ← wires M ↔ V
```

Data flows one way: `User action → View signal → Controller → Model → Service`

**Layer import rules** (strictly enforced):

| Layer | May import | Must NOT import |
|-------|-----------|-----------------|
| `IMyService` / `MyApplicationService` | `ISettingsService`, `IRobotService`, platform | Qt, model, view, controller |
| `MyModel` | `IMyService`, stdlib | Qt, services directly |
| `MyView` | Qt, `pl_gui` | model, service, broker, controller |
| `MyController` | model, view, `IMessagingService` | services directly |

---

## Startup Sequence (`src/bootstrap/main.py`)

Six ordered steps — order matters:

1. `EngineContext.build()` — creates the `MessagingService` singleton
2. `SystemBuilder().with_robot(...).with_messaging_service(...).build(GlueRobotSystem)` — wires all services and settings
3. `ShellConfigurator.configure(GlueRobotSystem)` — registers folder metadata with the shell
4. `QApplication(sys.argv)` — Qt must exist before any widgets
5. `ApplicationLoader` — iterates `GlueRobotSystem.shell.applications`, calls each `spec.factory(robot_system)`, then `application.register(messaging_service)`
6. `AppShell` — creates the main window and starts the Qt event loop

---

## Key Patterns

### Messaging

`MessageBroker` is a singleton using **weak references** — dead subscribers are cleaned up automatically. Always inject `IMessagingService`; never import `MessageBroker` directly.

**Critical:** Never use `lambda` or bare `.emit` as PyQt6 signal slot targets — they are silently GC'd. Always use named bound methods.

`ApplicationFactory` assigns `view._controller = controller` automatically to keep the controller alive as long as the view. Never write this line in a factory subclass.

### Cross-thread delivery

When a broker callback must update Qt widgets, use `_Bridge(QObject)` with `pyqtSignal` (see `GlueCellSettingsController`). For blocking service calls (port scan, connection test), use `QThread + _Worker` tracked in `_active` list (see `ModbusSettingsController`).

### Settings

JSON-based persistence. Each setting is declared with a `SettingsSerializer` (implements `get_default()`, `to_dict()`, `from_dict()`). Files are stored under `storage/settings/<system_name>/`. Access via `settings_service.get("key")`.

### Process State Machine

`BaseProcess` in `src/engine/process/` provides a thread-safe state machine. Subclass it and override `_on_start`, `_on_pause`, `_on_resume`, `_on_stop` hooks. **Hooks are called while the lock is held — must be non-blocking.**

---

## Adding a New Application

1. Copy `src/applications/APPLICATION_BLUEPRINT/` → `src/applications/my_application/`
2. Replace all `My`/`my`/`APPLICATION_BLUEPRINT` occurrences with your application name
3. Implement in order: `IMyService` → `StubMyService` → `MyApplicationService` → `MyModel` → `MyView` → `MyController` → `MyApplicationFactory`
4. Add a `_build_my_application()` factory function and `ApplicationSpec` to the RobotSystem (e.g. `application_wiring.py` + `glue_robot_system.py`)
5. Verify standalone runner: `python src/applications/my_application/example_usage.py`

See `src/applications/APPLICATION_BLUEPRINT/APPLICATION_GUIDE.MD` for the full step-by-step guide.

## Adding a New Robot System

Subclass `BaseRobotSystem`, declare `metadata`, `settings_specs`, `services`, and `shell` as class variables. Wire it in `src/bootstrap/main.py` via `SystemBuilder().with_robot(...).build(MyRobotSystem)`.

---

## Documentation

When making changes to any code inside `src/engine/`, ask the user whether
the corresponding documentation in `docs/engine/` should be updated before
finishing the task.

When making changes to any code inside `src/applications/`, ask the user whether
the corresponding documentation in `docs/applications/` should be updated before
finishing the task. Also ask whether `src/applications/APPLICATION_BLUEPRINT/APPLICATION_GUIDE.MD`
should be updated if the change introduces or modifies a shared pattern.

When making changes to any code inside `src/robot_systems/`, ask the user whether
the corresponding documentation in `docs/robot_systems/` should be updated before
finishing the task.

When making changes to any code inside `src/shared_contracts/`, ask the user
whether the corresponding documentation in `docs/shared_contracts/` should be
updated before finishing the task. The shared_contracts package is the canonical
topic-string and payload contract used across all layers — any topic or payload
change affects both publishers and subscribers throughout the codebase.
