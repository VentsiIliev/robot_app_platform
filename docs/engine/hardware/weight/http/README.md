# `src/engine/hardware/weight/http/` — HTTP Weight Cell Transport

This package provides the HTTP-based implementation of `ICellTransport` and `ICellCalibrator`, and the factory function that wires them into `WeightCellService`. Weight cells expose a simple REST API; this package handles all HTTP communication.

---

## Class Diagram

```
ICellTransport (ABC)          ICellCalibrator (ABC)
       │                               │
       └──────────┬────────────────────┘
                  │ implements both
          HttpCellTransport
          ─────────────────
          _config: CellConfig
          _base_url: str
          _timeout: float
          _connected: bool
```

---

## API Reference

### `HttpCellTransport`

**File:** `http_cell_transport.py`

Implements both `ICellTransport` and `ICellCalibrator` for cells that expose an HTTP REST API.

```python
class HttpCellTransport(ICellTransport, ICellCalibrator):
    def __init__(self, config: CellConfig): ...
```

**`ICellTransport` methods:**

| Method | HTTP Call | Description |
|--------|-----------|-------------|
| `connect()` | `GET {base_url}` | Probe the base URL; sets `_connected = True` on `2xx` |
| `disconnect()` | (none) | Sets `_connected = False` |
| `is_connected` | (none) | Returns `self._connected` |
| `read_weight()` | `GET {base_url}` | Returns a `float`; handles `int`, `float`, and `{"weight": …}` / `{"value": …}` JSON formats |

**`ICellCalibrator` methods:**

| Method | HTTP Call | Returns |
|--------|-----------|---------|
| `tare(cell_id)` | `GET {base_url}/tare` | `True` if request succeeds |
| `get_config(cell_id)` | (none) | Returns `CellConfig.calibration` from local settings |
| `update_offset(cell_id, offset)` | `GET {base_url}/update-config?offset={offset}` | `True` if request succeeds |
| `update_scale(cell_id, scale)` | `GET {base_url}/update-config?scale={scale}` | `True` if request succeeds |
| `update_config(cell_id, offset, scale)` | `GET {base_url}/update-config?offset={offset}&scale={scale}` | `True` if request succeeds |

**`read_weight()` response format handling:**

The method accepts three response formats from the remote server:
- Raw number: `42.5`
- Dict with `weight` key: `{"weight": 42.5, ...}`
- Dict with `value` key: `{"value": 42.5, ...}`

Raises `ValueError` for unrecognized formats.

---

### `build_http_weight_cell_service`

**File:** `http_weight_cell_factory.py`

Factory function that constructs a `WeightCellService` wired to HTTP transports.

```python
def build_http_weight_cell_service(
    cells_config: GlueCellsConfig,
    messaging:    IMessagingService,
) -> WeightCellService:
    ...
```

- Creates one `HttpCellTransport` per cell for the transport role
- Creates a **separate** `HttpCellTransport` instance per cell for the calibrator role (same class, different instance — both share the same config and URL)
- Returns a fully constructed `WeightCellService`

To swap the transport layer (e.g., to serial/USB), replace this factory function only.

---

## Data Flow

```
build_http_weight_cell_service(cells_config, messaging)
        │
        │  for each CellConfig in cells_config:
        │
        ├─ transport_factory(cfg)  → HttpCellTransport(cfg)
        │       connects to: cfg.url
        │       timeout:     cfg.fetch_timeout_seconds
        │
        └─ calibrator_factory(cfg) → HttpCellTransport(cfg)
                (separate instance, same URL)
        │
        ▼
WeightCellService(cells_config, transport_factory, calibrator_factory, messaging)
```

---

## HTTP Endpoints Summary

| Operation | Method | Path |
|-----------|--------|------|
| Connect probe / read weight | GET | `{cell_url}` |
| Tare | GET | `{cell_url}/tare` |
| Update offset | GET | `{cell_url}/update-config?offset={v}` |
| Update scale | GET | `{cell_url}/update-config?scale={v}` |
| Update both | GET | `{cell_url}/update-config?offset={v}&scale={v}` |

The `cell_url` comes from `CellConfig.url` in the cells settings JSON file.

---

## Usage Example

```python
from src.engine.hardware.weight.http.http_weight_cell_factory import build_http_weight_cell_service

service = build_http_weight_cell_service(
    cells_config=app.get_settings("cells"),
    messaging=messaging_service,
)

service.start_monitoring(cell_ids=[1, 2], interval_s=0.5)
```

---

## Design Notes

- **Single class for both interfaces**: `HttpCellTransport` implements `ICellTransport` and `ICellCalibrator`. This is appropriate because the same HTTP server handles both reading and calibration. If a future hardware type separates these concerns, two classes can implement the interfaces independently.
- **`get_config` returns local data**: The server has no endpoint for reading back calibration parameters. `get_config()` returns the `CalibrationConfig` embedded in the local `CellConfig` from settings.
- **All calibration calls use GET**: This matches the existing firmware API design. The query-parameter-based update approach avoids body parsing on the embedded server.
- **`requests` is a hard dependency**: Unlike `pyserial` in the Modbus package, `requests` is imported at module level and must be installed.
