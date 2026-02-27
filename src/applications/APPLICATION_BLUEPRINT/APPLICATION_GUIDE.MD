# Application Implementation Guide

Every application in this platform follows the same MVC structure backed by a set of
base interfaces and a template-method factory.  
Copy `APPLICATION_BLUEPRINT/`, rename every occurrence of `My` / `my`, implement the
marked methods — the infrastructure handles the rest.

---

## Architecture at a Glance

```
Bootstrap
  └─ spec.factory(robot_system)
       └─ WidgetApplication(IApplication)              ← generic IApplication shell
            └─ MyApplicationFactory().build(service)   ← ApplicationFactory template method
                 ├─ MyModel(service)         ← IApplicationModel — state + I/O, no Qt
                 ├─ MyView                  ← IApplicationView  — pure Qt, no logic
                 └─ MyController            ← IApplicationController — wires M ↔ V
```

Data flows in one direction only:

```
User action  →  View signal  →  Controller  →  Model  →  Service
Live data    →  Broker sub   →  Controller  →  View setter
```

---

## Base Interfaces (src/applications/base/)

| Class | Role |
|---|---|
| `IApplication` | Bootstrap contract — `register(messaging_service)` + `create_widget()` |
| `WidgetApplication` | Generic `IApplication` adapter — wraps any `widget_factory` callable |
| `IApplicationModel` | Enforces `load()` + `save()` on every model |
| `IApplicationView` | Extends `AppWidget` — enforces `setup_ui()` + `clean_up()` |
| `IApplicationController` | Enforces `load()` + `stop()` on every controller |
| `ApplicationFactory` | Template-method base — owns wiring order, GC fix, `load()` call |

---

## Full File Structure

```
src/applications/my_application/
  __init__.py                        expose MyApplication + IMyService only
  my_application.py                       IApplication entry point (thin shell)
  my_application_factory.py               ApplicationFactory subclass — 3 factory methods
  service/
    __init__.py
    i_my_service.py                  ABC — application's contract with the platform
    my_application_service.py             adapter: ISettingsService/IRobotService → IMyService
    stub_my_service.py               hardcoded impl for dev & unit tests
  model/
    __init__.py
    my_model.py                      IApplicationModel — in-memory state, delegates I/O
  view/
    __init__.py
    my_view.py                       IApplicationView  — pure Qt, signals out / setters in
  controller/
    __init__.py
    my_controller.py                 IApplicationController — wires signals, broker subs
  example_usage.py                   standalone runner + wiring snippet
```

---

## Step 1 — Create the package

Create `src/applications/my_application/` and copy every file from `APPLICATION_BLUEPRINT/`.  
Replace every `My` / `my` / `APPLICATION_BLUEPRINT` with your application name.

```
APPLICATION_BLUEPRINT/   →   my_application/
MyApplication            →   MyApplication
IMyService          →   IMyService
MyApplicationFactory     →   MyApplicationFactory
MyModel             →   MyModel
MyView              →   MyView
MyController        →   MyController
```

Add an empty `__init__.py` to every subfolder:
`service/`, `model/`, `view/`, `controller/`.

---

## Step 2 — Define the service interface
**File:** `service/i_my_service.py`

This is the **only boundary** between your application and the rest of the platform.  
Add one method per piece of data or action your application needs.  
Never accept `ISettingsService` or `IRobotService` directly inside the application.

```python
from abc import ABC, abstractmethod

class IMyService(ABC):

    # Queries — data the application needs to display
    @abstractmethod
    def get_value(self) -> str: ...

    # Commands — actions triggered by the user
    @abstractmethod
    def save_value(self, value: str) -> None: ...
```

**Rule:** queries return data, commands return `None`.

---

## Step 3 — Write the stub
**File:** `service/stub_my_service.py`

Implement every method with a `print` or a hardcoded return.  
Use this to develop and test the application without a real robot app.

```python
from src.applications.my_application.service.i_my_service import IMyService


class StubMyService(IMyService):

    def get_value(self) -> str:
        print("[MyApplication] get_value → stub_value")
        return "stub_value"

    def save_value(self, value: str) -> None:
        print(f"[MyApplication] save_value → {value!r}")
```

---

## Step 4 — Implement the service adapter
**File:** `service/my_application_service.py`

This is the **only file** allowed to import platform internals
(`ISettingsService`, `IRobotService`, etc.).

