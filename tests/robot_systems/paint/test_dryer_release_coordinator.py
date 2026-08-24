import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.robot_systems.paint.processes.paint.dryer_release_coordinator import (
    DryerReleaseCoordinator,
)


class TestDryerReleaseCoordinator(unittest.TestCase):
    def test_sequence_waits_for_next_position_before_eject_and_eject_done(self) -> None:
        events = []
        dryer = MagicMock()
        dryer.next_position.side_effect = lambda: events.append("next_position") or True
        dryer.eject.side_effect = lambda: events.append("eject") or True
        dryer.get_state.side_effect = [
            SimpleNamespace(is_healthy=True, next_position_done=True, eject_done=False),
            SimpleNamespace(is_healthy=True, next_position_done=True, eject_done=True),
        ]
        coordinator = DryerReleaseCoordinator(
            dryer,
            status_timeout_s=0.0,
            status_poll_interval_s=0.0,
        )

        coordinator._run_sequence()
        coordinator.shutdown()

        self.assertEqual(["next_position", "eject"], events)
        self.assertEqual(2, dryer.get_state.call_count)

    def test_release_callback_queues_without_waiting_for_dryer(self) -> None:
        entered = threading.Event()
        release = threading.Event()
        dryer = MagicMock()

        def blocking_next_position() -> bool:
            entered.set()
            release.wait(timeout=1.0)
            return False

        dryer.next_position.side_effect = blocking_next_position
        coordinator = DryerReleaseCoordinator(dryer)

        queued = coordinator.on_workpiece_release_verified()

        self.assertTrue(queued)
        self.assertTrue(entered.wait(timeout=1.0))
        release.set()
        coordinator.shutdown()

    def test_failed_next_position_does_not_send_eject(self) -> None:
        dryer = MagicMock()
        dryer.next_position.return_value = False
        coordinator = DryerReleaseCoordinator(dryer)

        coordinator._run_sequence()
        coordinator.shutdown()

        dryer.eject.assert_not_called()
        dryer.get_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
