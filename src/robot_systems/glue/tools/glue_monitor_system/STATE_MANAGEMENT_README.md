# Glue Monitor System - State Management
## Overview
This document describes the clean, SOLID-compliant state management system for the Glue Monitor System. The implementation follows the same patterns as the Robot and Vision services, providing consistent state tracking and publishing via MessageBroker.
## Architecture
The state management system follows **SOLID principles**:
### Single Responsibility Principle (S)
- `StateManager` - Only manages state transitions
- `StatePublisher` - Only publishes state changes
- `StateDeterminer` - Only determines appropriate states
- `StateMonitor` - Only monitors and triggers transitions
### Open/Closed Principle (O)
- State machine is open for extension (new states can be added)
- Core logic is closed for modification
### Liskov Substitution Principle (L)
- `IStatePublisher` interface allows different publisher implementations
- Mock publishers can be used in tests
### Interface Segregation Principle (I)
- `IStatePublisher` provides minimal interface
- Clients only depend on methods they use
### Dependency Inversion Principle (D)
- `StateManager` depends on `IStatePublisher` abstraction
- `StateMonitor` depends on `StateManager` abstraction
## Components
### 1. State Enums
#### ServiceState
```python
class ServiceState(Enum):
    INITIALIZING = "initializing"  # Service is starting up
    READY = "ready"               # Service is operational
    DISCONNECTED = "disconnected" # Connection lost
    ERROR = "error"               # Critical error occurred
```
**Valid Transitions:**
```
INITIALIZING → READY (successful init)
INITIALIZING → ERROR (init failed)
READY → DISCONNECTED (connection lost)
READY → ERROR (critical error)
DISCONNECTED → READY (reconnected)
ERROR → INITIALIZING (manual restart)
```
#### CellState
```python
class CellState(Enum):
    UNKNOWN = "unknown"           # Initial state
    INITIALIZING = "initializing" # Cell starting up
    READY = "ready"               # Normal operation
    LOW_WEIGHT = "low_weight"     # Weight below threshold
    EMPTY = "empty"               # Cell is empty
    ERROR = "error"               # Sensor error
    DISCONNECTED = "disconnected" # Connection lost
```
**Valid Transitions:**
```
UNKNOWN → INITIALIZING
INITIALIZING → READY / LOW_WEIGHT / EMPTY / ERROR
READY ↔ LOW_WEIGHT ↔ EMPTY
READY → ERROR / DISCONNECTED
ERROR → INITIALIZING / READY
DISCONNECTED → INITIALIZING / READY / ERROR
```
### 2. State Context
Provides detailed information about state changes:
```python
@dataclass
class StateContext:
    timestamp: datetime
    previous_state: Optional[ServiceState]
    current_state: ServiceState
    reason: str
    details: Optional[Dict[str, Any]]
```
### 3. StateManager
Manages state transitions and ensures valid state machine flow.
**Key Methods:**
```python
def transition_to(new_state: ServiceState, reason: str, details: Optional[Dict]) -> bool
def transition_cell_to(cell_id: int, new_state: CellState, reason: str, weight: float) -> bool
def get_current_state() -> ServiceState
def get_cell_state(cell_id: int) -> CellState
def get_all_cell_states() -> Dict[int, CellState]
```
**Features:**
- Thread-safe with locks
- Validates all transitions
- Prevents self-transitions
- Publishes state changes automatically
### 4. StatePublisher
Publishes state changes via MessageBroker.
**Topics:**
- Service state: `glue/monitor/service/state`
- Cell states: `glue/cell/{cell_id}/state`
**Payload Format:**
```json
{
  "timestamp": "2025-12-10T14:30:15.123Z",
  "previous_state": "initializing",
  "current_state": "ready",
  "reason": "Initialization completed successfully",
  "details": {}
}
```
### 5. StateDeterminer
Determines appropriate states based on system conditions.
**Thresholds (Configurable):**
```python
LOW_WEIGHT_THRESHOLD_KG = 0.5    # Below this = LOW_WEIGHT
EMPTY_THRESHOLD_KG = 0.1         # Below this = EMPTY
CONNECTION_TIMEOUT_SECONDS = 10.0 # No updates = DISCONNECTED
```
**Logic:**
```python
def determine_cell_state_from_weight(weight, last_update_time) -> CellState
def determine_service_state_from_cells(cell_states) -> ServiceState
```
### 6. StateMonitor
Monitors system and triggers appropriate transitions.
**Key Methods:**
```python
def update_cell_weight(cell_id: int, weight: float) -> None
def check_connection_health() -> None
def update_overall_service_state() -> None
def mark_initialization_complete() -> None
def mark_initialization_failed(error: str) -> None
```
## Integration
### In GlueDataFetcher
```python
def __init__(self):
    # Initialize MessageBroker
    self.broker = MessageBroker()
    # Initialize state management
    from modules.shared.tools.glue_monitor_system.state_management import (
        StateManager, MessageBrokerStatePublisher, StateMonitor
    )
    publisher = MessageBrokerStatePublisher(self.broker)
    self.state_manager = StateManager(publisher)
    self.state_monitor = StateMonitor(self.state_manager)
    # ... rest of initialization
def publish_weights(self):
    # Publish weight values
    self.broker.publish(GlueTopics.GLUE_METER_1_VALUE, self.weight1)
    # ... etc
    # Update state monitoring (convert g to kg)
    self.state_monitor.update_cell_weight(1, self.weight1 / 1000.0)
    self.state_monitor.update_cell_weight(2, self.weight2 / 1000.0)
    self.state_monitor.update_cell_weight(3, self.weight3 / 1000.0)
    # Update overall service state
    self.state_monitor.update_overall_service_state()
def start(self):
    # Start the thread
    self.thread = threading.Thread(target=self._fetch_loop, daemon=True)
    self.thread.start()
    # Mark as ready
    self.state_monitor.mark_initialization_complete()
```
### In GlueMeter
```python
def fetchData(self):
    # Fetch weight data
    weight = self.fetcher.weight1  # for cell 1
    # Sync state from state manager
    self._get_state_from_manager()
    return weight
def _get_state_from_manager(self):
    """Synchronize state from centralized state manager"""
    cell_state = self.fetcher.state_manager.get_cell_state(self.id)
    if cell_state:
        self.state = str(cell_state)
```
## Usage Examples
### Subscribe to State Changes
```python
from modules.shared.MessageBroker import MessageBroker
from communication_layer.api.v1.topics import GlueTopics
broker = MessageBroker()
def on_service_state_changed(state_data):
    print(f"Service state: {state_data['current_state']}")
    print(f"Reason: {state_data['reason']}")
def on_cell_state_changed(state_data):
    cell_id = state_data['cell_id']
    state = state_data['current_state']
    weight = state_data.get('weight')
    print(f"Cell {cell_id}: {state} (weight: {weight}kg)")
# Subscribe
broker.subscribe(GlueTopics.GLUE_MONITOR_SERVICE_STATE, on_service_state_changed)
broker.subscribe("glue/cell/1/state", on_cell_state_changed)
broker.subscribe("glue/cell/2/state", on_cell_state_changed)
broker.subscribe("glue/cell/3/state", on_cell_state_changed)
```
### Check Current State
```python
from modules.shared.tools.glue_monitor_system.data_fetcher import GlueDataFetcher
fetcher = GlueDataFetcher()
# Get service state
service_state = fetcher.state_manager.get_current_state()
print(f"Service: {service_state}")
# Get cell states
for cell_id in [1, 2, 3]:
    cell_state = fetcher.state_manager.get_cell_state(cell_id)
    print(f"Cell {cell_id}: {cell_state}")
```
### Manual State Transitions
```python
# Mark initialization failed
fetcher.state_monitor.mark_initialization_failed("Config error")
# Update cell weight manually
fetcher.state_monitor.update_cell_weight(1, 0.05)  # Will trigger EMPTY state
# Force overall state update
fetcher.state_monitor.update_overall_service_state()
```
## Testing
The system includes comprehensive unit tests covering:
- ✅ State enum values
- ✅ State context serialization
- ✅ Publisher functionality
- ✅ Valid state transitions
- ✅ Invalid transition rejection
- ✅ Cell state management
- ✅ State determination logic
- ✅ Weight threshold checking
- ✅ Connection timeout detection
- ✅ State monitoring
- ✅ Full lifecycle integration tests
**Run tests:**
```bash
cd src
python3 -m pytest modules/shared/tools/glue_monitor_system/test_state_management.py -v
```
**Test Coverage:**
- 7 test classes
- 25+ individual test cases
- Mock-based isolation
- Integration tests included
## State Flow Diagrams
### Service State Machine
```
     ┌─────────────────┐
     │  INITIALIZING   │
     └────┬───────┬────┘
          │       │
    (success)  (fail)
          │       │
          ↓       ↓
    ┌─────┴──┐  ┌─────────┐
    │ READY  │  │  ERROR  │
    └─┬───┬──┘  └────┬────┘
      │   │          │
 (timeout)(error) (restart)
      │   │          │
      ↓   ↓          ↓
 ┌─────────────────────┐
 │   DISCONNECTED      │
 └─────────────────────┘
```
### Cell State Machine
```
  ┌─────────┐
  │ UNKNOWN │
  └────┬────┘
       │
       ↓
  ┌──────────────┐
  │ INITIALIZING │
  └─────┬────────┘
        │
        ↓
   ┌────────┐
   │ READY  │ ←─────┐
   └┬──┬──┬─┘       │
    │  │  │     (refill)
    │  │  │         │
    │  │  └→ ┌──────────┐
    │  │     │LOW_WEIGHT│
    │  │     └────┬─────┘
    │  │          │
    │  │     (continue)
    │  │          │
    │  └────→ ┌───────┐
    │         │ EMPTY │
    │         └───────┘
    │
    └──→ ┌───────────────┐
         │ERROR/DISCONN. │
         └───────────────┘
```
## Benefits
### 1. **Consistency**
- Same pattern as Robot and Vision services
- Unified state management approach
- Predictable behavior
### 2. **Observability**
- All state changes published via MessageBroker
- Detailed context for each transition
- Easy monitoring and debugging
### 3. **Testability**
- Clean separation of concerns
- Mock-friendly interfaces
- Comprehensive test coverage
### 4. **Maintainability**
- SOLID principles followed
- Clear responsibilities
- Easy to extend
### 5. **Reliability**
- Thread-safe operations
- Validated transitions
- No invalid states possible
## Configuration
### Adjust Thresholds
```python
from modules.shared.tools.glue_monitor_system.state_management import StateDeterminer
# Modify thresholds
StateDeterminer.LOW_WEIGHT_THRESHOLD_KG = 0.8  # More conservative
StateDeterminer.EMPTY_THRESHOLD_KG = 0.2       # Higher empty threshold
StateDeterminer.CONNECTION_TIMEOUT_SECONDS = 5.0  # Faster timeout detection
```
### Custom Publisher
```python
from modules.shared.tools.glue_monitor_system.state_management import IStatePublisher
class CustomPublisher(IStatePublisher):
    def publish_service_state(self, context):
        # Custom publishing logic (e.g., to database, API, etc.)
        pass
    def publish_cell_state(self, context):
        # Custom publishing logic
        pass
# Use custom publisher
publisher = CustomPublisher()
state_manager = StateManager(publisher)
```
## Troubleshooting
### Issue: States not publishing
**Check:**
1. MessageBroker is initialized
2. Subscribers are registered before state changes
3. Topics match exactly (case-sensitive)
### Issue: Invalid transition errors
**Check:**
1. Review valid transition map in `StateManager`
2. Ensure proper initialization sequence
3. Check logs for transition rejection messages
### Issue: Cell states not updating
**Check:**
1. Weight values are being published
2. `update_cell_weight()` is being called
3. Threshold values are configured correctly
## Future Enhancements
Potential improvements:
1. **State History** - Track state change history
2. **State Persistence** - Save/restore state across restarts
3. **Metrics** - Count transitions, time in each state
4. **Alerts** - Trigger alerts on specific transitions
5. **State Predictor** - ML-based state prediction
## Conclusion
The Glue Monitor System now has enterprise-grade state management that is:
✅ **Clean** - SOLID principles, no spaghetti code  
✅ **Testable** - 25+ comprehensive unit tests  
✅ **Expandable** - Easy to add new states/logic  
✅ **Observable** - All changes published via MessageBroker  
✅ **Reliable** - Thread-safe, validated transitions  
✅ **Consistent** - Matches Robot/Vision service patterns  
---
**Version:** 1.0  
**Date:** December 10, 2025  
**Author:** Cobot Glue Dispensing System Team
---
## UI Integration
### GlueMeterCard Widget
The `GlueMeterCard` displays a **large color-coded state indicator (40x40)** in the header next to the title.
**File:** `plugins/core/dashboard/ui/widgets/GlueMeterCard.py`
**Features:**
- Large circular indicator (●) with color-coded border
- Rich tooltips showing state, weight, and reason
- Automatic updates via MessageBroker subscription
- Clean, modern design
**Implementation:**
```python
# State indicator in header
self.state_indicator = QLabel("●")
self.state_indicator.setFixedSize(40, 40)
self.state_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
# Subscribe to cell state topic
broker.subscribe(f"glue/cell/{self.index}/state", self.update_state_indicator)
def update_state_indicator(self, state_data: dict):
    """Update the state indicator based on cell state"""
    current_state = state_data.get('current_state', 'unknown')
    reason = state_data.get('reason', '')
    weight = state_data.get('weight')
    # State color mapping
    state_config = {
        'unknown': {'color': '#808080', 'text': 'Unknown'},
        'initializing': {'color': '#FFA500', 'text': 'Initializing...'},
        'ready': {'color': '#28a745', 'text': 'Ready'},
        'low_weight': {'color': '#ffc107', 'text': 'Low Weight'},
        'empty': {'color': '#dc3545', 'text': 'Empty'},
        'error': {'color': '#d9534f', 'text': 'Error'},
        'disconnected': {'color': '#6c757d', 'text': 'Disconnected'}
    }
    config = state_config.get(current_state, state_config['unknown'])
    # Update indicator style
    self.state_indicator.setStyleSheet(f"""
        QLabel {{
            font-size: 24px;
            color: {config['color']};
            background-color: white;
            border: 2px solid {config['color']};
            border-radius: 20px;
            padding: 5px;
        }}
    """)
    # Rich tooltip with context
    tooltip = f"{config['text']}"
    if weight is not None:
        tooltip += f"\nWeight: {weight:.3f} kg"
    if reason:
        tooltip += f"\n{reason}"
    self.state_indicator.setToolTip(tooltip)
```
**Visual Layout:**
```
┌────────────────────────────────────────┐
│  [Glue Meter 1            ] [🟢]       │  ← Header with state indicator
│  🧪 Type A             [⚙ Change]      │  ← Glue type
│  ┌──────────────────────────────────┐  │
│  │ 2500.00 g  ●  ████████▒▒▒▒▒▒▒▒▒ │  │  ← Progress bar
│  │            0% 20% 40% 60% 80% 100%│  │
│  └──────────────────────────────────┘  │
└────────────────────────────────────────┘
```
### GlueMeterWidget
The `GlueMeterWidget` shows a **small state indicator (16x16)** next to the weight display.
**File:** `plugins/core/dashboard/ui/widgets/GlueMeterWidget.py`
**Features:**
- Compact 16x16 circular indicator
- Positioned between weight label and progress bar
- Uses legacy state topic for backward compatibility
- Simple color coding (green/red/gray)
**Implementation:**
```python
# Small circular state indicator
self.state_indicator = QLabel()
self.state_indicator.setFixedSize(16, 16)
self.state_indicator.setStyleSheet("background-color: gray; border-radius: 8px;")
# Legacy state update (backward compatible)
def updateState(self, message):
    """Updates the circular status indicator"""
    if isinstance(message, str):
        state = message.strip().lower()
        if state == "ready":
            self.state_indicator.setStyleSheet(
                "background-color: green; border-radius: 8px;"
            )
        elif state in ("disconnected", "error"):
            self.state_indicator.setStyleSheet(
                "background-color: red; border-radius: 8px;"
            )
        else:
            self.state_indicator.setStyleSheet(
                "background-color: gray; border-radius: 8px;"
            )
```
**Visual Layout:**
```
┌────────────────────────────────────┐
│ 2500.00 g  ●  ████████▒▒▒▒▒▒▒▒▒▒▒ │
│               0% 20% 40% 60% 80% 100%│
└────────────────────────────────────┘
         ↑
    16x16 state indicator
```
### State Color Reference
| State | Color | Hex Code | Meaning |
|-------|-------|----------|---------|
| **Ready** | 🟢 Green | `#28a745` | Normal operation (weight > 0.5 kg) |
| **Low Weight** | 🟡 Yellow | `#ffc107` | Running low (0.1 - 0.5 kg) |
| **Empty** | 🔴 Red | `#dc3545` | Refill needed (< 0.1 kg) |
| **Initializing** | 🟠 Orange | `#FFA500` | Starting up |
| **Error** | 🔴 Dark Red | `#d9534f` | Sensor/system error |
| **Disconnected** | ⚫ Gray | `#6c757d` | Connection lost |
| **Unknown** | ⚫ Gray | `#808080` | State not determined |
### Dual State System
The system currently supports two state topic patterns for backward compatibility:
**New State System (Recommended):**
- **Topic:** `glue/cell/{cell_id}/state`
- **Publisher:** StateManager (state_management.py)
- **Format:** Full context dict with timestamp, reason, weight, details
- **Used by:** GlueMeterCard (large indicator)
**Legacy State System (Deprecated):**
- **Topic:** `GlueMeter_{id}/STATE`
- **Publisher:** GlueMeter.fetchData()
- **Format:** Simple string ("READY", "ERROR", "DISCONNECTED")
- **Used by:** GlueMeterWidget (small indicator)
### Migration to New State System
To migrate GlueMeterWidget to the new state system:
```python
# In GlueMeterWidget.__init__()
# Subscribe to new state topic
broker.subscribe(f"glue/cell/{self.id}/state", self.update_state_new)
def update_state_new(self, state_data: dict):
    """Update state using new state management system"""
    current_state = state_data.get('current_state', 'unknown')
    # Map new states to colors
    state_colors = {
        'ready': 'green',
        'low_weight': '#ffc107',
        'empty': 'red',
        'initializing': '#FFA500',
        'error': '#d9534f',
        'disconnected': 'gray',
        'unknown': 'gray'
    }
    color = state_colors.get(current_state, 'gray')
    self.state_indicator.setStyleSheet(
        f"background-color: {color}; border-radius: 8px;"
    )
    # Optional: Add tooltip
    weight = state_data.get('weight')
    if weight is not None:
        self.state_indicator.setToolTip(f"{current_state}: {weight:.3f} kg")
```
### Real-time State Flow
```
Weight Reading (2.5 kg)
        ↓
StateDeterminer.determine_cell_state_from_weight()
        ↓
StateMonitor.update_cell_weight()
        ↓
StateManager.transition_cell_to(READY)
        ↓
MessageBroker.publish("glue/cell/1/state", {...})
        ↓
    ┌───┴────┐
    ↓        ↓
GlueMeterCard    GlueMeterWidget
    ↓                ↓
🟢 Large Indicator  ● Small Indicator
```
### Cleanup
Both widgets properly unsubscribe from state topics:
```python
# In cleanup/destructor
broker.unsubscribe(f"glue/cell/{self.index}/state", self.update_state_indicator)
```
This prevents memory leaks and callback errors after widget destruction.
---
## Known Issues and Solutions
### Issue: State Indicators Show Gray on Load
**Problem:** GlueMeterCard state indicators remain gray even though state management is working correctly.
**Root Cause:** Timing issue - cards subscribe to state topics AFTER initial state transitions have already occurred.
**Solution:** Added `fetch_initial_state()` method that queries the state_manager directly after subscription.
```python
def fetch_initial_state(self) -> None:
    """Fetch the current state from GlueDataFetcher and update indicator"""
    fetcher = GlueDataFetcher()
    if hasattr(fetcher, 'state_manager'):
        current_state = fetcher.state_manager.get_cell_state(self.index)
        if current_state:
            weight_kg = fetcher.state_monitor.cell_weights.get(self.index)
            state_data = {
                'cell_id': self.index,
                'timestamp': datetime.datetime.now().isoformat(),
                'current_state': str(current_state),
                'reason': 'Initial state on subscription',
                'weight': weight_kg
            }
            self.update_state_indicator(state_data)
```
**Result:** Indicators show correct colors immediately on load! ✅
See `STATE_INDICATOR_TIMING_FIX.md` for full details.