```python
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.applications.my_application.service.i_my_service import IMyService


class MyApplicationService(IMyService):

    def __init__(self, settings_service: ISettingsService):
        self._settings = settings_service

    def get_value(self) -> str:
        return self._settings.get("my_setting_key")

    def save_value(self, value: str) -> None:
        self._settings.save("my_setting_key", value)
```

If your application also needs robot control:

```python
def __init__(self, robot_service: IRobotService, settings_service: ISettingsService):
    self._robot    = robot_service
    self._settings = settings_service
```

---

## Step 5 — Build the model
**File:** `model/my_model.py`

Inherits `IApplicationModel` — enforces `load()` and `save()`.  
Holds in-memory state. Delegates all I/O to the service.  
**No Qt imports. No view imports.**

```python
import logging
from typing import Optional

from src.applications.base.i_application_model import IApplicationModel
from src.applications.my_application.service.i_my_service import IMyService


class MyModel(IApplicationModel):

    def __init__(self, service: IMyService):
        self._service = service
        self._value: Optional[str] = None
        self._logger = logging.getLogger(self.__class__.__name__)

    def load(self) -> str:
        self._value = self._service.get_value()
        self._logger.debug("Loaded: %s", self._value)
        return self._value

    def save(self, value: str, **kwargs) -> None:
        self._service.save_value(value)
        self._value = value
        self._logger.info("Saved: %s", value)
```

---

## Step 6 — Build the view
**File:** `view/my_view.py`

Inherits `IApplicationView` which extends `AppWidget` — required by the shell.  
Override `setup_ui()` to build your widgets.  
**No service imports. No model imports. No business logic.**

### Signal forwarding rule
> **Never** connect an internal widget signal directly to an outbound `pyqtSignal.emit`  
> or use a `lambda` for forwarding.  
> PyQt6 weak-references `lambda` callbacks — they are silently GC'd and the connection dies.  
> Always use a **named bound method** as the forwarder slot.

```python
from PyQt6.QtCore import pyqtSignal, QEvent
from PyQt6.QtWidgets import QLabel, QVBoxLayout

from src.applications.base.i_application_view import IApplicationView


class MyView(IApplicationView):
    # Outbound signals — one per user action
    save_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("MyApplication", parent)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel("Value: —")
        layout.addWidget(self._label)

        # ✓ Use named method — NOT lambda or signal.emit directly
        # self._btn.clicked.connect(self._on_inner_save)

    # ── Named forwarders — bind internal → outbound signals ──────────────

    def _on_inner_save(self, value: str) -> None:
        self.save_requested.emit(value)  # ✓ named method, strong ref

    # ── Inbound setters — controller pushes data in ───────────────────────

    def set_value(self, value: str) -> None:
        self._label.setText(f"Value: {value}")

    # ── AppWidget hooks ───────────────────────────────────────────────────

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.LanguageChange:
            self.on_language_changed()
        super().changeEvent(event)

    def clean_up(self) -> None:
        pass  # stop timers / threads here
```

**Rules:**
- Every user action = one `pyqtSignal` out
- Every data push = one setter in
- The view never calls the model
- Never use `lambda` or `.emit` references as connection targets

---

## Step 7 — Build the controller
**File:** `controller/my_controller.py`

Inherits `IApplicationController` — enforces `load()` and `stop()`.  
The **only** class allowed to touch both model and view.  
On construction: wire signals. In `load()`: populate the view from the model.

```python
import logging

from src.applications.base.i_application_controller import IApplicationController
from src.applications.my_application.model.my_model import MyModel
from src.applications.my_application.view.my_view import MyView


class MyController(IApplicationController):

    def __init__(self, model: MyModel, view: MyView):
        self._model = model
        self._view = view
        self._logger = logging.getLogger(self.__class__.__name__)

        self._view.save_requested.connect(self._on_save)
        self._view.destroyed.connect(self.stop)

    def load(self) -> None:
        value = self._model.load()
        self._view.set_value(value)

    def stop(self) -> None:
        pass  # unsubscribe from broker topics here

    def _on_save(self, value: str) -> None:
        try:
            self._model.save(value)
            self._logger.info("Saved: %s", value)
        except Exception:
            self._logger.exception("Failed to save")
```

If your application subscribes to broker topics for live data:

