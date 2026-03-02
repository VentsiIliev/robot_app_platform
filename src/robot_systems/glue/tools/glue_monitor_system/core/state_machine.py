"""
Glue Monitor System State Management
Implements clean state management following SOLID principles.
States are published via MessageBroker for system-wide awareness.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime
import threading


class ServiceState(Enum):
    """
    Service states following the same pattern as Robot and Vision services.
    State Transitions:
    INITIALIZING → READY (on successful initialization)
    INITIALIZING → ERROR (on initialization failure)
    READY → DISCONNECTED (on connection loss)
    READY → ERROR (on critical error)
    DISCONNECTED → READY (on reconnection)
    ERROR → INITIALIZING (on manual reset/restart)
    """
    INITIALIZING = "initializing"
    READY = "ready"
    DISCONNECTED = "disconnected"
    ERROR = "error"

    def __str__(self):
        return self.value


class CellState(Enum):
    """
    Individual glue cell states.
    """
    UNKNOWN = "unknown"
    INITIALIZING = "initializing"
    READY = "ready"
    LOW_WEIGHT = "low_weight"
    EMPTY = "empty"
    ERROR = "error"
    DISCONNECTED = "disconnected"

    def __str__(self):
        return self.value


@dataclass
class StateContext:
    """
    Context information for state changes.
    Provides detailed information about why a state changed.
    """
    timestamp: datetime
    previous_state: Optional[ServiceState]
    current_state: ServiceState
    reason: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for publishing"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'previous_state': str(self.previous_state) if self.previous_state else None,
            'current_state': str(self.current_state),
            'reason': self.reason,
            'details': self.details or {}
        }


@dataclass
class CellStateContext:
    """
    Context information for individual cell state changes.
    """
    cell_id: int
    timestamp: datetime
    previous_state: Optional[CellState]
    current_state: CellState
    reason: str
    weight: Optional[float] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for publishing"""
        return {
            'cell_id': self.cell_id,
            'timestamp': self.timestamp.isoformat(),
            'previous_state': str(self.previous_state) if self.previous_state else None,
            'current_state': str(self.current_state),
            'reason': self.reason,
            'weight': self.weight,
            'details': self.details or {}
        }


class IStatePublisher:
    """
    Interface for state publishers.
    Follows Interface Segregation Principle (SOLID).
    """

    def publish_service_state(self, context: StateContext) -> None:
        """Publish service state change"""
        raise NotImplementedError

    def publish_cell_state(self, context: CellStateContext) -> None:
        """Publish cell state change"""
        raise NotImplementedError


class MessageBrokerStatePublisher(IStatePublisher):
    """
    Publishes state changes via MessageBroker.
    Single Responsibility: Only handles state publishing.
    """

    def __init__(self, broker):
        self.broker = broker

    def publish_service_state(self, context: StateContext) -> None:
        """Publish service state to MessageBroker"""
        from communication_layer.api.v1.topics import GlueMonitorServiceTopics
        topic = GlueMonitorServiceTopics.SERVICE_STATE
        payload = context.to_dict()
        self.broker.publish(topic, payload)
        print(f"[StatePublisher] Service state: {context.current_state} - {context.reason}")

    def publish_cell_state(self, context: CellStateContext) -> None:
        """Publish cell state to MessageBroker"""
        from communication_layer.api.v1.topics import GlueCellTopics
        # Dynamic topic based on cell ID
        topic = GlueCellTopics.cell_state(context.cell_id)
        payload = context.to_dict()
        self.broker.publish(topic, payload)
        print(f"[StatePublisher] Cell {context.cell_id} state: {context.current_state} - {context.reason}")


