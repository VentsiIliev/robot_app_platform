import threading
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.robot_systems.paint.processes.paint.dryer_release_coordinator import (
    DryerReleaseCoordinator,
)


class TestDryerReleaseCoordinator(unittest.TestCase):
    def test_disabled_dryer_skips_commands_and_readiness_validation(self) -> None:
        dryer = MagicMock()
        dryer.is_enabled.return_value = False
        coordinator = DryerReleaseCoordinator(dryer)

        self.assertTrue(coordinator.on_workpiece_release_verified())
        self.assertEqual((True, ""), coordinator.wait_until_ready_for_release())
        coordinator.shutdown()

        dryer.next_position.assert_not_called()
        dryer.eject.assert_not_called()
        dryer.get_state.assert_not_called()

    def test_sequence_waits_for_next_position_before_eject_and_eject_done(self) -> None:
        events = []
        dryer = MagicMock()
        dryer.next_position.side_effect = lambda: events.append("next_position") or True
        dryer.eject.side_effect = lambda: events.append("eject") or True
        dryer.get_state.side_effect = [
            SimpleNamespace(is_healthy=True, next_position_done=True),
            SimpleNamespace(is_healthy=True, next_position_moving=True, next_position_done=False),
            SimpleNamespace(is_healthy=True, next_position_moving=False, next_position_done=True),
            SimpleNamespace(is_healthy=True, next_position_done=True, eject_done=False),
            SimpleNamespace(is_healthy=True, next_position_done=True, ejecting=True, eject_done=False),
            SimpleNamespace(is_healthy=True, next_position_done=True, ejecting=False, eject_done=True),
        ]
        coordinator = DryerReleaseCoordinator(
            dryer,
            status_timeout_s=0.1,
            status_poll_interval_s=0.0,
        )

        coordinator._run_sequence()
        self.assertEqual((True, ""), coordinator.wait_until_ready_for_release())
        coordinator.shutdown()

        self.assertEqual(["next_position", "eject"], events)
        self.assertEqual(6, dryer.get_state.call_count)

    def test_eject_completion_accepts_return_to_ready_after_physical_activity(self) -> None:
        dryer = MagicMock()
        dryer.next_position.return_value = True
        dryer.eject.return_value = True
        dryer.get_state.side_effect = [
            SimpleNamespace(is_healthy=True, next_position_done=True),
            SimpleNamespace(is_healthy=True, next_position_moving=True, next_position_done=False),
            SimpleNamespace(is_healthy=True, next_position_moving=False, next_position_done=True),
            SimpleNamespace(is_healthy=True, is_ready=True, ejecting=False, eject_done=False),
            SimpleNamespace(is_healthy=True, is_ready=False, ejecting=True, eject_done=False, raw_status=0x08),
            SimpleNamespace(is_healthy=True, is_ready=True, ejecting=False, eject_done=True, raw_status=0x11),
        ]
        coordinator = DryerReleaseCoordinator(dryer, status_timeout_s=0.1, status_poll_interval_s=0.0)

        coordinator._run_sequence()

        self.assertEqual((True, ""), coordinator.wait_until_ready_for_release())
        coordinator.shutdown()

    def test_stale_next_position_done_does_not_trigger_eject(self) -> None:
        dryer = MagicMock()
        stale_done = SimpleNamespace(
            is_healthy=True,
            next_position_moving=False,
            next_position_done=True,
        )
        dryer.get_state.return_value = stale_done
        dryer.next_position.return_value = True
        coordinator = DryerReleaseCoordinator(
            dryer,
            status_timeout_s=0.0,
            status_poll_interval_s=0.0,
        )

        coordinator._run_sequence()
        ready, reason = coordinator.wait_until_ready_for_release()
        coordinator.shutdown()

        self.assertFalse(ready)
        self.assertEqual("NEXT_POSITION completion was not confirmed", reason)
        dryer.next_position.assert_called_once_with()
        dryer.eject.assert_not_called()

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
        dryer.get_state.return_value = SimpleNamespace(
            is_healthy=True,
            next_position_done=True,
        )
        coordinator = DryerReleaseCoordinator(dryer)

        coordinator._run_sequence()
        coordinator.shutdown()

        dryer.eject.assert_not_called()
        dryer.get_state.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