```python
from src.engine.core.i_messaging_service import IMessagingService

class MyController(IApplicationController):

    def __init__(self, model: MyModel, view: MyView, messaging_service: IMessagingService):
        ...
        self._messaging_service = messaging_service
        self._subs = []

    def load(self) -> None:
        self._subscribe()
        value = self._model.load()
        self._view.set_value(value)

    def _subscribe(self) -> None:
        cb = self._on_live_update          # ✓ named bound method — strong ref
        self._messaging_service.subscribe("some/topic", cb)
        self._subs.append(("some/topic", cb))

    def _on_live_update(self, data) -> None:
        self._view.set_value(str(data))

    def stop(self) -> None:
        for topic, cb in reversed(self._subs):
            try: self._messaging_service.unsubscribe(topic, cb)
            except Exception: pass
        self._subs.clear()
```

### Cross-thread broker callbacks — `_Bridge(QObject)` pattern

If broker callbacks arrive from **background threads** (e.g., weight readings from `WeightCellService`), calling Qt setters directly is unsafe. Use a `_Bridge(QObject)` with `pyqtSignal` attributes — PyQt6 automatically queues cross-thread signal delivery to the main thread.

```python
from PyQt6.QtCore import QObject, pyqtSignal

class _Bridge(QObject):
    data_updated = pyqtSignal(int, float)   # (id, value)

class MyController(IApplicationController):

    def __init__(self, model, view, messaging_service):
        ...
        self._bridge = _Bridge()
        self._bridge.data_updated.connect(self._view.set_value)

    def _subscribe(self) -> None:
        cb = lambda data, uid=item_id: self._bridge.data_updated.emit(uid, data.value)
        self._messaging_service.subscribe("some/topic", cb)
        self._subs.append(("some/topic", cb))
```

`_Bridge` must be stored as `self._bridge` — it must stay alive as long as the controller.

---

### Blocking service calls — `QThread + _Worker` pattern

If a service method may block the GUI (e.g., serial port scan, HTTP request), dispatch it to a worker thread:

```python
from PyQt6.QtCore import QObject, QThread, pyqtSignal
from typing import Callable, List, Tuple

class _Worker(QObject):
    finished = pyqtSignal(object)

    def __init__(self, fn: Callable): self._fn = fn

    def run(self) -> None:
        self.finished.emit(self._fn())

class MyController(IApplicationController):

    def __init__(self, model, view):
        ...
        self._active: List[Tuple[QThread, _Worker]] = []
        self._view.detect_requested.connect(self._on_detect)

    def _on_detect(self) -> None:
        self._view.set_busy(True)
        thread = QThread()
        worker = _Worker(fn=self._model.detect)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_detect_ready)
        worker.finished.connect(thread.quit)
        self._active.append((thread, worker))
        thread.start()

    def _on_detect_ready(self, result) -> None:
        self._view.set_result(result)
        self._view.set_busy(False)
        self._active = [(t, w) for t, w in self._active if t.isRunning()]

    def stop(self) -> None:
        for topic, cb in reversed(self._subs):
            try: self._messaging_service.unsubscribe(topic, cb)
            except Exception: pass
        self._subs.clear()
        for thread, _ in reversed(self._active):
            thread.quit(); thread.wait(2000)
        self._active.clear()
```

Store threads in `_active` to prevent immediate GC. Clean up in `stop()`.

---

## Step 8 — Wire the MVC in the factory
**File:** `my_application_factory.py`

Subclass `ApplicationFactory` and implement three factory methods.  
`ApplicationFactory.build()` handles the wiring order, `controller.load()`, and the GC fix automatically.

### The GC fix (handled automatically by ApplicationFactory)
> PyQt6 uses **weak references** for Python bound-method slot connections.  
> If no strong reference holds the controller after the factory returns, it is
> immediately garbage collected and all signal connections die silently.  
> `ApplicationFactory.build()` assigns `view._controller = controller` — transferring
> ownership to the view so the controller lives as long as the widget does.  
> **Never write this line yourself — it is already in `ApplicationFactory.build()`.**

```python
from __future__ import annotations

from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.application_factory import ApplicationFactory
from src.applications.my_application.controller.my_controller import MyController
from src.applications.my_application.model.my_model import MyModel
from src.applications.my_application.service.i_my_service import IMyService
from src.applications.my_application.view.my_view import MyView


class MyApplicationFactory(ApplicationFactory):

    def _create_model(self, service: IMyService) -> IApplicationModel:
        return MyModel(service)

    def _create_view(self) -> IApplicationView:
        return MyView()

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        return MyController(model, view)
```

