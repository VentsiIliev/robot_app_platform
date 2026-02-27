# `src/robot_systems/glue/dashboard/model/` — Glue Dashboard Model

---

## `GlueDashboardModel`

**File:** `glue_dashboard_model.py`

```python
class GlueDashboardModel(IApplicationModel):
    def __init__(self, service: IGlueDashboardService, config: GlueDashboardConfig = None): ...

    # IApplicationModel
    def load(self) -> GlueDashboardConfig: ...   # returns config, no I/O
    def save(self, *args, **kwargs) -> None: ... # no-op — dashboard state is not persisted

    # Delegation to service
    def get_cell_capacity(self, cell_id: int) -> float: ...
    def get_cell_glue_type(self, cell_id: int) -> Optional[str]: ...
    def get_all_glue_types(self) -> List[str]: ...
    def get_initial_cell_state(self, cell_id: int) -> Optional[Dict]: ...
    def get_cells_count(self) -> int: ...
    def get_cell_connection_state(self, cell_id: int) -> str: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def pause(self) -> None: ...
    def clean(self) -> None: ...
    def reset_errors(self) -> None: ...
    def set_mode(self, mode: str) -> None: ...
    def change_glue(self, cell_id: int, glue_type: str) -> None: ...
```

This model is a thin pass-through facade over `IGlueDashboardService`. It holds `GlueDashboardConfig` (the layout/capacity configuration) but no mutable runtime state. Every method directly delegates to the service.

`load()` returns the `GlueDashboardConfig` object — the controller uses it to read static configuration (like `default_cell_capacity_grams`) but does not call `load()` to refresh cell data. Cell data arrives via broker subscriptions.

`save()` is a no-op because dashboard state (current weight, glue type, robot state) is transient and not persisted to disk.

---

## `protocols.py`

**File:** `model/protocols.py`

Defines `Protocol` types for structural type-checking of card and view objects used internally by the dashboard. Not part of the public API.

---

## Design Notes

- **No in-memory state**: Unlike `GlueSettingsModel` or `ModbusSettingsModel`, this model caches nothing. All queries hit the service synchronously. This is acceptable because dashboard queries (`get_cell_capacity`, `get_cell_glue_type`) read from the already-cached `ISettingsService` — no disk I/O.
- **`IApplicationModel` for interface uniformity**: The dashboard uses `IApplicationModel` as its base even though it doesn't persist anything. This ensures the controller can call `model.load()` in the standard lifecycle pattern.
