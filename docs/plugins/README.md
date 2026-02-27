# `src/plugins/` — Plugin System

The `plugins` package contains all pluggable GUI features of the platform. Each plugin is a self-contained MVC unit wired into the shell at startup via `PluginSpec` entries on the robot app. Plugins are the only place in the codebase where the GUI and platform services meet.

---

## Architecture Overview

```
Bootstrap
  └─ PluginSpec.factory(robot_app)
       └─ IPlugin
            ├─ register(messaging_service)    ← receive broker reference at startup
            └─ create_widget()                ← lazy: called when user opens folder
                    └─ PluginFactory.build(service)
                         ├─ IPluginModel      ← state + I/O, no Qt
                         ├─ IPluginView       ← pure Qt, no logic
                         └─ IPluginController ← wires M ↔ V, broker subscriptions
```

Data flows in one direction only:

```
User action  →  View signal  →  Controller  →  Model  →  Service
Live data    →  Broker sub   →  Bridge      →  View setter
```

---

## Packages

| Package | Description |
|---------|-------------|
| `base/` | Abstract base classes: `IPlugin`, `PluginFactory`, `IPluginModel`, `IPluginView`, `IPluginController` |
| `PLUGIN_BLUEPRINT/` | Copy-paste template with full guide in `PLUGIN_GUIDE.MD` |
| `modbus_settings/` | Modbus serial port configuration — port detection + connection test |
| `glue_cell_settings/` | Weight cell configuration + live readings per cell |
| `robot_settings/` | Robot kinematics, safety limits, calibration, and movement group editor |

---

## Lifecycle

```
Bootstrap startup:
  for each PluginSpec in robot_app.shell.plugins:
    plugin = spec.factory(robot_app)          ← returns IPlugin instance
    plugin.register(messaging_service)        ← broker reference stored
    shell.register(plugin)                    ← stored for lazy widget creation

User opens folder:
  plugin.create_widget()                      ← instantiates view + controller
    └─ PluginFactory.build(service)
         ├─ _create_model(service)
         ├─ _create_view()
         ├─ _create_controller(model, view)
         ├─ controller.load()                 ← populate view from model
         └─ view._controller = controller     ← GC ownership fix
```

---

## Wiring a Plugin

In the robot app, add a module-level factory function and a `PluginSpec`:

```python
def _build_my_plugin(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.my_plugin.my_plugin_factory import MyPluginFactory
    from src.applications.my_plugin.service.my_plugin_service import MyPluginService

    service = MyPluginService(settings_service=robot_app._settings_service)
    factory = MyPluginFactory()
    return WidgetApplication(widget_factory=lambda _ms: factory.build(service))
    # If the plugin needs live broker data:
    # return WidgetApplication(widget_factory=lambda ms: factory.build(service, ms))


class YourRobotApp(BaseRobotApp):
    shell = ShellSetup(
        plugins=[
            PluginSpec(name="MyApplication", folder_id=2, icon="fa5s.cog", factory=_build_my_plugin),
        ],
    )
```

---

## Design Notes

- **Lazy widget creation**: `create_widget()` is only called when the user first navigates to that folder. Plugins are initialized at startup but widgets are not created until needed.
- **GC safety**: `PluginFactory.build()` assigns `view._controller = controller`, keeping the controller alive as long as the view exists. Never write this line yourself.
- **Layer separation**: Each layer has strict import rules — see `PLUGIN_BLUEPRINT/PLUGIN_GUIDE.MD`.
- **Cross-thread safety**: When broker callbacks arrive from background threads (e.g., weight readings), controllers use a `_Bridge(QObject)` with `pyqtSignal` attributes to marshal data back to the Qt main thread safely. See `glue_cell_settings/controller/`.
- **Blocking service calls**: When a service call may block the GUI (e.g., serial port detection), controllers dispatch a `QThread + _Worker` pair and track them in `_active: List[Tuple[QThread, _Worker]]`. See `modbus_settings/controller/`.
