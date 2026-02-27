# `src/robot_systems/glue/glue_settings/service/` — Glue Settings Service

---

## `IGlueSettingsService`

**File:** `service/i_glue_settings_service.py`

```python
class IGlueSettingsService(ABC):
    def load_settings(self) -> GlueSettings: ...
    def save_settings(self, settings: GlueSettings) -> None: ...
    def load_glue_types(self) -> List[Glue]: ...
    def add_glue_type(self, name: str, description: str) -> Glue: ...
    def update_glue_type(self, id_: str, name: str, description: str) -> Glue: ...
    def remove_glue_type(self, id_: str) -> None: ...
```

---

## `GlueSettingsApplicationService`

**File:** `service/glue_settings_application_service.py`

```python
class GlueSettingsApplicationService(IGlueSettingsService):
    def __init__(self, settings_service: ISettingsService): ...
```

| Method | Settings key | Action |
|--------|-------------|--------|
| `load_settings()` | `"glue_settings"` | `settings_service.get("glue_settings")` |
| `save_settings(settings)` | `"glue_settings"` | `settings_service.save("glue_settings", settings)` |
| `load_glue_types()` | `"glue_catalog"` | `settings_service.get("glue_catalog").glue_types` |
| `add_glue_type(name, description)` | `"glue_catalog"` | Load catalog → `catalog.add(Glue(name, description))` → save → return new `Glue` |
| `update_glue_type(id_, name, description)` | `"glue_catalog"` | Load → find by id → update fields → save |
| `remove_glue_type(id_)` | `"glue_catalog"` | Load → `catalog.remove_by_id(id_)` → save |

---

## `StubGlueSettingsService`

**File:** `service/stub_glue_settings_service.py`

In-memory implementation. `load_settings()` returns `GlueSettings()` defaults. `load_glue_types()` returns a fixed list. CRUD methods mutate an in-memory `GlueCatalog`.

---

## Design Notes

- **`add_glue_type` raises `ValueError`** if a glue type with the same name already exists (enforced by `GlueCatalog.add()`).
- **CRUD operations read–modify–write**: Each catalog mutation loads the full catalog, applies the change, and saves it back. No long-lived catalog object is held in the service.
