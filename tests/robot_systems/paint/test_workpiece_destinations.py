import unittest
from unittest.mock import MagicMock

from src.robot_systems.paint.destinations import AutomaticDryerDestination
from src.robot_systems.paint.processes.paint.destination import (
    PassThroughWorkpieceDestination,
)


class TestWorkpieceDestinations(unittest.TestCase):
    def test_compact_pass_through_has_no_external_handoff(self):
        destination = PassThroughWorkpieceDestination()

        self.assertEqual((True, ""), destination.check_ready_for_release())
        self.assertTrue(destination.on_release_verified())

    def test_automatic_dryer_adapter_delegates_to_coordinator(self):
        coordinator = MagicMock()
        coordinator.wait_until_ready_for_release.return_value = (True, "")
        coordinator.on_workpiece_release_verified.return_value = True
        destination = AutomaticDryerDestination(coordinator)

        self.assertEqual((True, ""), destination.check_ready_for_release())
        self.assertTrue(destination.on_release_verified())

        coordinator.wait_until_ready_for_release.assert_called_once_with()
        coordinator.on_workpiece_release_verified.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
