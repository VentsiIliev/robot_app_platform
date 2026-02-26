# `src/plugins/PLUGIN_BLUEPRINT/` — Plugin Template

This directory is the canonical copy-paste template for creating new plugins. It contains stub implementations of every layer with inline comments explaining what to fill in.

**The authoritative implementation guide is in `PLUGIN_GUIDE.MD` in this same directory — read it before creating a new plugin.**

---

## File Structure

```
PLUGIN_BLUEPRINT/
  PLUGIN_GUIDE.MD             ← 13-step implementation walkthrough (read this first)
  my_plugin.py                ← IPlugin entry point — thin shell
  my_plugin_factory.py        ← PluginFactory subclass — 3 factory methods
  example_usage.py            ← standalone runner with StubMyService
  service/
    i_my_service.py           ← ABC: plugin's only contract with the platform
    my_plugin_service.py      ← adapter: wraps ISettingsService / IRobotService
    stub_my_service.py        ← hardcoded impl for dev and unit tests
  model/
    my_model.py               ← IPluginModel: load/save, delegates to service
  view/
    my_view.py                ← IPluginView: signals out, setters in, zero logic
  controller/
    my_controller.py          ← IPluginController: wires M ↔ V, broker subscriptions
```

---

## Class Summary

| Class | Interface | Role |
|-------|-----------|------|
| `MyPlugin` | `IPlugin` | Bootstrap entry point; creates service + factory |
| `MyPluginFactory` | `PluginFactory` | Implements 3 factory methods; wiring is automatic |
| `IMyService` | ABC | Plugin-platform boundary: `get_value()` / `save_value(value)` |
| `MyPluginService` | `IMyService` | Wraps `ISettingsService`; only file importing platform services |
| `StubMyService` | `IMyService` | Returns `"stub_value"`, prints to stdout |
| `MyModel` | `IPluginModel` | Holds `_value: Optional[str]`; delegates I/O to `IMyService` |
| `MyView` | `IPluginView` | `save_requested: pyqtSignal(str)`; `set_value(value)` setter |
| `MyController` | `IPluginController` | Connects `save_requested → _on_save`; `destroyed → stop` |

---

## Creating a New Plugin

1. Copy `PLUGIN_BLUEPRINT/` → `src/plugins/my_plugin/`
2. Replace every occurrence of `My` / `my` / `PLUGIN_BLUEPRINT`
3. Implement the service interface, stub, adapter, model, view, controller, and factory
4. Add `PluginSpec` + factory function to your robot app
5. Verify standalone runner: `python src/plugins/my_plugin/example_usage.py`

→ Follow `PLUGIN_GUIDE.MD` for the complete 13-step walkthrough.

---

## Standalone Runner

```python
# example_usage.py
def run_standalone() -> None:
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from src.plugins.PLUGIN_BLUEPRINT.my_plugin_factory import MyPluginFactory
    from src.plugins.PLUGIN_BLUEPRINT.service.stub_my_service import StubMyService

    app    = QApplication(sys.argv)
    widget = MyPluginFactory().build(StubMyService())

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
| `IPlugin` / `WidgetPlugin` | `IMyService`, factory | `ISettingsService`, `IRobotService` directly |
| `IMyService` | stdlib only | anything platform |
| `MyPluginService` | platform services | Qt, model, view, controller |
| `MyModel` | `IMyService`, stdlib | Qt, view, controller |
| `MyView` | Qt, `pl_gui` | model, service, controller |
| `MyController` | model, view, `IMessagingService` | services, `ISettingsService` |
| `MyPluginFactory` | model, view, controller, service | broker directly |
