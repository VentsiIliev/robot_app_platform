# `src/applications/glue_cell_settings/service/` — Glue Cell Settings Service

---

## `IGlueCellSettingsService`

**File:** `i_glue_cell_settings_service.py`

```python
class IGlueCellSettingsService(ABC):
    @abstractmethod
    def load_cells(self) -> CellsConfig: ...

    @abstractmethod
    def save_cells(self, cells: CellsConfig) -> None: ...

    @abstractmethod
    def tare(self, cell_id: int) -> bool: ...

    @abstractmethod
    def get_cell_ids(self) -> List[int]: ...

    @abstractmethod
    def push_calibration(self, cell_id: int, config: CellConfig) -> None: ...
```

`CellsConfig` and `CellConfig` are defined in `src/engine/hardware/weight/config.py`.

| Method | Description |
|--------|-------------|
| `load_cells()` | Load all cell configurations from persistence |
| `save_cells(cells)` | Persist the full `CellsConfig` to disk |
| `tare(cell_id)` | Send a tare command to the cell via `IWeightCellService`; returns success |
| `get_cell_ids()` | Return the list of configured cell IDs |
| `push_calibration(cell_id, config)` | Write updated calibration to the running `IWeightCellService` without restart |

---

## `GlueCellSettingsService`

**File:** `glue_cell_settings_service.py`

```python
class GlueCellSettingsService(IGlueCellSettingsService):
    def __init__(
        self,
        settings_service:     ISettingsService,
        weight_cell_service:  Optional[IWeightCellService] = None,
    ): ...
```

The only file in this application allowed to import `ISettingsService` or `IWeightCellService`. Uses settings key `"glue_cells"`.

- `load_cells()` → `settings_service.get("glue_cells")` → `CellsConfig`
- `save_cells(cells)` → `settings_service.save("glue_cells", cells)`
- `tare(cell_id)` → `weight_cell_service.tare(cell_id)` (returns `False` if service unavailable)
- `get_cell_ids()` → loads config, returns `config.get_all_cell_ids()`
- `push_calibration(cell_id, config)` → `weight_cell_service.update_calibration(cell_id, config)` (no-op if unavailable)

---

## `StubGlueCellSettingsService`

**File:** `stub_glue_cell_settings.py`

In-memory implementation backed by a default `CellsConfig`. `tare()` always returns `True`. `push_calibration()` is a no-op. Used by `example_usage.py` and unit tests.

---

## Design Notes

- **Optional `IWeightCellService`**: The weight cell service may not be available if hardware is disconnected or `required=False` in `ServiceSpec`. The service gracefully degrades — `tare` returns `False`, `push_calibration` is skipped.
- **`get_cell_ids()` is called at factory build time**: `GlueCellSettingsFactory` calls this before creating the view to determine how many tabs to build.
