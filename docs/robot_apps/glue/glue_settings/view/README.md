# `src/robot_apps/glue/glue_settings/view/` — Glue Settings View

---

## `GlueSettingsView`

**File:** `glue_settings_view.py`

```python
class GlueSettingsView(IPluginView):
    save_requested = pyqtSignal(dict)
```

Pure Qt widget. Renders a `SettingsView` for glue dispenser parameters plus a `GlueTypeTab` for catalog management.

### Outbound Signals

| Signal | Emitted when |
|--------|-------------|
| `save_requested(dict)` | User clicks Save |

### Inbound Methods

| Method | Effect |
|--------|--------|
| `load_settings(settings: GlueSettings)` | Populates the settings form |
| `load_glue_types(glue_types: List[Glue])` | Populates the `GlueTypeTab` table |
| `get_values() → dict` | Returns current flat form values |

---

## `GlueTypeTab`

**File:** `view/glue_type_tab.py`

A `QWidget` embedded in the view that renders the glue type catalog as a table with Add/Edit/Remove buttons. Emits signals for each catalog operation; the controller connects them to the model.

---

## `glue_settings_schema.py`

Defines field groups for the `SettingsView` form. Field names correspond to `GlueSettingKey` enum values.
