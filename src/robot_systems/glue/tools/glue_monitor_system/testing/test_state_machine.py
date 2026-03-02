"""
Unit tests for Glue Monitor State Management System
Tests all components following clean testing principles:
- Isolated tests
- Mock external dependencies
- Clear assertions
- Comprehensive coverage
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from modules.shared.tools.glue_monitor_system.core.state_machine import (
    ServiceState, CellState, StateContext, CellStateContext,
    IStatePublisher, MessageBrokerStatePublisher,
    StateManager, StateDeterminer, StateMonitor
)


class TestServiceState(unittest.TestCase):
    """Test ServiceState enum"""

    def test_service_state_values(self):
        """Test all service state values are correct"""
        self.assertEqual(str(ServiceState.INITIALIZING), "initializing")
        self.assertEqual(str(ServiceState.READY), "ready")
        self.assertEqual(str(ServiceState.DISCONNECTED), "disconnected")
        self.assertEqual(str(ServiceState.ERROR), "error")


class TestCellState(unittest.TestCase):
    """Test CellState enum"""

    def test_cell_state_values(self):
        """Test all cell state values are correct"""
        self.assertEqual(str(CellState.UNKNOWN), "unknown")
        self.assertEqual(str(CellState.INITIALIZING), "initializing")
        self.assertEqual(str(CellState.READY), "ready")
        self.assertEqual(str(CellState.LOW_WEIGHT), "low_weight")
        self.assertEqual(str(CellState.EMPTY), "empty")
        self.assertEqual(str(CellState.ERROR), "error")
        self.assertEqual(str(CellState.DISCONNECTED), "disconnected")


class TestStateContext(unittest.TestCase):
    """Test StateContext dataclass"""

    def test_to_dict(self):
        """Test StateContext converts to dict correctly"""
        context = StateContext(
            timestamp=datetime(2025, 12, 10, 14, 30, 0),
            previous_state=ServiceState.INITIALIZING,
            current_state=ServiceState.READY,
            reason="Initialization complete",
            details={'config_loaded': True}
        )
        result = context.to_dict()
        self.assertEqual(result['timestamp'], '2025-12-10T14:30:00')
        self.assertEqual(result['previous_state'], 'initializing')
        self.assertEqual(result['current_state'], 'ready')
        self.assertEqual(result['reason'], 'Initialization complete')
        self.assertEqual(result['details']['config_loaded'], True)

    def test_to_dict_no_previous_state(self):
        """Test StateContext with None previous state"""
        context = StateContext(
            timestamp=datetime.now(),
            previous_state=None,
            current_state=ServiceState.INITIALIZING,
            reason="Initial state"
        )
        result = context.to_dict()
        self.assertIsNone(result['previous_state'])


class TestMessageBrokerStatePublisher(unittest.TestCase):
    """Test MessageBrokerStatePublisher"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_broker = Mock()
        self.publisher = MessageBrokerStatePublisher(self.mock_broker)

    def test_publish_service_state(self):
        """Test service state publishing"""
        context = StateContext(
            timestamp=datetime.now(),
            previous_state=ServiceState.INITIALIZING,
            current_state=ServiceState.READY,
            reason="Test reason"
        )
        self.publisher.publish_service_state(context)
        self.mock_broker.publish.assert_called_once()
        call_args = self.mock_broker.publish.call_args
        self.assertIn('glue/monitor/service/state', call_args[0][0])

    def test_publish_cell_state(self):
        """Test cell state publishing"""
        context = CellStateContext(
            cell_id=2,
            timestamp=datetime.now(),
            previous_state=CellState.READY,
            current_state=CellState.LOW_WEIGHT,
            reason="Weight dropped",
            weight=0.3
        )
        self.publisher.publish_cell_state(context)
        self.mock_broker.publish.assert_called_once()
        call_args = self.mock_broker.publish.call_args
        self.assertEqual(call_args[0][0], "glue/cell/2/state")


