# `src/engine/hardware/weight/` — Weight Cell Service

The weight package provides a multi-cell weight measurement system. `WeightCellService` manages the lifecycle, monitoring, and calibration of one or more physical weight cells. Each cell operates on its own daemon thread, publishes readings to the messaging bus, and auto-reconnects after errors.

---

## Class Diagram

```
IWeightCellService (ABC)
       │
       └── WeightCellService
                 │ owns many
           _CellContext (internal)
                 ├── config:      CellConfig
                 ├── transport:   ICellTransport
                 ├── calibrator:  ICellCalibrator
                 ├── state:       CellState
                 └── monitor_thread: Thread
```

---

## API Reference

### `WeightCellService`

**File:** `weight_cell_service.py`

```python
class WeightCellService(IWeightCellService):
    def __init__(
        self,
        cells_config:       CellsConfig,
        transport_factory:  Callable[[CellConfig], ICellTransport],
        calibrator_factory: Callable[[CellConfig], ICellCalibrator],
        messaging:          IMessagingService,
    ): ...
```

**Lifecycle methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `connect` | `(cell_id: int) → bool` | Connect a single cell; publishes state transitions |
| `disconnect` | `(cell_id: int) → None` | Disconnect a single cell |
| `connect_all` | `() → None` | Non-blocking: connects each cell in its own daemon thread |
| `disconnect_all` | `() → None` | Disconnect all cells synchronously |

**Reading methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `read_weight` | `(cell_id: int) → Optional[WeightReading]` | Read and publish one weight sample; `None` if not connected |
| `get_cell_state` | `(cell_id: int) → CellState` | Current state of a cell |
| `get_connected_cell_ids` | `() → List[int]` | IDs of all cells currently in `CONNECTED` state |

**Monitoring methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `start_monitoring` | `(cell_ids: List[int], interval_s: float = 0.5) → None` | Start one daemon thread per cell |
| `stop_monitoring` | `() → None` | Signal all monitor threads to stop; joins with 3s timeout |

**Calibration methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `tare` | `(cell_id: int) → bool` | Zero the cell reading |
| `get_calibration` | `(cell_id: int) → Optional[CalibrationConfig]` | Retrieve current calibration parameters |
| `update_offset` | `(cell_id: int, offset: float) → bool` | Update zero offset |
| `update_scale` | `(cell_id: int, scale: float) → bool` | Update scale factor |
| `update_config` | `(cell_id: int, offset: float, scale: float) → bool` | Update both offset and scale atomically |

---

### Configuration Classes (`config.py`)

#### `CellConfig`

```python
@dataclass(frozen=True)
class CellConfig:
    id: int
    type: str
    url: str
    capacity: float
    fetch_timeout_seconds: float
    data_fetch_interval_ms: int
    calibration: CalibrationConfig
    measurement: MeasurementConfig
    motor_address: int = 0
```

#### `CalibrationConfig`

```python
@dataclass(frozen=True)
class CalibrationConfig:
    zero_offset: float
    scale_factor: float
```

#### `MeasurementConfig`

```python
@dataclass(frozen=True)
class MeasurementConfig:
    sampling_rate: int
    filter_cutoff: float
    averaging_samples: int
    min_weight_threshold: float
    max_weight_threshold: float
```

#### `CellsConfig`

```python
@dataclass(frozen=True)
class CellsConfig:
    cells: List[CellConfig]

    def get_cell_by_id(self, cell_id: int) -> Optional[CellConfig]: ...
    def get_all_cell_ids(self) -> List[int]: ...
    def get_cells_by_type(self, cell_type: str) -> List[CellConfig]: ...
    @property
    def cell_count(self) -> int: ...
```

#### `CellsConfigSerializer`

Implements `ISettingsSerializer[CellsConfig]`. `settings_type = "cells_config"`.

---

## Data Flow

### Monitoring Loop (per cell)

