# `src/applications/glue_cell_settings/model/` — Glue Cell Settings Model

---

## `GlueCellSettingsModel`

**File:** `glue_cell_settings_model.py`

```python
class GlueCellSettingsModel(IApplicationModel):
    def __init__(self, service: IGlueCellSettingsService): ...

    def load(self) -> CellsConfig: ...
    def save(self, cell_id: int, flat: dict) -> None: ...
    def tare(self, cell_id: int) -> bool: ...
    def get_cell_flat(self, cell_id: int) -> Optional[dict]: ...
    def get_cell_ids(self) -> List[int]: ...
```

Holds `_config: Optional[CellsConfig]` in memory after `load()`. Provides per-cell flat-dict access for the view. Contains zero Qt imports.

| Method | Behaviour |
|--------|-----------|
| `load()` | Calls `service.load_cells()`, caches in `_config`, returns it |
| `save(cell_id, flat)` | Maps flat dict → `CellConfig` via `GlueCellMapper`, updates `_config`, calls `service.save_cells()`, then calls `service.push_calibration(cell_id, config)` |
| `tare(cell_id)` | Delegates to `service.tare(cell_id)` → `bool` |
| `get_cell_flat(cell_id)` | Returns `GlueCellMapper.cell_to_flat(cell)` for the given cell ID, or `None` if not found |
| `get_cell_ids()` | Returns `service.get_cell_ids()` |

---

## `GlueCellMapper`

**File:** `mapper.py`

```python
class GlueCellMapper:
    @staticmethod
    def cell_to_flat(cell: CellConfig) -> dict: ...

    @staticmethod
    def flat_to_cell(flat: dict, original: CellConfig) -> CellConfig: ...
```

### `cell_to_flat` output keys

| Key | Source |
|-----|--------|
| `url` | `cell.url` |
| `type` | `cell.type` |
| `capacity` | `cell.capacity` |
| `fetch_timeout_seconds` | `cell.fetch_timeout_seconds` |
| `data_fetch_interval_ms` | `cell.data_fetch_interval_ms` |
| `motor_address` | `cell.motor_address` |
| `zero_offset` | `cell.calibration.zero_offset` |
| `scale_factor` | `cell.calibration.scale_factor` |
| `sampling_rate` | `cell.measurement.sampling_rate` |
| `filter_cutoff` | `cell.measurement.filter_cutoff` |
| `averaging_samples` | `cell.measurement.averaging_samples` |
| `min_weight_threshold` | `cell.measurement.min_weight_threshold` |
| `max_weight_threshold` | `cell.measurement.max_weight_threshold` |

### `flat_to_cell` type coercions

| Field | Coercion |
|-------|---------|
| `zero_offset`, `scale_factor`, `capacity`, `fetch_timeout_seconds`, `filter_cutoff`, `min/max_weight_threshold` | `float()` |
| `sampling_rate`, `averaging_samples`, `data_fetch_interval_ms`, `motor_address` | `int()` |
| `url`, `type` | `str()` |

Uses `dataclasses.replace()` for immutable `CellConfig` fields, preserving all unspecified values from `original`.

---

## Design Notes

- **`push_calibration` is called in `save()`**: After persisting the updated `CellsConfig`, the model immediately pushes the new calibration config to the running hardware service. This ensures the weight cell starts using the new calibration without requiring a restart.
- **`get_cell_flat` returns `None` on unknown ID**: The controller checks for `None` before calling `view.load_cell()`, making missing cells a no-op rather than an error.
