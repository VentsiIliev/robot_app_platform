# `src/robot_systems/glue/glue_settings/` — Glue Settings Application

The `glue_settings` application provides a GUI for editing glue dispenser parameters (`GlueSettings`) and managing the glue type catalog (`GlueCatalog`). It lives in `robot_apps/glue/` rather than `src/applications/` because it depends on glue-specific domain types (`GlueSettings`, `Glue`).

---

## Architecture

```
GlueSettingsFactory(ApplicationFactory).build(service)
  ├─ GlueSettingsModel    ← load/save GlueSettings + CRUD on GlueCatalog
  ├─ GlueSettingsView     ← SettingsView + GlueTypeTab
  └─ GlueSettingsController ← save_requested → model.save(flat)
```

---

## Class Summary

| Class | Role |
|-------|------|
| `GlueSettingsFactory(ApplicationFactory)` | Standard 3-method override |
| `IGlueSettingsService` | ABC: `load_settings/save_settings` + CRUD on glue types |
| `GlueSettingsApplicationService` | Wraps `ISettingsService`; keys `"glue_settings"` + `"glue_catalog"` |
| `StubGlueSettingsService` | In-memory defaults |
| `GlueSettingsModel(IApplicationModel)` | `load/save` + `load/add/update/remove` glue types |
| `GlueSettingsMapper` | `to_flat_dict / from_flat_dict` for `GlueSettings` |
| `GlueSettingsView(IApplicationView)` | `save_requested` signal; `SettingsView` + `GlueTypeTab` |
| `GlueSettingsController(IApplicationController)` | `save_requested → model.save(flat)` |

---

## `IGlueSettingsService`

```python
class IGlueSettingsService(ABC):
    def load_settings(self) -> GlueSettings: ...
    def save_settings(self, settings: GlueSettings) -> None: ...
    def load_glue_types(self) -> List[Glue]: ...
    def add_glue_type(self, name: str, description: str) -> Glue: ...
    def update_glue_type(self, id_: str, name: str, description: str) -> Glue: ...
    def remove_glue_type(self, id_: str) -> None: ...
```

Settings persistence (`"glue_settings"`) and catalog CRUD (`"glue_catalog"`) are combined in one interface because the view presents them in one tabbed widget.

---

## Data Flow

### Load

```
controller.load()
  → settings = model.load()          ← returns GlueSettings from service
  → glue_types = model.load_glue_types()
  → view.load_settings(settings)
  → view.load_glue_types(glue_types)
```

### Save settings

```
User edits a field → clicks Save
  → GlueSettingsView.save_requested.emit(flat_dict)
  → GlueSettingsController._on_save(flat)
  → model.save(flat)
       └─ GlueSettingsMapper.from_flat_dict(flat, base) → GlueSettings
       └─ service.save_settings(updated)
```

### Glue type CRUD

The `GlueTypeTab` in the view emits separate signals for add/edit/remove. The controller connects them to `model.add_glue_type`, `model.update_glue_type`, and `model.remove_glue_type`.

---

## Design Notes

- **App-specific application**: This application is in `robot_apps/glue/` instead of `src/applications/` because it imports `GlueSettings` and `Glue` — domain types that belong to the glue app, not the generic platform. Generic applications must not depend on app-specific types.
- **No broker subscriptions**: `GlueSettingsController.stop()` is a no-op.

→ Subpackages: [service/](service/README.md) · [model/](model/README.md) · [view/](view/README.md) · [controller/](controller/README.md)
