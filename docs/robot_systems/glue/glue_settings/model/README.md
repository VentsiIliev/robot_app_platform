# `src/robot_systems/glue/glue_settings/model/` — Glue Settings Model

---

## `GlueSettingsModel`

**File:** `glue_settings_model.py`

```python
class GlueSettingsModel(IApplicationModel):
    def __init__(self, service: IGlueSettingsService): ...

    def load(self) -> GlueSettings: ...
    def save(self, flat: dict, **kwargs) -> None: ...

    def load_glue_types(self) -> List[Glue]: ...
    def add_glue_type(self, name: str, description: str) -> Glue: ...
    def update_glue_type(self, id_: str, name: str, description: str) -> Glue: ...
    def remove_glue_type(self, id_: str) -> None: ...
```

Holds `_settings: Optional[GlueSettings]` in memory after `load()`. All glue type operations delegate directly to the service (no caching of `GlueCatalog`).

| Method | Behaviour |
|--------|-----------|
| `load()` | `service.load_settings()`, caches in `_settings`, returns it |
| `save(flat)` | `GlueSettingsMapper.from_flat_dict(flat, _settings)` → `service.save_settings(updated)` → updates cache |

---

## `GlueSettingsMapper`

**File:** `model/mapper.py`

```python
class GlueSettingsMapper:
    @staticmethod
    def to_flat_dict(settings: GlueSettings) -> dict: ...

    @staticmethod
    def from_flat_dict(flat: dict, base: GlueSettings) -> GlueSettings: ...
```

Maps all 19 `GlueSettings` fields to/from flat dicts. Type coercions applied in `from_flat_dict`:

| Field group | Coercion |
|-------------|---------|
| `spray_width`, `spraying_height`, `fan_speed`, `motor_speed`, `speed_reverse`, `initial_ramp_speed`, `forward_ramp_steps`, `reverse_ramp_steps` | `int()` |
| `time_between_generator_and_glue`, `reverse_duration`, `rz_angle`, `generator_timeout`, `time_before_motion`, `time_before_stop`, `reach_start_threshold`, `reach_end_threshold`, `initial_ramp_speed_duration` | `float()` |
| `spray_on` | `str(...) == "True"` → `bool` |
| `glue_type` | `str()` |
