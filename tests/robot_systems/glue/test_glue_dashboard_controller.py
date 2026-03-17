import unittest
from unittest.mock import MagicMock

from src.robot_systems.glue.applications.dashboard.controller.glue_dashboard_controller import (
    GlueDashboardController,
)


class TestGlueDashboardController(unittest.TestCase):
    def test_on_start_runs_model_start_in_background_helper(self):
        model = MagicMock()
        view = MagicMock()
        broker = MagicMock()
        controller = GlueDashboardController(model, view, broker)
        controller._active = True
        controller._run_blocking = MagicMock()

        controller._on_start()

        controller._run_blocking.assert_called_once_with(model.start)
        model.start.assert_not_called()

    def test_on_start_does_nothing_when_inactive(self):
        model = MagicMock()
        view = MagicMock()
        broker = MagicMock()
        controller = GlueDashboardController(model, view, broker)
        controller._active = False
        controller._run_blocking = MagicMock()

        controller._on_start()

        controller._run_blocking.assert_not_called()


if __name__ == "__main__":
    unittest.main()
