import os
import sys
import unittest
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication

from src.robot_systems.glue.applications.glue_process_driver.view.glue_process_driver_view import (
    GlueProcessDriverView,
)


class TestGlueProcessDriverView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_get_selected_match_indexes_defaults_to_all_items(self):
        view = GlueProcessDriverView()
        view.set_matched_workpieces(
            [{"workpieceId": "113"}, {"workpieceId": "114"}]
        )

        view._match_list.clearSelection()

        self.assertEqual(view.get_selected_match_indexes(), [0, 1])

    def test_set_process_snapshot_updates_machine_state_summary(self):
        view = GlueProcessDriverView()

        view.set_process_snapshot(
            {
                "process_state": "running",
                "machine": {
                    "last_state": "LOADING_PATH",
                    "current_state": "ISSUING_MOVE_TO_FIRST_POINT",
                    "last_next_state": "MOVING_TO_FIRST_POINT",
                },
            }
        )

        self.assertEqual(
            view._machine_state_summary.text(),
            "Previous: LOADING_PATH | Current: ISSUING_MOVE_TO_FIRST_POINT | Next: MOVING_TO_FIRST_POINT",
        )

    def test_clean_up_stops_controller_if_present(self):
        view = GlueProcessDriverView()
        view._controller = MagicMock()

        view.clean_up()

        view._controller.stop.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
