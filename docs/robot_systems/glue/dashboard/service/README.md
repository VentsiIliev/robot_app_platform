# `src/robot_systems/glue/dashboard/service/` — Glue Dashboard Service

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
        runner:           GlueOperationCoordinator,
        settings_service: ISettingsService,
        weight_service:   Optional[IWeightCellService] = None,
        execution_service: Optional[GlueJobExecutionService] = None,
        messaging_service: Optional[IMessagingService] = None,
    ): ...
```

The only file in the dashboard that imports platform services. Dependencies:

| Dependency | Used for |
|-----------|---------|
| `GlueOperationCoordinator` | normal production lifecycle: start / stop / pause / resume / clean / reset |
| `ISettingsService` | `change_glue` → reads/writes `"glue_cells"`; `get_cell_capacity/glue_type` → reads `"glue_cells"`; `get_all_glue_types` → reads `"glue_catalog"` |
| `IWeightCellService` (optional) | `get_cell_connection_state` → `weight.get_cell_state(cell_id).value`; returns `"disconnected"` if `None` |
| `GlueJobExecutionService` (optional) | shared glue preparation flow: move to capture pose + wait + capture + match + build + load |
| `IMessagingService` (optional) | publishes a warning message when automated glue-only start fails |

### Method Implementations

| Method | Implementation |
|--------|---------------|
| `start()` | delegates to `runner.start()` |
| `stop()` | `runner.stop()` |
| `pause()` | `runner.pause()` |
| `resume()` | `runner.resume()` |
| `clean()` | `runner.clean()` |
| `reset_errors()` | `runner.reset_errors()` |
| `set_mode(mode)` | parses label to `GlueOperationMode` and calls `runner.set_mode(...)` |
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
- **Coordinator-owned startup**: The dashboard service always delegates `start()` to `GlueOperationCoordinator`. In `SPRAY_ONLY`, the coordinator performs glue preparation before starting the glue sequence. In `PICK_AND_SPRAY`, preparation happens later in the sequence transition hook.
- **Paused run vs fresh restart**: In `SPRAY_ONLY`, the coordinator skips preparation only when the active glue run is actually `paused`. If the previous glue run is already `stopped`, `start()` is treated as a fresh run and preparation executes again before glue motion starts.
- **Settings-driven spray enable**: For automated glue preparation, the coordinator reads `GlueSettings.spray_on` via `ISettingsService.get(SettingsID.GLUE_SETTINGS)` and passes that configured value into `GlueJobExecutionService.prepare_and_load(...)`.
- **Mandatory positioning stage**: The execution service always starts by moving the robot to the calibration capture pose with the current vision capture offset, then waiting briefly for stabilization. If that step fails, the result stage is `positioning` and the glue flow does not proceed to matching.
- **Pick-and-spray handoff stays in the coordinator**: In `PICK_AND_SPRAY`, the dashboard still delegates to `GlueOperationCoordinator.start()`. Glue preparation happens later inside the sequence transition hook, after pick-and-place stops.
- **Cancellable pre-start preparation**: If `stop()` or `pause()` is called while glue preparation is still running, the coordinator cancels the pending preparation and requests robot stop before glue starts.
- **Interruptible capture wait**: The navigation move used for capture positioning now passes a wait-cancel callback down into the robot motion wait path, so cancellation interrupts the wait immediately instead of waiting for the navigation timeout.
- **Failure feedback**: On glue-only preparation failure, the service publishes `ProcessTopics.busy(ProcessID.COORDINATOR)` with a human-readable failure message so the dashboard status widget shows the reason immediately.
