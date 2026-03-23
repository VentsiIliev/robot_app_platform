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
WidgetApplication(widget_factory=lambda ms: factory.build(service, messaging=ms))

# Application supports shared jog wiring:
WidgetApplication(widget_factory=lambda ms: factory.build(service, messaging=ms, jog_service=jog_service))
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

`build(service, messaging=None, jog_service=None)` calls the three abstract methods in order, then:
1. Optionally auto-attaches `JogController` when the view enables jog and both shared dependencies are provided
2. Calls `controller.load()` — populates the view from the model
3. Assigns `view._controller = controller` — GC ownership fix (never write this yourself)
4. Logs the build at DEBUG level
5. Returns the `view`

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
    SHOW_JOG_WIDGET = False
    JOG_FRAME_SELECTOR_ENABLED = False

    jog_requested = pyqtSignal(str, str, str, float)
    jog_started = pyqtSignal(str)
    jog_stopped = pyqtSignal(str)

    def enable_jog_widget(self, enabled: bool) -> None: ...
    def set_jog_position(self, pos: list) -> None: ...
    def get_jog_frame(self) -> str: ...

    @abstractmethod
    def setup_ui(self) -> None: ...

    @abstractmethod
    def clean_up(self) -> None: ...
```

Extends `AppWidget` from `pl_gui` and now owns the shared jog drawer lifecycle for all application views.

Behavior:
- every `IApplicationView` gets a `RobotJogWidget` and `DrawerToggle` installed automatically after `setup_ui()`
- the drawer is hidden by default
- views opt in by setting `SHOW_JOG_WIDGET = True`
- views that need frame selection opt in with `JOG_FRAME_SELECTOR_ENABLED = True`
- controllers can always call `view.set_jog_position(...)`
- `JogController` can always ask `view.get_jog_frame()`
- `ApplicationFactory.build(..., messaging=..., jog_service=...)` auto-attaches jog support when the view opts in

This removes the need for each application view to manually create `_drawer` and `_jog_widget`.
It also removes the need for application controllers to manually construct `JogController`.

Typical view configuration:

```python
class PickTargetView(IApplicationView):
    SHOW_JOG_WIDGET = True
    JOG_FRAME_SELECTOR_ENABLED = True
```

If a view needs custom jog setup, implement a private hook:

```python
def _configure_jog_widget(self) -> None:
    self._jog_widget.set_frame_options(
        ["camera", "tool", "gripper"],
        default="tool",
    )
```

If the view needs to react to frame changes, implement:

```python
def _on_jog_frame_changed(self, name: str) -> None:
    ...
```

`setup_ui()` is still called by `AppWidget.__init__` after the subclass has initialized its own state. `clean_up()` remains the place for stopping timers or threads when the widget is destroyed.

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
ApplicationFactory.build(service, messaging=..., jog_service=...)
      │
      ├─ _create_model(service) → model
      ├─ _create_view()         → view
      ├─ _create_controller(model, view) → controller
      │
      ├─ [optional] auto-create JogController when view enables jog
      ├─ controller.load()          ← populate view from model
      ├─ view._controller = controller  ← GC ownership fix
      └─ return view
```

---

## `RobotJogWidget`

**File:** `robot_jog_widget.py`

A reusable Qt widget that provides manual robot jogging controls with directional buttons, step-size selection, and frame/end-effector selection.

### Frame Selector

The widget has an optional `QComboBox` labeled **"Frame:"** in its bottom row. It is hidden by default and must be enabled explicitly by the host view.

```python
# Signals
frame_changed = pyqtSignal(str)   # emitted when operator selects a different frame

# Public API
def enable_frame_selector(self, enabled: bool) -> None:
    """Show or hide the optional frame selector."""

def set_frame_options(self, names: List[str], default: Optional[str] = None) -> None:
    """Populate the combo box with the given names; optionally set the active selection."""

def set_frame(self, name: str) -> None:
    """Programmatically select a frame without emitting frame_changed."""

def get_frame(self) -> str:
    """Return the currently selected frame name, or '' if not set."""
```

Typical usage:

```python
self._jog_widget = RobotJogWidget()
self._jog_widget.enable_frame_selector(True)
self._jog_widget.set_frame_options(["camera", "tool", "gripper"], default="tool")
```

`set_frame()` is intentionally signal-free so a parent widget can keep a button and the combo box in sync without triggering an infinite signal loop.

### Integration in `PickTarget`

`PickTargetView` enables the frame selector via the base view flags, populates the combo in `_configure_jog_widget()`, and reacts to selection changes in `_on_jog_frame_changed()`. The existing **Target:** button on the control panel does the same thing, so both selectors stay in sync via `_apply_target(sync_jog=True/False)`.

### Shared Jog Path

`JogController` now reads the active jog frame from the host view when the view exposes:

```python
def get_jog_frame(self) -> str: ...
```

and forwards that into `RobotJogService`.

In the shared application path, you normally do not create `JogController` yourself anymore. The base factory does it automatically when:
- the view sets `SHOW_JOG_WIDGET = True`
- the factory `build(...)` call receives both `messaging` and `jog_service`

In glue-system applications, the wiring can provide a target-aware jog service that converts a jog request into a corrected Cartesian pose move. That shared path lets jog moves respect:
- TCP-delta correction
- selected end-effector point (`camera`, `tool`, `gripper`)
- robot tool/user settings from glue configuration

Internally that shared jog path resolves the selected frame name through `PointRegistry` once and then works with the concrete registry point, matching the resolver API used by vision targeting.

Applications that do not enable the frame selector continue to behave like normal raw jog UIs.

---

## Design Notes

- **GC ownership**: PyQt6 weak-references Python bound methods as signal slots. If no strong ref holds the controller, it is GC'd and all signal connections die silently. `ApplicationFactory.build()` assigns `view._controller = controller` to transfer ownership to the view.
- **`IApplicationView` extends `AppWidget`**: Required for shell integration. `AppWidget` provides `on_language_changed()` and the hooks `AppShell` uses to show/hide panels.
- **`WidgetApplication` is the universal adapter**: The bootstrap works with `IApplication` references. `WidgetApplication` decouples the typed factory from the bootstrap protocol, enabling lazy widget creation.
- **`build()` is the only entry point**: Subclasses implement `_create_model`, `_create_view`, `_create_controller` only. The wiring order and GC fix are handled by the base class exactly once.
- **Notifications stay out of backend layers**: Processes, coordinators, and services should publish typed notification events via the broker. Controllers render them through `UserNotificationPresenter`. This avoids Qt imports in engine or robot-system code and keeps the mechanism reusable across robot systems.