`ApplicationFactory.build(service)` calls these three methods in order, then:
1. calls `controller.load()`
2. assigns `view._controller = controller`
3. logs the build
4. returns the view

---

## Step 9 — Create the IApplication entry point
**File:** `my_application.py`

Thin shell. Receives only what this application needs — never the whole `robot_app`.  
Delegates `create_widget()` entirely to the factory.

```python
import logging

from pl_gui.shell.base_app_widget.AppWidget import AppWidget
from src.engine.core.i_messaging_service import IMessagingService
from src.applications.base.application_interface import IApplication
from src.applications.my_application.my_application_factory import MyApplicationFactory
from src.applications.my_application.service.my_application_service import MyApplicationService


class MyApplication(IApplication):

    def __init__(self, settings_service=None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._service = MyApplicationService(settings_service)

    def register(self, messaging_service: IMessagingService) -> None:
        self._logger.debug("MyApplication registered")

    def create_widget(self) -> AppWidget:
        return MyApplicationFactory().build(self._service)
```

---

## Step 10 — Expose the public API
**File:** `__init__.py`

Expose only `MyApplication` and `IMyService`. Nothing else belongs in the public API.

```python
from src.applications.my_application.my_application import MyApplication
from src.applications.my_application.service.i_my_service import IMyService

__all__ = ["MyApplication", "IMyService"]
```

---

## Step 11 — Declare settings (if needed)

If your application persists settings, add a dataclass + serializer.  
Place it in `src/applications/my_application/settings/` or, if shared across apps,
in `src/engine/robot/configuration/` alongside `robot_settings.py`.

```python
from dataclasses import dataclass
from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer

@dataclass
class MySettings:
    my_value: str = "default"

    @classmethod
    def from_dict(cls, data: dict) -> 'MySettings':
        return cls(my_value=data.get("my_value", "default"))

    def to_dict(self) -> dict:
        return {"my_value": self.my_value}


class MySettingsSerializer(ISettingsSerializer[MySettings]):

    @property
    def settings_type(self) -> str:
        return "my_settings"

    def get_default(self) -> MySettings:
        return MySettings()

    def to_dict(self, s: MySettings) -> dict:
        return s.to_dict()

    def from_dict(self, data: dict) -> MySettings:
        return MySettings.from_dict(data)
```

---

## Step 12 — Wire into the robot system
**File:** `src/robot_systems/your_system/your_robot_system.py`

Add a module-level factory function returning a `WidgetApplication`.  
`WidgetApplication` is the **only** `IApplication` implementation — `ApplicationSpec.name` is
the registry identity, not the class name.

```python
from src.robot_systems.base_robot_system import (
    SystemMetadata, BaseRobotSystem, FolderSpec, ApplicationSpec,
    SettingsSpec, ShellSetup,
)
from src.applications.my_application.settings import MySettingsSerializer


# ── factory function (module-level, lazy imports inside) ─────────────────

def _build_my_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.my_application.my_application_factory import MyApplicationFactory
    from src.applications.my_application.service.my_application_service import MyApplicationService

    service = MyApplicationService(
        settings_service=robot_system._settings_service,
        # robot_service=robot_system.get_service("robot"),
    )
    factory = MyApplicationFactory()
    return WidgetApplication(
        widget_factory=lambda _ms: factory.build(service)
        # If the application needs live data from the broker:
        # widget_factory=lambda ms: factory.build(service, ms)
    )


class YourRobotSystem(BaseRobotSystem):
    metadata = SystemMetadata(name="YourSystem", version="1.0.0")

    shell = ShellSetup(
        folders=[
            FolderSpec(folder_id=1, name="PRODUCTION", display_name="Production"),
            FolderSpec(folder_id=2, name="SERVICE", display_name="Service"),
        ],
        applications=[
            ApplicationSpec(
                name="MyApplication",  # registry key — shown in shell menu
                folder_id=2,  # must match a FolderSpec above
                icon="fa5s.cog",  # any qtawesome icon string
                factory=_build_my_application,
            ),
        ],
    )

    settings_specs = [
        SettingsSpec("my_settings", MySettingsSerializer(), "my/settings.json"),
    ]

    def on_start(self) -> None:
        self._my_settings = self.get_settings("my_settings")

    def on_stop(self) -> None:
        pass
```

