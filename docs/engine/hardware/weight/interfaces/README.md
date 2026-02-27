# `src/engine/hardware/weight/interfaces/` — Weight Cell Interfaces

This package defines the three abstract interfaces that decouple `WeightCellService` from any specific hardware protocol or calibration backend. All concrete implementations must satisfy these contracts.

---

## Class Diagram

```
ICellTransport (ABC)          ICellCalibrator (ABC)
      │                               │
      │ implemented by                │ implemented by
      └──────────┬────────────────────┘
                 │
         HttpCellTransport    ← (http/ package)
         (implements both)
```

Note: `HttpCellTransport` intentionally implements both interfaces. This is valid because HTTP-based cells use the same endpoint for transport and calibration. A different backend (e.g., serial) could split these into two separate classes.

---

## API Reference

### `ICellTransport`

**File:** `i_cell_transport.py`

Raw communication interface for a single weight cell. Responsible for connection lifecycle and reading weight values. Has no knowledge of calibration or business logic.

```python
class ICellTransport(ABC):
    def connect(self) -> bool: ...
    def disconnect(self) -> None: ...
    @property
    def is_connected(self) -> bool: ...
    def read_weight(self) -> float: ...
```

| Method | Returns | Description |
|--------|---------|-------------|
| `connect()` | `bool` | Open connection; `True` on success |
| `disconnect()` | `None` | Close connection; should not raise |
| `is_connected` | `bool` | `True` if currently connected (property) |
| `read_weight()` | `float` | Return raw weight value; raises on transport error |

---

### `ICellCalibrator`

**File:** `i_cell_calibrator.py`

Calibration operations for a single weight cell. Decoupled from transport — updating calibration parameters is a distinct concern from reading raw values.

```python
class ICellCalibrator(ABC):
    def tare(self, cell_id: int) -> bool: ...
    def get_config(self, cell_id: int) -> CalibrationConfig: ...
    def update_offset(self, cell_id: int, offset: float) -> bool: ...
    def update_scale(self, cell_id: int, scale: float) -> bool: ...
    def update_config(self, cell_id: int, offset: float, scale: float) -> bool: ...
```

| Method | Returns | Description |
|--------|---------|-------------|
| `tare(cell_id)` | `bool` | Zero-point calibration (set current reading as zero) |
| `get_config(cell_id)` | `CalibrationConfig` | Retrieve current calibration parameters |
| `update_offset(cell_id, offset)` | `bool` | Update zero offset only |
| `update_scale(cell_id, scale)` | `bool` | Update scale factor only |
| `update_config(cell_id, offset, scale)` | `bool` | Update both atomically |

The `cell_id` parameter is passed for logging and routing purposes — implementations may or may not use it if they already know their own ID from construction.

---

### `IWeightCellService`

**File:** `i_weight_cell_service.py`

The top-level service interface consumed by applications. Combines lifecycle, reading, monitoring, and calibration operations for a multi-cell installation.

```python
class IWeightCellService(ABC):
    # Lifecycle
    def connect(self, cell_id: int) -> bool: ...
    def disconnect(self, cell_id: int) -> None: ...
    def connect_all(self) -> None: ...
    def disconnect_all(self) -> None: ...
    # Reading
    def read_weight(self, cell_id: int) -> Optional[WeightReading]: ...
    def get_cell_state(self, cell_id: int) -> CellState: ...
    def get_connected_cell_ids(self) -> List[int]: ...
    # Monitoring
    def start_monitoring(self, cell_ids: List[int], interval_s: float = 0.5) -> None: ...
    def stop_monitoring(self) -> None: ...
    # Calibration
    def tare(self, cell_id: int) -> bool: ...
    def get_calibration(self, cell_id: int) -> Optional[CalibrationConfig]: ...
    def update_offset(self, cell_id: int, offset: float) -> bool: ...
    def update_scale(self, cell_id: int, scale: float) -> bool: ...
    def update_config(self, cell_id: int, offset: float, scale: float) -> bool: ...
```

Concrete implementation: `WeightCellService` (see [weight/README.md](../README.md)).

---

## Design Notes

- **Separation of concerns**: `ICellTransport` and `ICellCalibrator` are kept separate so a transport-only implementation (e.g., a read-only sensor) doesn't need to implement calibration methods.
- **`cell_id` in calibrator methods**: The `cell_id` argument lets a single calibrator instance serve multiple cells if needed. In the HTTP implementation, the calibrator already knows the cell's URL from construction, so `cell_id` is only used for logging.
- **`CalibrationConfig` return type**: `ICellCalibrator.get_config()` returns a `CalibrationConfig` from `src/engine/hardware/weight/config.py`. For the HTTP transport, this returns the locally cached config from settings (the remote server has no get-config endpoint).
