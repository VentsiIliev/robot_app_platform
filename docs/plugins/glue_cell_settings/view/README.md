# `src/plugins/glue_cell_settings/view/` — Glue Cell Settings View

---

## `GlueCellSettingsView`

**File:** `glue_cell_settings_view.py`

```python
class GlueCellSettingsView(IPluginView):
    save_requested = pyqtSignal(int, dict)   # (cell_id, flat_values)
    tare_requested = pyqtSignal(int)         # (cell_id)

    def __init__(self, cell_ids: List[int], parent=None): ...
```

Root view. Builds a `QTabWidget` with one `CellSettingsTab` per cell ID. Each tab's signals are forwarded through named lambdas at construction time.

### Outbound Signals

| Signal | Emitted when |
|--------|-------------|
| `save_requested(int, dict)` | User clicks Save in a cell tab |
| `tare_requested(int)` | User clicks Tare in a cell tab |

### Inbound Setters

| Method | Effect |
|--------|--------|
| `load_cell(cell_id, flat)` | Populates the tab for `cell_id` with the given flat values |
| `set_cell_weight(cell_id, value)` | Updates the live weight display on `CellMonitorWidget` for that cell |
| `set_cell_state(cell_id, state)` | Updates the state indicator on `CellMonitorWidget` for that cell |

---

## `CellSettingsTab`

**File:** `cell_settings_tab.py`

Per-cell widget containing a live monitor bar and a three-tab settings form.

```python
class CellSettingsTab(QWidget):
    save_requested = pyqtSignal(dict)    # flat values from the settings form
    tare_requested = pyqtSignal()
```

Layout:
```
┌─────────────────────────────────────────────┐
│  Cell N  │ ● connected  25.43 g │  ⊘ Tare  │  ← CellMonitorWidget
├─────────────────────────────────────────────┤
│  Connection │ Calibration │ Measurement      │  ← SettingsView (3 tabs)
│  [form fields per tab]                       │
└─────────────────────────────────────────────┘
```

The three tabs are built from schema groups defined in `glue_cell_schema.py`:
- **Connection** — `CONNECTION_GROUP`: URL, type, capacity, timeouts, motor address
- **Calibration** — `CALIBRATION_GROUP`: zero offset, scale factor, temperature compensation
- **Measurement** — `MEASUREMENT_GROUP`: sampling rate, filter cutoff, averaging, weight thresholds

---

## `CellMonitorWidget`

**File:** `cell_monitor_widget.py`

```python
class CellMonitorWidget(QWidget):
    def set_weight(self, value: float) -> None: ...
    def set_state(self, state: str) -> None: ...
```

Shows a colored status indicator and a live weight label. Internally uses `_MonitorBridge(QObject)` with `pyqtSignal(float)` and `pyqtSignal(str)` to safely accept calls from any thread. Public `set_weight` and `set_state` emit to the bridge; the bridge signals are connected to the actual Qt label updates on the main thread.

### State Indicator Colors

| State | Color |
|-------|-------|
| `"connected"` | `#28a745` (green) |
| `"connecting"` | `#f39c12` (orange) |
| `"disconnected"` | `#6c757d` (grey) |
| `"error"` | `#d9534f` (red) |
| other | `#808080` |

---

## Design Notes

- **`_MonitorBridge` in `CellMonitorWidget`**: Weight and state updates arrive from background threads via the broker. `CellMonitorWidget` has its own bridge so that both `set_weight` and `set_state` are safe to call from any thread — they emit through PyQt6 signals which queue to the main thread automatically.
- **`GlueCellSettingsController` also has a `_Bridge`**: The controller-level `_Bridge(QObject)` with `weight_updated(int, float)` and `state_updated(int, str)` signals routes broker callbacks to the view's per-cell setters. The view then routes to `CellMonitorWidget` which has its own bridge for fine-grained thread safety.
- **`glue_cell_schema.py`**: Not a runtime registry — it is imported at construction time by `CellSettingsTab` to define form field groups.