Bootstrap automatically:
- calls `spec.factory(robot_system)` → gets the `WidgetApplication` instance
- calls `application.register(messaging_service)`
- calls `application.create_widget()` when the user opens that folder

---

## Step 13 — Run standalone (dev / demo)
**File:** `example_usage.py`

Use the stub service to run your application without the full platform:

```python
def run_standalone() -> None:
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from src.applications.my_application.my_application_factory import MyApplicationFactory
    from src.applications.my_application.service.stub_my_service import StubMyService

    app = QApplication(sys.argv)
    widget = MyApplicationFactory().build(StubMyService())

    window = QMainWindow()
    window.setCentralWidget(widget)
    window.resize(1280, 900)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()
```

---

## Layer Rules (what each layer may import)

| Layer | May import | Must NOT import |
|---|---|---|
| `IApplication` / `WidgetApplication` | `IMyService`, factory | `ISettingsService`, `IRobotService` directly |
| `IMyService` | stdlib only | anything platform |
| `MyApplicationService` | platform services | Qt, model, view, controller |
| `MyModel` (`IApplicationModel`) | `IMyService`, stdlib | Qt, view, controller |
| `MyView` (`IApplicationView`) | Qt, `pl_gui` | model, service, broker, controller |
| `MyController` (`IApplicationController`) | model, view, `IMessagingService` | services, `ISettingsService` |
| `MyApplicationFactory` (`ApplicationFactory`) | model, view, controller, service | broker directly |

---

## Critical Rules Summary

| Rule | Why |
|---|---|
| Inherit `IApplicationModel` on every model | Enforces `load()` + `save()` contract |
| Inherit `IApplicationView` on every view | Enforces `setup_ui()` + `clean_up()`, provides `AppWidget` shell integration |
| Inherit `IApplicationController` on every controller | Enforces `load()` + `stop()` lifecycle |
| Subclass `ApplicationFactory`, not a static method | GC fix and `load()` call are automatic, never duplicated |
| Use named methods for signal forwarding, never `lambda` or `.emit` | PyQt6 weak-refs lambdas — connections silently die |
| `view._controller = controller` is in `ApplicationFactory.build()` — never write it yourself | Prevents duplicating the ownership transfer in every factory |
| Use `IMessagingService`, never `MessageBroker` directly | Keeps the broker swappable; `MessageBroker` is an implementation detail |

---

## Real Examples in This Codebase

| Application | Factory | Service interface | Broker needed | Special patterns |
|---|---|---|---|---|
| `RobotSettings` | `RobotSettingsFactory(ApplicationFactory)` | `IRobotSettingsService` | No — `lambda _ms:` | — |
| `ModbusSettings` | `ModbusSettingsFactory(ApplicationFactory)` | `IModbusSettingsService` + `IModbusActionService` | No — `lambda _ms:` | `QThread + _Worker` for blocking port scan / connection test |
| `GlueCellSettings` | `GlueCellSettingsFactory` (custom `build`) | `IGlueCellSettingsService` | Yes — `lambda ms:` | `_Bridge(QObject)` for cross-thread weight readings |
| `GlueDashboard` | `GlueDashboard.create()` | `IGlueDashboardService` | Yes — `lambda ms:` | — |

---

## Quick Checklist

- [ ] Step 1  — Package created, `APPLICATION_BLUEPRINT` replaced everywhere
- [ ] Step 2  — `IMyService` defines all queries and commands
- [ ] Step 3  — `StubMyService` implements every method with print / hardcoded values
- [ ] Step 4  — `MyApplicationService` adapts platform services to `IMyService`
- [ ] Step 5  — `MyModel` inherits `IApplicationModel`, zero Qt
- [ ] Step 6  — `MyView` inherits `IApplicationView`, named forwarders, zero logic
- [ ] Step 7  — `MyController` inherits `IApplicationController`, `stop()` cleans up broker
- [ ] Step 8  — `MyApplicationFactory` inherits `ApplicationFactory`, implements 3 factory methods
- [ ] Step 9  — `MyApplication` calls `MyApplicationFactory().build(service)` in `create_widget()`
- [ ] Step 10 — `__init__.py` exposes only `MyApplication` + `IMyService`
- [ ] Step 11 — Settings dataclass + serializer declared (if needed)
- [ ] Step 12 — `WidgetApplication` + factory function wired into robot app via `ApplicationSpec`
- [ ] Step 13 — Standalone runner works with `StubMyService`

