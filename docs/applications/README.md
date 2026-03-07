# `src/applications/` — Application System

The `applications` package contains all pluggable GUI features of the platform. Each application is a self-contained MVC unit wired into the shell at startup via `ApplicationSpec` entries on the robot system. Applications are the only place in the codebase where the GUI and platform services meet.

---

## Architecture Overview

```
Bootstrap
  └─ ApplicationSpec.factory(robot_system)
       └─ IApplication
            ├─ register(messaging_service)    ← receive broker reference at startup
            └─ create_widget()                ← lazy: called when user opens folder
                    └─ ApplicationFactory.build(service)
                         ├─ IApplicationModel      ← state + I/O, no Qt
                         ├─ IApplicationView       ← pure Qt, no logic
                         └─ IApplicationController ← wires M ↔ V, broker subscriptions
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
| `base/` | Abstract base classes: `IApplication`, `ApplicationFactory`, `IApplicationModel`, `IApplicationView`, `IApplicationController` |
| `APPLICATION_BLUEPRINT/` | Copy-paste template with full guide in `APPLICATION_GUIDE.MD` |
| `modbus_settings/` | Modbus serial port configuration — port detection + connection test |
| `glue_cell_settings/` | Weight cell configuration + live readings per cell |
| `robot_settings/` | Robot kinematics, safety limits, calibration, and movement group editor |
| `camera_settings/` | Camera resolution, brightness, thresholds, and work area configuration |
| `calibration/` | Robot-to-camera calibration workflow (ArUco marker capture + solve) |
| `broker_debug/` | Live message broker inspector — spy on topics, publish test messages |
| `workpiece_editor/` | Contour-based workpiece path editor with vision overlay |
| `workpiece_library/` | Workpiece catalogue — browse, edit metadata, delete entries |
| `tool_settings/` | Tool changer configuration (grip offsets, tool type selection) |
| `user_management/` | User account management backed by a CSV repository |
| `contour_matching_tester/` | Offline workpiece-to-contour match testing tool |

---

## Lifecycle

```
Bootstrap startup:
  for each ApplicationSpec in robot_system.shell.applications:
    application = spec.factory(robot_system)          ← returns IApplication instance
    application.register(messaging_service)        ← broker reference stored
    shell.register(application)                    ← stored for lazy widget creation

User opens folder:
  application.create_widget()                      ← instantiates view + controller
    └─ ApplicationFactory.build(service)
         ├─ _create_model(service)
         ├─ _create_view()
         ├─ _create_controller(model, view)
         ├─ controller.load()                 ← populate view from model
         └─ view._controller = controller     ← GC ownership fix
```

---

## Wiring a Application

In the robot system, add a module-level factory function and a `ApplicationSpec`:

```python
def _build_my_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.my_application.my_application_factory import MyApplicationFactory
    from src.applications.my_application.service.my_application_service import MyApplicationService

    service = MyApplicationService(settings_service=robot_system._settings_service)
    factory = MyApplicationFactory()
    return WidgetApplication(widget_factory=lambda _ms: factory.build(service))
    # If the application needs live broker data:
    # return WidgetApplication(widget_factory=lambda ms: factory.build(service, ms))


class YourRobotApp(BaseRobotSystem):
    shell = ShellSetup(
        applications=[
            ApplicationSpec(name="MyApplication", folder_id=2, icon="fa5s.cog", factory=_build_my_application),
        ],
    )
```

---

## Design Notes

- **Lazy widget creation**: `create_widget()` is only called when the user first navigates to that folder. Applications are initialized at startup but widgets are not created until needed.
- **GC safety**: `ApplicationFactory.build()` assigns `view._controller = controller`, keeping the controller alive as long as the view exists. Never write this line yourself.
- **Layer separation**: Each layer has strict import rules — see `APPLICATION_BLUEPRINT/APPLICATION_GUIDE.MD`.
- **Cross-thread safety**: When broker callbacks arrive from background threads (e.g., weight readings), controllers use a `_Bridge(QObject)` with `pyqtSignal` attributes to marshal data back to the Qt main thread safely. See `glue_cell_settings/controller/`.
- **Blocking service calls**: When a service call may block the GUI (e.g., serial port detection), controllers dispatch a `QThread + _Worker` pair and track them in `_active: List[Tuple[QThread, _Worker]]`. See `modbus_settings/controller/`.
