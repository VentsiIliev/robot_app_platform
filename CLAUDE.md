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

**Run a plugin standalone (for development without the full platform):**
```bash
python src/applications/<plugin_name>/example_usage.py
```

No `pyproject.toml`, `setup.py`, or `requirements.txt` — dependencies are managed via the `.venv` directory.

## Architecture Overview

This is a **PyQt6-based platform** for controlling industrial robotic systems (FaiRino arm). It follows a **plugin-based, MVC architecture** with strict layering.

### Startup Sequence (`src/bootstrap/main.py`)

Six ordered steps — order matters:
1. `EngineContext.build()` — creates the `MessagingService` singleton
2. `AppBuilder().with_robot(...).with_messaging_service(...).build(GlueRobotApp)` — wires all services and settings
3. `ShellConfigurator.configure(GlueRobotApp)` — registers shell folder metadata
4. `QApplication(sys.argv)` — Qt must exist before any widgets
5. `PluginLoader` — iterates `GlueRobotApp.shell.plugins`, calls each `spec.factory(robot_app)`, then `plugin.register(messaging_service)`
6. `AppShell` — creates the main window and starts the Qt event loop

### Robot App (`src/robot_apps/`)

`BaseRobotApp` is the abstract base. Subclasses declare class-level specs (no instance state at class level):

- `metadata: AppMetadata` — identity and `settings_root`
- `settings_specs: List[SettingsSpec]` — which JSON files to load and their serializers
- `services: List[ServiceSpec]` — required/optional service contracts with type validation
- `shell: ShellSetup` — folders and plugin factories for the GUI

`AppBuilder` constructs the app: builds `SettingsService` from specs, builds `MotionService → RobotService → NavigationService`, then calls `app.start(services, settings_service)`.

`GlueRobotApp` (`src/robot_apps/glue/glue_robot_app.py`) is the concrete app. It declares 5 plugins and 6 settings files. Each plugin is wired via a module-level factory function in that file.

### Plugin Architecture

Every plugin lives in `src/plugins/<name>/` and follows a strict MVC pattern. The template is `src/applications/APPLICATION_BLUEPRINT/` with a comprehensive guide at `APPLICATION_BLUEPRINT/APPLICATION_GUIDE.MD`.

```
spec.factory(robot_app)
  └─ WidgetPlugin(IPlugin)
       └─ MyPluginFactory(PluginFactory).build(service)
            ├─ MyModel(IPluginModel)      ← state + I/O, no Qt
            ├─ MyView(IPluginView)        ← pure Qt, no logic
            └─ MyController(IPluginController) ← wires M ↔ V
```

Data flows one way: `User action → View signal → Controller → Model → Service`

**Layer import rules** (strictly enforced):
- `IMyService` / `MyPluginService` — the only boundary between plugin and platform; `MyPluginService` is the only file allowed to import `ISettingsService` / `IRobotService`
- `MyModel` — imports `IMyService` and stdlib only; **no Qt**
- `MyView` — imports Qt and `pl_gui` only; **no model, service, or controller**
- `MyController` — imports model, view, and `IMessagingService` only; **no services directly**

### Messaging (`src/engine/core/`)

`MessageBroker` is a singleton using **weak references** for automatic cleanup when widgets are destroyed. Always use `IMessagingService`, never `MessageBroker` directly. Supports pub/sub and request/response patterns.

**Critical:** Never use `lambda` or `.emit` as slot targets for PyQt6 signal connections — PyQt6 weak-references them and they are silently GC'd. Always use named bound methods.

The same rule applies to the `PluginFactory`: it assigns `view._controller = controller` automatically to keep the controller alive as long as the view. Never write this line in a factory subclass.

### Settings (`src/engine/repositories/`)

JSON-based persistence. Each setting is declared with a `SettingsSerializer` (implements `get_default()`, `to_dict()`, `from_dict()`). Settings files are stored under `storage/settings/<app_name>/`. Access via `robot_app.get_settings("key")` or `settings_service.get("key")`.

### Services

Default services built by `AppBuilder` for every robot app:
- `IRobotService` → `RobotService` (wraps `MotionService` + `RobotStateManager`)
- `NavigationService` — named position movements from settings
- `IToolService` — optional, skipped if no `tool_changer` provided

Optional services declared with `required=False` in `ServiceSpec` don't block startup if unavailable (e.g., weight cells, vision).

### GUI (`pl_gui/`)

**Treat `pl_gui/` as an external, read-only package.** It will eventually be distributed as an installable pip package. Do not modify any files inside `pl_gui/` — changes there will be lost when the package is updated. Consume its public API only (imports from `pl_gui`).

- `AppShell` — main window with a stacked widget; each plugin's widget is created lazily when the user navigates to its folder
- `FolderLauncher` — grid of app icons per folder
- Plugin views must inherit `IPluginView` (which extends `AppWidget`) to integrate with the shell

### Adding a New Plugin

1. Copy `src/applications/APPLICATION_BLUEPRINT/` → `src/plugins/my_plugin/`
2. Replace all `My`/`my`/`APPLICATION_BLUEPRINT` occurrences
3. Implement: `IMyService` interface → `StubMyService` → `MyPluginService` → `MyModel` → `MyView` → `MyController` → `MyPluginFactory`
4. Add a factory function and `PluginSpec` to the robot app (e.g., `glue_robot_app.py`)
5. Verify standalone runner works: `python src/plugins/my_plugin/example_usage.py`

### Adding a New Robot App

Subclass `BaseRobotApp`, declare `metadata`, `settings_specs`, `services`, and `shell` as class variables. Wire it in `src/bootstrap/main.py` via `AppBuilder().with_robot(...).build(MyRobotApp)`.

## Documentation

When making changes to any code inside `src/engine/`, ask the user whether
the corresponding documentation in `docs/engine/` should be updated before
finishing the task.

When making changes to any code inside `src/plugins/`, ask the user whether
the corresponding documentation in `docs/plugins/` should be updated before
finishing the task. Also ask whether `src/applications/APPLICATION_BLUEPRINT/PLUGIN_GUIDE.MD`
should be updated if the change introduces or modifies a shared pattern.

When making changes to any code inside `src/robot_apps/`, ask the user whether
the corresponding documentation in `docs/robot_apps/` should be updated before
finishing the task.

When making changes to any code inside `src/shared_contracts/`, ask the user
whether the corresponding documentation in `docs/shared_contracts/` should be
updated before finishing the task. The shared_contracts package is the canonical
topic-string and payload contract used across all layers — any topic or payload
change affects both publishers and subscribers throughout the codebase.