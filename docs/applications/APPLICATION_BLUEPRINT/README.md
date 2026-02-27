# `src/applications/APPLICATION_BLUEPRINT/` — Application Template

This directory is the canonical copy-paste template for creating new applications. It contains stub implementations of every layer with inline comments explaining what to fill in.

**The authoritative implementation guide is in `APPLICATION_GUIDE.MD` in this same directory — read it before creating a new application.**

---

## File Structure

```
APPLICATION_BLUEPRINT/
  APPLICATION_GUIDE.MD             ← 13-step implementation walkthrough (read this first)
  my_application.py                ← IApplication entry point — thin shell
  my_application_factory.py        ← ApplicationFactory subclass — 3 factory methods
  example_usage.py            ← standalone runner with StubMyService
  service/
    i_my_service.py           ← ABC: application's only contract with the platform
    my_application_service.py      ← adapter: wraps ISettingsService / IRobotService
    stub_my_service.py        ← hardcoded impl for dev and unit tests
  model/
    my_model.py               ← IApplicationModel: load/save, delegates to service
  view/
    my_view.py                ← IApplicationView: signals out, setters in, zero logic
  controller/
    my_controller.py          ← IApplicationController: wires M ↔ V, broker subscriptions
```

---

## Class Summary

| Class | Interface | Role |
|-------|-----------|------|
| `MyPlugin` | `IApplication` | Bootstrap entry point; creates service + factory |
| `MyApplicationFactory` | `ApplicationFactory` | Implements 3 factory methods; wiring is automatic |
| `IMyService` | ABC | Application-platform boundary: `get_value()` / `save_value(value)` |
| `MyApplicationService` | `IMyService` | Wraps `ISettingsService`; only file importing platform services |
| `StubMyService` | `IMyService` | Returns `"stub_value"`, prints to stdout |
| `MyModel` | `IApplicationModel` | Holds `_value: Optional[str]`; delegates I/O to `IMyService` |
| `MyView` | `IApplicationView` | `save_requested: pyqtSignal(str)`; `set_value(value)` setter |
| `MyController` | `IApplicationController` | Connects `save_requested → _on_save`; `destroyed → stop` |

---

## Creating a New Application

1. Copy `APPLICATION_BLUEPRINT/` → `src/applications/my_application/`
2. Replace every occurrence of `My` / `my` / `APPLICATION_BLUEPRINT`
3. Implement the service interface, stub, adapter, model, view, controller, and factory
4. Add `ApplicationSpec` + factory function to your robot system
5. Verify standalone runner: `python src/applications/my_application/example_usage.py`

→ Follow `APPLICATION_GUIDE.MD` for the complete 13-step walkthrough.

---

## Standalone Runner

```python
# example_usage.py
def run_standalone() -> None:
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from src.applications.APPLICATION_BLUEPRINT.my_application_factory import MyApplicationFactory
    from src.applications.APPLICATION_BLUEPRINT.service.stub_my_service import StubMyService

    app = QApplication(sys.argv)
    widget = MyApplicationFactory().build(StubMyService())

    window = QMainWindow()
    window.setCentralWidget(widget)
    window.resize(1280, 900)
    window.show()
    sys.exit(app.exec())
```

---

## Layer Import Rules

| Layer | May import | Must NOT import |
|-------|-----------|-----------------|
| `IApplication` / `WidgetApplication` | `IMyService`, factory | `ISettingsService`, `IRobotService` directly |
| `IMyService` | stdlib only | anything platform |
| `MyApplicationService` | platform services | Qt, model, view, controller |
| `MyModel` | `IMyService`, stdlib | Qt, view, controller |
| `MyView` | Qt, `pl_gui` | model, service, controller |
| `MyController` | model, view, `IMessagingService` | services, `ISettingsService` |
| `MyApplicationFactory` | model, view, controller, service | broker directly |
