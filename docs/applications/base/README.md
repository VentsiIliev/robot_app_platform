# `src/applications/base/` — Application Infrastructure

This package defines the abstract contracts and the generic wiring implementation shared by all applications. No application-specific logic lives here — only the interfaces and the template-method factory.

---

## Class Hierarchy

```
IApplication (ABC)
  └── WidgetApplication          ← generic shell; wraps any widget_factory callable

IApplicationModel (ABC)
  └── [application].Model        ← e.g. ModbusSettingsModel

IApplicationView (AppWidget, ABC)
  └── [application].View         ← e.g. RobotSettingsView

IApplicationController (ABC)
  └── [application].Controller   ← e.g. GlueCellSettingsController

ApplicationFactory (ABC)
  └── [application].Factory      ← template method: build(service) → IApplicationView
```

---

## API Reference

### `IApplication`

**File:** `application_interface.py`

```python
class IApplication(ABC):
    @abstractmethod
    def register(self, messaging_service: IMessagingService) -> None: ...

    @abstractmethod
    def create_widget(self) -> AppWidget: ...
```

Called by the bootstrap in two phases:
1. `register(messaging_service)` — called at startup; store the broker reference here
2. `create_widget()` — called lazily when the user opens the application's folder; must return the root widget

---

### `WidgetApplication`

**File:** `widget_application.py`

```python
class WidgetApplication(IApplication):
    def __init__(self, widget_factory: Callable[[IMessagingService], AppWidget]): ...
    def register(self, messaging_service: IMessagingService) -> None: ...
    def create_widget(self) -> AppWidget: ...
```

Generic `IApplication` adapter. Stores `widget_factory` and calls it with `messaging_service` in `create_widget()`. The `messaging_service` is captured in `register()`.

```python
# Application does not need broker:
WidgetApplication(widget_factory=lambda _ms: factory.build(service))

# Application needs broker for live data subscriptions:
WidgetApplication(widget_factory=lambda ms: factory.build(service, ms))
```

---

### `ApplicationFactory`

**File:** `application_factory.py`

```python
class ApplicationFactory(ABC):
    def build(self, *args, **kwargs) -> IApplicationView: ...   # template method

    @abstractmethod
    def _create_model(self, *args) -> IApplicationModel: ...

    @abstractmethod
    def _create_view(self) -> IApplicationView: ...

    @abstractmethod
    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController: ...
```

`build()` calls the three abstract methods in order, then:
1. Calls `controller.load()` — populates the view from the model
2. Assigns `view._controller = controller` — GC ownership fix (never write this yourself)
3. Logs the build at DEBUG level
4. Returns the `view`

---

### `IApplicationModel`

**File:** `i_application_model.py`

```python
class IApplicationModel(ABC):
    @abstractmethod
    def load(self) -> Any: ...

    @abstractmethod
    def save(self, *args, **kwargs) -> None: ...
```

---

### `IApplicationView`

**File:** `i_application_view.py`

```python
class IApplicationView(AppWidget):
    @abstractmethod
    def setup_ui(self) -> None: ...

    @abstractmethod
    def clean_up(self) -> None: ...
```

Extends `AppWidget` from `pl_gui` — required for shell integration. `setup_ui()` is called by `AppWidget.__init__` after all instance attributes are set. `clean_up()` is for stopping timers or threads when the widget is destroyed.

---

### `IApplicationController`

**File:** `i_application_controller.py`

```python
class IApplicationController(ABC):
    @abstractmethod
    def load(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...
```

`load()` is called once by `ApplicationFactory.build()` after construction. `stop()` should unsubscribe from all broker topics and is typically connected to `view.destroyed`.

---

## Data Flow

```
ApplicationFactory.build(service)
      │
      ├─ _create_model(service) → model
      ├─ _create_view()         → view
      ├─ _create_controller(model, view) → controller
      │
      ├─ controller.load()          ← populate view from model
      ├─ view._controller = controller  ← GC ownership fix
      └─ return view
```

---

## Design Notes

- **GC ownership**: PyQt6 weak-references Python bound methods as signal slots. If no strong ref holds the controller, it is GC'd and all signal connections die silently. `ApplicationFactory.build()` assigns `view._controller = controller` to transfer ownership to the view.
- **`IApplicationView` extends `AppWidget`**: Required for shell integration. `AppWidget` provides `on_language_changed()` and the hooks `AppShell` uses to show/hide panels.
- **`WidgetApplication` is the universal adapter**: The bootstrap works with `IApplication` references. `WidgetApplication` decouples the typed factory from the bootstrap protocol, enabling lazy widget creation.
- **`build()` is the only entry point**: Subclasses implement `_create_model`, `_create_view`, `_create_controller` only. The wiring order and GC fix are handled by the base class exactly once.
