import unittest
from unittest.mock import MagicMock, patch

from src.applications.workpiece_library.controller.workpiece_library_controller import (
    WorkpieceLibraryController,
)


class TestWorkpieceLibraryController(unittest.TestCase):
    @patch(
        "src.applications.workpiece_library.controller.workpiece_library_controller.ask_yes_no",
        return_value=True,
    )
    def test_delete_refreshes_controller_cache_used_by_search(self, _ask_yes_no):
        model = MagicMock()
        model.delete.return_value = (True, "Deleted")
        model.get_all.return_value = [{"id": "kept", "name": "Kept"}]
        model.schema.id_key = "id"
        model.schema.name_key = "name"
        view = MagicMock()
        controller = WorkpieceLibraryController(model, view, MagicMock())
        controller._all_records = [
            {"id": "deleted", "name": "Deleted"},
            {"id": "kept", "name": "Kept"},
        ]

        controller._on_delete("deleted")
        controller._on_search("")

        self.assertEqual(controller._all_records, [{"id": "kept", "name": "Kept"}])
        self.assertEqual(view.set_records.call_args_list[-1].args[0], [{"id": "kept", "name": "Kept"}])


if __name__ == "__main__":
    unittest.main()
