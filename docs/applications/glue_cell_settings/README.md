# `src/applications/glue_cell_settings/` — Glue Cell Settings Application

The `glue_cell_settings` application provides a per-cell tabbed GUI for configuring weight cell hardware (connection URL, calibration, measurement parameters) and monitoring live weight readings and connection state. It differs from the standard application pattern in two ways: it uses `WidgetApplication` directly instead of wrapping `IApplication`, and its controller bridges background-thread broker callbacks to the Qt main thread using `_Bridge(QObject)`.

This application is now a low-level editor for direct cell configuration. The glue shell uses `DispenseChannelSettings` as the primary operator-facing setup screen for channel-level glue dispensing.

---

## Architecture

```
GlueCellSettingsApplication(WidgetApplication)
  └─ GlueCellSettingsFactory.build(service, messaging_service)
       ├─ GlueCellSettingsModel          ← load/save/tare, per-cell flat dicts
       ├─ GlueCellSettingsView           ← QTabWidget; one CellSettingsTab per cell
       └─ GlueCellSettingsController     ← _Bridge for cross-thread weight delivery
```

One service interface:

```
IGlueCellSettingsService   ← load_cells / save_cells / tare / get_cell_ids / push_calibration
```

---

## Class Summary

| Class | Role |
|-------|------|
| `GlueCellSettingsApplication(WidgetApplication)` | Wraps factory lambda; passes `ms` through to factory |
| `GlueCellSettingsFactory` | Custom `build(service, messaging_service)` — queries cell IDs at build time |
| `IGlueCellSettingsService` | ABC: 5 methods; persistence + tare + calibration push |
| `GlueCellSettingsService` | Wraps `ISettingsService` + optional `IWeightCellService`; key `"glue_cells"` |
| `StubGlueCellSettingsService` | In-memory stub for standalone use |
| `GlueCellSettingsModel` | Per-cell load/save/tare; calls `push_calibration` after every save |
| `GlueCellMapper` | `cell_to_flat / flat_to_cell` — maps `CellConfig` ↔ flat dict |
| `GlueCellSettingsView` | `QTabWidget`; `save_requested(int, dict)` + `tare_requested(int)` |
| `CellSettingsTab` | Per-cell widget: live monitor bar + 3-tab `SettingsView` |
| `CellMonitorWidget` | Status indicator + weight label; thread-safe via `_MonitorBridge` |
| `GlueCellSettingsController` | Subscribes to weight/state topics; uses `_Bridge` for thread safety |

---

## Data Flow

### Load

```
controller.load()
  → model.load() → CellsConfig
  → for each cell_id:
       flat = model.get_cell_flat(cell_id)
       view.load_cell(cell_id, flat)
       view.set_cell_state(cell_id, "disconnected")
  → _subscribe()   ← broker subscriptions for live data
```

### Save cell settings

```
User edits a field and clicks Save (CellSettingsTab)
  → CellSettingsTab.save_requested.emit(flat_dict)
  → GlueCellSettingsView.save_requested.emit(cell_id, flat_dict)
  → GlueCellSettingsController._on_save(cell_id, flat)
  → GlueCellSettingsModel.save(cell_id, flat)
       └─ GlueCellMapper.flat_to_cell(flat, original) → CellConfig
       └─ ISettingsService.save("glue_cells", cells_config)
       └─ push_calibration(cell_id, config)   ← write to hardware
```

### Live weight/state (background thread → GUI)

```
WeightCellService publishes WeightReading on weight/cell/{id}/reading
  → lambda in controller captures and emits to _bridge.weight_updated
  → _Bridge.weight_updated (pyqtSignal) → GlueCellSettingsController._view.set_cell_weight
       (Qt signal → safely dispatched to main thread)

WeightCellService publishes CellStateEvent on weight/cell/{id}/state
  → _bridge.state_updated.emit(cell_id, state_str)
  → GlueCellSettingsController._view.set_cell_state
```

---

## Broker Topics Consumed

| Topic | Payload | Handler |
|-------|---------|---------|
| `weight/cell/{id}/reading` | `WeightReading` | `_bridge.weight_updated.emit(cell_id, reading.value)` |
| `weight/cell/{id}/state` | `CellStateEvent` | `_bridge.state_updated.emit(cell_id, event.state.value)` |

---

## Usage Example

```python
from src.applications.glue_cell_settings.glue_cell_settings_factory import GlueCellSettingsFactory
from src.applications.glue_cell_settings.service.stub_glue_cell_settings import StubGlueCellSettingsService

widget = GlueCellSettingsFactory().build(
    service=StubGlueCellSettingsService(),
    messaging_service=messaging,
)
```

---

## Design Notes

- **`WidgetApplication` directly (no `IApplication` subclass)**: `GlueCellSettingsApplication` passes a `lambda ms: factory.build(service, ms)` as `widget_factory`. The bootstrap calls it with `messaging_service` in `create_widget()`.
- **`_Bridge(QObject)` for cross-thread safety**: Broker callbacks for weight and state arrive on background threads. Calling Qt setters directly from a background thread is unsafe. `GlueCellSettingsController` creates a `_Bridge` QObject with `pyqtSignal(int, float)` and `pyqtSignal(int, str)`. Lambda subscriptions emit to the bridge; bridge signals are connected to view setters via normal Qt signal routing (auto-connection queues across threads).
- **`push_calibration` on every save**: After writing to disk, `GlueCellSettingsService` immediately calls `IWeightCellService.push_calibration(cell_id, config)` to apply the new calibration to the running hardware service without requiring a restart.
- **`GlueCellSettingsFactory` queries cell IDs at build time**: `factory.build()` calls `service.get_cell_ids()` to know how many `CellSettingsTab` instances to create. This means the factory produces a view tailored to the actual cell count from settings.
- **No temperature-compensation field**: The weight calibration model no longer includes `temperature_compensation`, so the legacy cell editor no longer exposes it.

→ Subpackages: [service/](service/README.md) · [model/](model/README.md) · [view/](view/README.md) · [controller/](controller/README.md)
