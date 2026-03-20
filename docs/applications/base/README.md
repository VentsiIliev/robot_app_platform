# `src/applications/base/` — Application Infrastructure

This package defines the abstract contracts and the generic wiring implementation shared by all applications. No application-specific logic lives here — only the interfaces and the template-method factory.

It also contains reusable UI infrastructure that is safe to share across applications, such as styled dialogs and the broker-backed user notification presenter.

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

### `UserNotificationPresenter`

**File:** `notification_presenter.py`

Reusable application-layer presenter for user-facing notifications published on the message broker.

Responsibilities:
- subscribe to `NotificationTopics.USER`
- resolve localization-ready notification keys into display text
- fall back to provided English text when no translation is available
- present the notification with the shared [styled message box](/home/ilv/Desktop/robot_app_platform/src/applications/base/styled_message_box.py)

The presenter intentionally lives in `src/applications/base/` because it depends on Qt and dialog rendering. Backend layers must not import it.

Use it from controllers:

```python
self._notifications = UserNotificationPresenter(self._view, broker, translate=self._t)
self._notifications.start()
...
self._notifications.stop()
```

For now it shows modal dialogs via:
- `show_info(...)`
- `show_warning(...)`
- `show_critical(...)`

It also supports simple consecutive deduplication via `dedupe_key`.

---

### `NotificationTextResolver`

**File:** `notification_presenter.py`

Small helper used by `UserNotificationPresenter` to make the notification mechanism localization-ready.

Resolution order:
1. use `title_key` / `message_key` if a translation function returns a localized template
2. otherwise use `fallback_title` / `fallback_message`
3. apply `str.format(**params)` if formatting parameters are provided

This keeps translation at the UI boundary instead of pushing localized strings into engine or robot-system code.

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

## `RobotJogWidget`

**File:** `robot_jog_widget.py`

A reusable Qt widget that provides manual robot jogging controls with directional buttons, step-size selection, and frame/end-effector selection.

### Frame Selector

The widget includes a `QComboBox` labeled **"Frame:"** in its bottom row. It allows the operator to select which end-effector point the jog motion is relative to.

```python
# Signals
frame_changed = pyqtSignal(str)   # emitted when operator selects a different frame

# Public API
def set_frame_options(self, names: List[str], default: Optional[str] = None) -> None:
    """Populate the combo box with the given names; optionally set the active selection."""

def set_frame(self, name: str) -> None:
    """Programmatically select a frame without emitting frame_changed."""

def get_frame(self) -> str:
    """Return the currently selected frame name, or '' if not set."""
```

`set_frame()` is intentionally signal-free so a parent widget can keep a button and the combo box in sync without triggering an infinite signal loop.

### Integration in `PickTarget`

The `PickTargetView` populates the combo with the three canonical end-effector names (`camera_center`, `tool`, `gripper`) and connects `frame_changed` to `_on_jog_frame_changed`. The existing **Target:** button on the control panel does the same thing — both selectors are kept in sync via `_apply_target(sync_jog=True/False)`.

---

## Design Notes

- **GC ownership**: PyQt6 weak-references Python bound methods as signal slots. If no strong ref holds the controller, it is GC'd and all signal connections die silently. `ApplicationFactory.build()` assigns `view._controller = controller` to transfer ownership to the view.
- **`IApplicationView` extends `AppWidget`**: Required for shell integration. `AppWidget` provides `on_language_changed()` and the hooks `AppShell` uses to show/hide panels.
- **`WidgetApplication` is the universal adapter**: The bootstrap works with `IApplication` references. `WidgetApplication` decouples the typed factory from the bootstrap protocol, enabling lazy widget creation.
- **`build()` is the only entry point**: Subclasses implement `_create_model`, `_create_view`, `_create_controller` only. The wiring order and GC fix are handled by the base class exactly once.
- **Notifications stay out of backend layers**: Processes, coordinators, and services should publish typed notification events via the broker. Controllers render them through `UserNotificationPresenter`. This avoids Qt imports in engine or robot-system code and keeps the mechanism reusable across robot systems.