class StateManager:
    """
    Manages state transitions and ensures valid state machine flow.
    Single Responsibility: State management logic only.
    Open/Closed: Open for extension (new states), closed for modification.
    """
    # Valid state transitions
    VALID_TRANSITIONS = {
        ServiceState.INITIALIZING: {ServiceState.READY, ServiceState.ERROR},
        ServiceState.READY: {ServiceState.DISCONNECTED, ServiceState.ERROR, ServiceState.INITIALIZING},
        ServiceState.DISCONNECTED: {ServiceState.READY, ServiceState.ERROR, ServiceState.INITIALIZING},
        ServiceState.ERROR: {ServiceState.INITIALIZING, ServiceState.READY}
    }
    VALID_CELL_TRANSITIONS = {
        CellState.UNKNOWN: {CellState.INITIALIZING, CellState.ERROR},
        CellState.INITIALIZING: {CellState.READY, CellState.LOW_WEIGHT, CellState.EMPTY, CellState.ERROR},
        CellState.READY: {CellState.LOW_WEIGHT, CellState.EMPTY, CellState.ERROR, CellState.DISCONNECTED},
        CellState.LOW_WEIGHT: {CellState.READY, CellState.EMPTY, CellState.ERROR, CellState.DISCONNECTED},
        CellState.EMPTY: {CellState.READY, CellState.LOW_WEIGHT, CellState.ERROR, CellState.DISCONNECTED},
        CellState.ERROR: {CellState.INITIALIZING, CellState.READY},
        CellState.DISCONNECTED: {CellState.INITIALIZING, CellState.READY, CellState.ERROR}
    }

    def __init__(self, publisher: IStatePublisher):
        self.publisher = publisher
        self._current_state = ServiceState.INITIALIZING
        self._cell_states: Dict[int, CellState] = {1: CellState.UNKNOWN, 2: CellState.UNKNOWN, 3: CellState.UNKNOWN}
        self._lock = threading.Lock()

    def transition_to(self, new_state: ServiceState, reason: str, details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Transition to a new service state.
        Args:
            new_state: The target state
            reason: Why the transition is happening
            details: Additional context information
        Returns:
            True if transition was successful, False otherwise
        """
        with self._lock:
            if not self._is_valid_transition(self._current_state, new_state):
                print(f"[StateManager] Invalid transition: {self._current_state} → {new_state}")
                return False
            previous_state = self._current_state
            self._current_state = new_state
            context = StateContext(
                timestamp=datetime.now(),
                previous_state=previous_state,
                current_state=new_state,
                reason=reason,
                details=details
            )
            self.publisher.publish_service_state(context)
            return True

    def transition_cell_to(self, cell_id: int, new_state: CellState, reason: str,
                           weight: Optional[float] = None, details: Optional[Dict[str, Any]] = None) -> bool:
        """
        Transition a cell to a new state.
        Args:
            cell_id: The cell ID (1, 2, or 3)
            new_state: The target state
            reason: Why the transition is happening
            weight: Current weight reading
            details: Additional context information
        Returns:
            True if transition was successful, False otherwise
        """
        with self._lock:
            if cell_id not in self._cell_states:
                print(f"[StateManager] Invalid cell ID: {cell_id}")
                return False
            current = self._cell_states[cell_id]
            if not self._is_valid_cell_transition(current, new_state):
                print(f"[StateManager] Invalid cell {cell_id} transition: {current} → {new_state}")
                return False
            previous_state = current
            self._cell_states[cell_id] = new_state
            context = CellStateContext(
                cell_id=cell_id,
                timestamp=datetime.now(),
                previous_state=previous_state,
                current_state=new_state,
                reason=reason,
                weight=weight,
                details=details
            )
            self.publisher.publish_cell_state(context)
            return True

    def get_current_state(self) -> ServiceState:
        """Get current service state"""
        with self._lock:
            return self._current_state

    def get_cell_state(self, cell_id: int) -> Optional[CellState]:
        """Get current state of a cell"""
        with self._lock:
            return self._cell_states.get(cell_id)

    def get_all_cell_states(self) -> Dict[int, CellState]:
        """Get states of all cells"""
        with self._lock:
            return self._cell_states.copy()

    def _is_valid_transition(self, from_state: ServiceState, to_state: ServiceState) -> bool:
        """Check if state transition is valid"""
        if from_state == to_state:
            return False  # No self-transitions
        valid_targets = self.VALID_TRANSITIONS.get(from_state, set())
        return to_state in valid_targets

    def _is_valid_cell_transition(self, from_state: CellState, to_state: CellState) -> bool:
        """Check if cell state transition is valid"""
        if from_state == to_state:
            return False  # No self-transitions
        valid_targets = self.VALID_CELL_TRANSITIONS.get(from_state, set())
        return to_state in valid_targets


class StateDeterminer:
    """
    Determines appropriate states based on system conditions.
    Single Responsibility: State determination logic.
    """
    # Configurable thresholds
    LOW_WEIGHT_THRESHOLD_KG = 0.5
    EMPTY_THRESHOLD_KG = 0.1
    CONNECTION_TIMEOUT_SECONDS = 10.0

    @staticmethod
    def determine_cell_state_from_weight(weight: Optional[float], last_update_time: Optional[datetime]) -> CellState:
        """
        Determine cell state based on weight reading.
        Args:
            weight: Current weight in kg (None if unavailable)
            last_update_time: When the last update was received
        Returns:
            Appropriate CellState
        """
        # Check for disconnection
        if last_update_time is not None:
            time_since_update = (datetime.now() - last_update_time).total_seconds()
            if time_since_update > StateDeterminer.CONNECTION_TIMEOUT_SECONDS:
                return CellState.DISCONNECTED
        # Check weight levels
        if weight is None:
            return CellState.ERROR
        if weight < StateDeterminer.EMPTY_THRESHOLD_KG:
            return CellState.EMPTY
        elif weight < StateDeterminer.LOW_WEIGHT_THRESHOLD_KG:
            return CellState.LOW_WEIGHT
        else:
            return CellState.READY

    @staticmethod
    def determine_service_state_from_cells(cell_states: Dict[int, CellState]) -> ServiceState:
        """
        Determine overall service state based on cell states.
        Args:
            cell_states: Dictionary of cell ID to cell state
        Returns:
            Appropriate ServiceState
        """
        # If any cell is in ERROR state, service is in ERROR
        if any(state == CellState.ERROR for state in cell_states.values()):
            return ServiceState.ERROR
        # If all cells are DISCONNECTED, service is DISCONNECTED
        if all(state == CellState.DISCONNECTED for state in cell_states.values()):
            return ServiceState.DISCONNECTED
        # If all cells are READY, service is READY
        ready_states = {CellState.READY, CellState.LOW_WEIGHT, CellState.EMPTY}
        if all(state in ready_states for state in cell_states.values()):
            return ServiceState.READY
        # If cells are still initializing
        if any(state in {CellState.UNKNOWN, CellState.INITIALIZING} for state in cell_states.values()):
            return ServiceState.INITIALIZING
        # Default to READY if we have mixed states
        return ServiceState.READY


class StateMonitor:
    """
    Monitors system state and triggers appropriate transitions.
    Dependency Inversion: Depends on abstractions (StateManager, StateDeterminer).
    """

    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.cell_last_update: Dict[int, Optional[datetime]] = {1: None, 2: None, 3: None}
        self.cell_weights: Dict[int, Optional[float]] = {1: None, 2: None, 3: None}
        self._lock = threading.Lock()

    def update_cell_weight(self, cell_id: int, weight: float) -> None:
        """
        Update cell weight and determine new state.

        Args:
            cell_id: The cell ID
            weight: The new weight reading in kg
        """
        with self._lock:
            self.cell_weights[cell_id] = weight
            self.cell_last_update[cell_id] = datetime.now()

        # Determine new state based on weight
        new_state = StateDeterminer.determine_cell_state_from_weight(
            weight,
            self.cell_last_update[cell_id]
        )

        # Get current state
        current_state = self.state_manager.get_cell_state(cell_id)

        # print(f"[StateMonitor] Cell {cell_id}: weight={weight:.3f}kg, current={current_state}, new={new_state}")

        # Special handling: INITIALIZING can transition to any operational state
        # This is the first weight reading, so we allow direct transition
        if current_state == CellState.INITIALIZING and new_state in {
            CellState.READY, CellState.LOW_WEIGHT, CellState.EMPTY
        }:
            # print(f"[StateMonitor] Cell {cell_id}: Transitioning from INITIALIZING to {new_state}")
            # Valid transition from INITIALIZING to operational state
            result = self.state_manager.transition_cell_to(
                cell_id=cell_id,
                new_state=new_state,
                reason=f"First weight reading: {weight:.3f}kg",
                weight=weight,
                details={'initial_calibration': True}
            )
            # print(f"[StateMonitor] Cell {cell_id}: Transition result = {result}")
        elif current_state != new_state:
            # print(f"[StateMonitor] Cell {cell_id}: Transitioning from {current_state} to {new_state}")
            # Normal state transition
            result = self.state_manager.transition_cell_to(
                cell_id=cell_id,
                new_state=new_state,
                reason=f"Weight changed to {weight:.3f}kg",
                weight=weight,
                details={'threshold_check': 'passed'}
            )
            # print(f"[StateMonitor] Cell {cell_id}: Transition result = {result}")
        else:
            pass
            # print(f"[StateMonitor] Cell {cell_id}: No state change needed (already {current_state})")

    def check_connection_health(self) -> None:
        """
        Check connection health for all cells.
        Should be called periodically.
        """
        for cell_id in [1, 2, 3]:
            with self._lock:
                last_update = self.cell_last_update[cell_id]
                weight = self.cell_weights[cell_id]
            new_state = StateDeterminer.determine_cell_state_from_weight(weight, last_update)
            current_state = self.state_manager.get_cell_state(cell_id)
            if current_state != new_state and new_state == CellState.DISCONNECTED:
                self.state_manager.transition_cell_to(
                    cell_id=cell_id,
                    new_state=new_state,
                    reason="Connection timeout",
                    weight=weight,
                    details={'last_update': last_update.isoformat() if last_update else None}
                )

    def update_overall_service_state(self) -> None:
        """
        Update overall service state based on cell states.
        Should be called after cell state changes.
        """
        cell_states = self.state_manager.get_all_cell_states()
        new_service_state = StateDeterminer.determine_service_state_from_cells(cell_states)
        current_service_state = self.state_manager.get_current_state()
        if current_service_state != new_service_state:
            self.state_manager.transition_to(
                new_state=new_service_state,
                reason="Updated based on cell states",
                details={'cell_states': {k: str(v) for k, v in cell_states.items()}}
            )

    def mark_initialization_complete(self) -> None:
        """Mark service as initialized and ready"""
        self.state_manager.transition_to(
            ServiceState.READY,
            reason="Initialization completed successfully"
        )

    def mark_initialization_failed(self, error: str) -> None:
        """Mark initialization as failed"""
        self.state_manager.transition_to(
            ServiceState.ERROR,
            reason="Initialization failed",
            details={'error': error}
        )
