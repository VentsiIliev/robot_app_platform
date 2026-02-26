# `src/robot_apps/glue/dashboard/service/` — Glue Dashboard Service

---

## `IGlueDashboardService`

**File:** `i_glue_dashboard_service.py`

```python
class IGlueDashboardService(ABC):
    # Commands
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def pause(self) -> None: ...
    def clean(self) -> None: ...
    def reset_errors(self) -> None: ...
    def set_mode(self, mode: str) -> None: ...
    def change_glue(self, cell_id: int, glue_type: str) -> None: ...

    # Queries
    def get_cell_capacity(self, cell_id: int) -> float: ...
    def get_cell_glue_type(self, cell_id: int) -> Optional[str]: ...
    def get_all_glue_types(self) -> List[str]: ...
    def get_initial_cell_state(self, cell_id: int) -> Optional[Dict]: ...
    def get_cells_count(self) -> int: ...
```

---

## `GlueDashboardService`

**File:** `glue_dashboard_service.py`

```python
class GlueDashboardService(IGlueDashboardService):
    def __init__(
        self,
        robot_service:    IRobotService,
        settings_service: ISettingsService,
        weight_service:   Optional[IWeightCellService] = None,
    ): ...
```

The only file in the dashboard that imports platform services. Dependencies:

| Dependency | Used for |
|-----------|---------|
| `IRobotService` | `start` → `enable_robot()`, `stop` → `stop_motion() + disable_robot()`, `pause` → `stop_motion()` |
| `ISettingsService` | `change_glue` → reads/writes `"glue_cells"`; `get_cell_capacity/glue_type` → reads `"glue_cells"`; `get_all_glue_types` → reads `"glue_catalog"` |
| `IWeightCellService` (optional) | `get_cell_connection_state` → `weight.get_cell_state(cell_id).value`; returns `"disconnected"` if `None` |

### Method Implementations

| Method | Implementation |
|--------|---------------|
| `start()` | `robot_service.enable_robot()` |
| `stop()` | `robot_service.stop_motion()` + `robot_service.disable_robot()` |
| `pause()` | `robot_service.stop_motion()` |
| `clean()` | Logs only (hardware command to be wired) |
| `reset_errors()` | Logs only |
| `set_mode(mode)` | Logs only |
| `change_glue(cell_id, glue_type)` | Loads `GlueCellsConfig`, replaces `cell.type`, saves back |
| `get_cell_capacity(cell_id)` | Reads `"glue_cells"` → `cell.capacity` |
| `get_cell_glue_type(cell_id)` | Reads `"glue_cells"` → `cell.type` |
| `get_all_glue_types()` | Reads `"glue_catalog"` → `catalog.get_all_names()` |
| `get_cells_count()` | Reads `"glue_cells"` → `cells_config.cell_count` |
| `get_cell_connection_state(cell_id)` | `weight_service.get_cell_state(cell_id).value` or `"disconnected"` |

---

## `StubGlueDashboardService`

**File:** `stub_glue_dashboard_service.py`

Returns hardcoded values for all queries. Commands are no-ops that log. Used by `example_usage.py` for standalone development.

---

## Design Notes

- **`get_initial_cell_state` returns `None`**: The initial state is determined at startup by reading from `IWeightCellService` via `get_cell_connection_state()`. The `get_initial_cell_state()` method is kept in the interface for future use (e.g., returning a cached state snapshot from before startup).
- **`clean` and `reset_errors` log only**: Hardware command wiring (e.g., Modbus output, robot I/O) is not yet implemented. The method stubs exist so the controller can call them and the broker can publish the command events.
