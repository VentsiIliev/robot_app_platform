# `src/plugins/base/` — Plugin Infrastructure

This package defines the abstract contracts and the generic wiring implementation shared by all plugins. No plugin-specific logic lives here — only the interfaces and the template-method factory.

---

## Class Hierarchy

```
IPlugin (ABC)
  └── WidgetPlugin          ← generic shell; wraps any widget_factory callable

IPluginModel (ABC)
  └── [plugin].Model        ← e.g. ModbusSettingsModel

IPluginView (AppWidget, ABC)
  └── [plugin].View         ← e.g. RobotSettingsView

IPluginController (ABC)
  └── [plugin].Controller   ← e.g. GlueCellSettingsController

PluginFactory (ABC)
  └── [plugin].Factory      ← template method: build(service) → IPluginView
```

---

## API Reference

### `IPlugin`

**File:** `plugin_interface.py`

```python
class IPlugin(ABC):
    @abstractmethod
    def register(self, messaging_service: IMessagingService) -> None: ...

    @abstractmethod
    def create_widget(self) -> AppWidget: ...
```

Called by the bootstrap in two phases:
1. `register(messaging_service)` — called at startup; store the broker reference here
2. `create_widget()` — called lazily when the user opens the plugin's folder; must return the root widget

---

### `WidgetPlugin`

**File:** `widget_plugin.py`

```python
class WidgetPlugin(IPlugin):
    def __init__(self, widget_factory: Callable[[IMessagingService], AppWidget]): ...
    def register(self, messaging_service: IMessagingService) -> None: ...
    def create_widget(self) -> AppWidget: ...
```

Generic `IPlugin` adapter. Stores `widget_factory` and calls it with `messaging_service` in `create_widget()`. The `messaging_service` is captured in `register()`.

```python
# Plugin does not need broker:
WidgetPlugin(widget_factory=lambda _ms: factory.build(service))

# Plugin needs broker for live data subscriptions:
WidgetPlugin(widget_factory=lambda ms: factory.build(service, ms))
```

---

### `PluginFactory`

**File:** `plugin_factory.py`

```python
class PluginFactory(ABC):
    def build(self, *args, **kwargs) -> IPluginView: ...   # template method

    @abstractmethod
    def _create_model(self, *args) -> IPluginModel: ...

    @abstractmethod
    def _create_view(self) -> IPluginView: ...

    @abstractmethod
    def _create_controller(self, model: IPluginModel, view: IPluginView) -> IPluginController: ...
```

`build()` calls the three abstract methods in order, then:
1. Calls `controller.load()` — populates the view from the model
2. Assigns `view._controller = controller` — GC ownership fix (never write this yourself)
3. Logs the build at DEBUG level
4. Returns the `view`

---

### `IPluginModel`

**File:** `i_plugin_model.py`

```python
class IPluginModel(ABC):
    @abstractmethod
    def load(self) -> Any: ...

    @abstractmethod
    def save(self, *args, **kwargs) -> None: ...
```

---

### `IPluginView`

**File:** `i_plugin_view.py`

```python
class IPluginView(AppWidget):
    @abstractmethod
    def setup_ui(self) -> None: ...

    @abstractmethod
    def clean_up(self) -> None: ...
```

Extends `AppWidget` from `pl_gui` — required for shell integration. `setup_ui()` is called by `AppWidget.__init__` after all instance attributes are set. `clean_up()` is for stopping timers or threads when the widget is destroyed.

---

### `IPluginController`

**File:** `i_plugin_controller.py`

```python
class IPluginController(ABC):
    @abstractmethod
    def load(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...
```

`load()` is called once by `PluginFactory.build()` after construction. `stop()` should unsubscribe from all broker topics and is typically connected to `view.destroyed`.

---

## Data Flow

```
PluginFactory.build(service)
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

- **GC ownership**: PyQt6 weak-references Python bound methods as signal slots. If no strong ref holds the controller, it is GC'd and all signal connections die silently. `PluginFactory.build()` assigns `view._controller = controller` to transfer ownership to the view.
- **`IPluginView` extends `AppWidget`**: Required for shell integration. `AppWidget` provides `on_language_changed()` and the hooks `AppShell` uses to show/hide panels.
- **`WidgetPlugin` is the universal adapter**: The bootstrap works with `IPlugin` references. `WidgetPlugin` decouples the typed factory from the bootstrap protocol, enabling lazy widget creation.
- **`build()` is the only entry point**: Subclasses implement `_create_model`, `_create_view`, `_create_controller` only. The wiring order and GC fix are handled by the base class exactly once.