```
start_monitoring(cell_ids, interval_s)
        │
        │  per cell_id
        ▼
daemon Thread: _cell_monitor_loop(cell_id, interval_s)
        │
        ├── state == CONNECTED ──────────────────────────────────────────┐
        │       read_weight(cell_id)                                     │
        │           │                                                    │
        │           ├─ transport.read_weight() → float                  │
        │           │                                                    │
        │           ├─ publish WeightTopics.reading(cell_id)            │
        │           │          → WeightReading                          │
        │           │                                                    │
        │           └─ publish WeightTopics.all_readings()              │
        │                      → WeightReading                          │
        │                                                                │
        ├── state == DISCONNECTED or ERROR                               │
        │       accumulate time                                          │
        │       if time >= 5s → connect(cell_id) → try reconnect        │
        │                                                                │
        └── time.sleep(interval_s) ──────────────────────────────────────┘
              (interval from CellConfig.data_fetch_interval_ms if set,
               otherwise the interval_s argument)
```

### State Transitions

```
  ┌─────────────────┐
  │   DISCONNECTED  │◄──────────────────────────────────────┐
  └────────┬────────┘                                       │
           │ connect()                                      │ disconnect()
           ▼                                                │
  ┌─────────────────┐   transport fails   ┌─────────────────┤
  │   CONNECTING    │────────────────────►│     ERROR       │
  └────────┬────────┘                    └─────────────────┘
           │ transport.connect() == True         ▲
           ▼                                     │ read_weight() exception
  ┌─────────────────┐                            │
  │    CONNECTED    │────────────────────────────┘
  └─────────────────┘
```

Every state transition publishes a `CellStateEvent` to `WeightTopics.state(cell_id)`.

---

## Pub/Sub Topics

| Topic | Method | Payload | When Published |
|-------|--------|---------|---------------|
| `weight/cell/{id}/state` | `WeightTopics.state(id)` | `CellStateEvent` | On every state transition |
| `weight/cell/{id}/reading` | `WeightTopics.reading(id)` | `WeightReading` | On each successful `read_weight` |
| `weight/cell/all/reading` | `WeightTopics.all_readings()` | `WeightReading` | On each successful `read_weight` (any cell) |

### `WeightReading`

```python
@dataclass(frozen=True)
class WeightReading:
    cell_id:   int
    value:     float
    unit:      str      = "g"
    timestamp: datetime

    def is_valid(self, min_threshold: float, max_threshold: float) -> bool: ...
```

### `CellStateEvent`

```python
@dataclass(frozen=True)
class CellStateEvent:
    cell_id:   int
    state:     CellState   # DISCONNECTED | CONNECTING | CONNECTED | ERROR
    message:   str
    timestamp: datetime
```

### `CellState` Enum

```python
class CellState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING   = "connecting"
    CONNECTED    = "connected"
    ERROR        = "error"
```

---

## Usage Example

```python
from src.engine.hardware.weight.http.http_weight_cell_factory import build_http_weight_cell_service
from src.shared_contracts.events.weight_events import WeightTopics, WeightReading

# Build service
service = build_http_weight_cell_service(cells_config, messaging)

# Subscribe to readings
class MyWidget:
    def __init__(self, messaging):
        messaging.subscribe(WeightTopics.reading(1), self._on_reading)

    def _on_reading(self, reading: WeightReading) -> None:
        print(f"Cell {reading.cell_id}: {reading.value} {reading.unit}")

# Start continuous monitoring
service.start_monitoring(cell_ids=[1, 2], interval_s=0.5)

# Tare cell 1
service.tare(1)
```

---

## Design Notes

- **Thread safety**: each `_CellContext` has a `threading.Lock` protecting state reads and writes. State is published outside the lock to avoid deadlocks with message broker callbacks.
- **Reconnect interval**: hardcoded at `_RECONNECT_INTERVAL_S = 5.0` seconds. The monitor thread accumulates elapsed time and reconnects when the threshold is crossed.
- **Factory pattern**: `WeightCellService.__init__` accepts `transport_factory` and `calibrator_factory` callables rather than concrete objects. Swapping transport (e.g., from HTTP to serial) requires only a different factory — the service itself is unchanged.
- **`data_fetch_interval_ms`**: if non-zero in `CellConfig`, it overrides the `interval_s` argument to `start_monitoring` for that specific cell.
