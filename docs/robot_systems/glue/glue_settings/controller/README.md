# `src/robot_systems/glue/glue_settings/controller/` — Glue Settings Controller

---

## `GlueSettingsController`

**File:** `controller/glue_settings_controller.py`

```python
class GlueSettingsController(IApplicationController):
    def __init__(self, model: GlueSettingsModel, view: GlueSettingsView): ...
    def load(self) -> None: ...
    def stop(self) -> None: ...
```

Wires view signals to model calls. No broker subscriptions.

### Signal Wiring

| View signal | Controller slot | Action |
|-------------|----------------|--------|
| `save_requested(flat)` | `_on_save(flat)` | `model.save(flat)` |
| Glue type add signal | `_on_add_glue_type(name, desc)` | `model.add_glue_type(name, desc)`; refresh view |
| Glue type update signal | `_on_update_glue_type(id_, name, desc)` | `model.update_glue_type(...)`; refresh view |
| Glue type remove signal | `_on_remove_glue_type(id_)` | `model.remove_glue_type(id_)`; refresh view |
| `destroyed` | `stop()` | No-op |

### `load()` Sequence

```
load()
  → settings   = model.load()
  → glue_types = model.load_glue_types()
  → view.load_settings(settings)
  → view.load_glue_types(glue_types)
  → connect all signals
```

### `stop()`

No-op — no broker subscriptions, no background threads.

---

## Design Notes

- **Catalog operations refresh the view**: After each add/update/remove, the controller calls `model.load_glue_types()` and `view.load_glue_types()` to ensure the table shows the current state.
- **No broker subscriptions**: Glue settings are only changed by user action. There is no need to subscribe to external events.