class TestStateManager(unittest.TestCase):
    """Test StateManager transitions and validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_publisher = Mock(spec=IStatePublisher)
        self.manager = StateManager(self.mock_publisher)

    def test_initial_state(self):
        """Test initial state is INITIALIZING"""
        self.assertEqual(self.manager.get_current_state(), ServiceState.INITIALIZING)

    def test_valid_transition_initializing_to_ready(self):
        """Test valid transition from INITIALIZING to READY"""
        result = self.manager.transition_to(
            ServiceState.READY,
            "Initialization complete"
        )
        self.assertTrue(result)
        self.assertEqual(self.manager.get_current_state(), ServiceState.READY)
        self.mock_publisher.publish_service_state.assert_called_once()

    def test_valid_transition_initializing_to_error(self):
        """Test valid transition from INITIALIZING to ERROR"""
        result = self.manager.transition_to(
            ServiceState.ERROR,
            "Initialization failed"
        )
        self.assertTrue(result)
        self.assertEqual(self.manager.get_current_state(), ServiceState.ERROR)

    def test_invalid_transition(self):
        """Test invalid state transition is rejected"""
        # INITIALIZING can only go to READY or ERROR, not DISCONNECTED
        result = self.manager.transition_to(
            ServiceState.DISCONNECTED,
            "Invalid transition"
        )
        self.assertFalse(result)
        self.assertEqual(self.manager.get_current_state(), ServiceState.INITIALIZING)
        self.mock_publisher.publish_service_state.assert_not_called()

    def test_no_self_transition(self):
        """Test cannot transition to same state"""
        result = self.manager.transition_to(
            ServiceState.INITIALIZING,
            "Same state"
        )
        self.assertFalse(result)

    def test_cell_state_transitions(self):
        """Test cell state transitions"""
        # UNKNOWN → INITIALIZING
        result = self.manager.transition_cell_to(
            cell_id=1,
            new_state=CellState.INITIALIZING,
            reason="Starting initialization"
        )
        self.assertTrue(result)
        self.assertEqual(self.manager.get_cell_state(1), CellState.INITIALIZING)
        # INITIALIZING → READY
        result = self.manager.transition_cell_to(
            cell_id=1,
            new_state=CellState.READY,
            reason="Initialization complete",
            weight=2.5
        )
        self.assertTrue(result)
        self.assertEqual(self.manager.get_cell_state(1), CellState.READY)

    def test_invalid_cell_id(self):
        """Test invalid cell ID is rejected"""
        result = self.manager.transition_cell_to(
            cell_id=99,
            new_state=CellState.READY,
            reason="Invalid cell"
        )
        self.assertFalse(result)

    def test_get_all_cell_states(self):
        """Test getting all cell states"""
        states = self.manager.get_all_cell_states()
        self.assertEqual(len(states), 3)
        self.assertIn(1, states)
        self.assertIn(2, states)
        self.assertIn(3, states)


class TestStateDeterminer(unittest.TestCase):
    """Test StateDeterminer logic"""

    def test_determine_cell_state_ready(self):
        """Test cell state determination for normal weight"""
        state = StateDeterminer.determine_cell_state_from_weight(
            weight=2.5,
            last_update_time=datetime.now()
        )
        self.assertEqual(state, CellState.READY)

    def test_determine_cell_state_low_weight(self):
        """Test cell state determination for low weight"""
        state = StateDeterminer.determine_cell_state_from_weight(
            weight=0.3,  # Below 0.5 kg threshold
            last_update_time=datetime.now()
        )
        self.assertEqual(state, CellState.LOW_WEIGHT)

    def test_determine_cell_state_empty(self):
        """Test cell state determination for empty"""
        state = StateDeterminer.determine_cell_state_from_weight(
            weight=0.05,  # Below 0.1 kg threshold
            last_update_time=datetime.now()
        )
        self.assertEqual(state, CellState.EMPTY)

    def test_determine_cell_state_disconnected(self):
        """Test cell state determination for timeout"""
        old_time = datetime.now() - timedelta(seconds=15)  # 15 seconds ago
        state = StateDeterminer.determine_cell_state_from_weight(
            weight=2.5,
            last_update_time=old_time
        )
        self.assertEqual(state, CellState.DISCONNECTED)

    def test_determine_cell_state_error_none_weight(self):
        """Test cell state determination with None weight"""
        state = StateDeterminer.determine_cell_state_from_weight(
            weight=None,
            last_update_time=datetime.now()
        )
        self.assertEqual(state, CellState.ERROR)

    def test_determine_service_state_all_ready(self):
        """Test service state when all cells are ready"""
        cell_states = {
            1: CellState.READY,
            2: CellState.READY,
            3: CellState.LOW_WEIGHT  # Still operational
        }
        state = StateDeterminer.determine_service_state_from_cells(cell_states)
        self.assertEqual(state, ServiceState.READY)

    def test_determine_service_state_any_error(self):
        """Test service state when any cell has error"""
        cell_states = {
            1: CellState.READY,
            2: CellState.ERROR,
            3: CellState.READY
        }
        state = StateDeterminer.determine_service_state_from_cells(cell_states)
        self.assertEqual(state, ServiceState.ERROR)

    def test_determine_service_state_all_disconnected(self):
        """Test service state when all cells disconnected"""
        cell_states = {
            1: CellState.DISCONNECTED,
            2: CellState.DISCONNECTED,
            3: CellState.DISCONNECTED
        }
        state = StateDeterminer.determine_service_state_from_cells(cell_states)
        self.assertEqual(state, ServiceState.DISCONNECTED)

    def test_determine_service_state_initializing(self):
        """Test service state when cells are initializing"""
        cell_states = {
            1: CellState.INITIALIZING,
            2: CellState.UNKNOWN,
            3: CellState.READY
        }
        state = StateDeterminer.determine_service_state_from_cells(cell_states)
        self.assertEqual(state, ServiceState.INITIALIZING)


class TestStateMonitor(unittest.TestCase):
    """Test StateMonitor behavior"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_publisher = Mock(spec=IStatePublisher)
        self.state_manager = StateManager(self.mock_publisher)
        self.monitor = StateMonitor(self.state_manager)

    def test_update_cell_weight_triggers_transition(self):
        """Test updating cell weight triggers state transition"""
        # Initialize cells to READY
        self.state_manager.transition_cell_to(1, CellState.READY, "Init")
        self.mock_publisher.reset_mock()
        # Update with low weight
        self.monitor.update_cell_weight(1, 0.3)
        # Should transition to LOW_WEIGHT
        self.assertEqual(self.state_manager.get_cell_state(1), CellState.LOW_WEIGHT)
        self.mock_publisher.publish_cell_state.assert_called()

    def test_update_cell_weight_no_transition_same_state(self):
        """Test no transition when state doesn't change"""
        # Initialize to READY
        self.state_manager.transition_cell_to(1, CellState.READY, "Init")
        self.mock_publisher.reset_mock()
        # Update with normal weight
        self.monitor.update_cell_weight(1, 2.5)
        # Should stay READY, but publishes update
        self.assertEqual(self.state_manager.get_cell_state(1), CellState.READY)

    def test_mark_initialization_complete(self):
        """Test marking initialization as complete"""
        self.monitor.mark_initialization_complete()
        self.assertEqual(self.state_manager.get_current_state(), ServiceState.READY)

    def test_mark_initialization_failed(self):
        """Test marking initialization as failed"""
        self.monitor.mark_initialization_failed("Config error")
        self.assertEqual(self.state_manager.get_current_state(), ServiceState.ERROR)

    def test_update_overall_service_state(self):
        """Test updating overall service state based on cells"""
        # Set all cells to READY
        self.state_manager.transition_cell_to(1, CellState.READY, "Init")
        self.state_manager.transition_cell_to(2, CellState.READY, "Init")
        self.state_manager.transition_cell_to(3, CellState.READY, "Init")
        # Transition service to READY
        self.state_manager.transition_to(ServiceState.READY, "Init")
        self.mock_publisher.reset_mock()
        # Change one cell to ERROR
        self.state_manager.transition_cell_to(1, CellState.ERROR, "Sensor fail")
        # Update overall state
        self.monitor.update_overall_service_state()
        # Service should transition to ERROR
        self.assertEqual(self.state_manager.get_current_state(), ServiceState.ERROR)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete state management system"""

    def test_full_lifecycle(self):
        """Test complete lifecycle from initialization to operation"""
        # Setup
        mock_broker = Mock()
        publisher = MessageBrokerStatePublisher(mock_broker)
        manager = StateManager(publisher)
        monitor = StateMonitor(manager)
        # 1. Initialize service
        self.assertEqual(manager.get_current_state(), ServiceState.INITIALIZING)
        # 2. Mark initialization complete
        monitor.mark_initialization_complete()
        self.assertEqual(manager.get_current_state(), ServiceState.READY)
        # 3. Update cell weights
        monitor.update_cell_weight(1, 2.5)  # READY
        monitor.update_cell_weight(2, 0.3)  # LOW_WEIGHT
        monitor.update_cell_weight(3, 1.5)  # READY
        # 4. Check cell states
        self.assertEqual(manager.get_cell_state(1), CellState.READY)
        self.assertEqual(manager.get_cell_state(2), CellState.LOW_WEIGHT)
        self.assertEqual(manager.get_cell_state(3), CellState.READY)
        # 5. Service should still be READY (cells are operational)
        monitor.update_overall_service_state()
        self.assertEqual(manager.get_current_state(), ServiceState.READY)
        # 6. Simulate cell failure
        manager.transition_cell_to(1, CellState.ERROR, "Sensor fail")
        monitor.update_overall_service_state()
        # Service should now be ERROR
        self.assertEqual(manager.get_current_state(), ServiceState.ERROR)


if __name__ == '__main__':
    unittest.main()
