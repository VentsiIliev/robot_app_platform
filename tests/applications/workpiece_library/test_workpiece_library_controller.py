import unittest
from unittest.mock import MagicMock, patch

from src.applications.workpiece_library.controller.workpiece_library_controller import (
    WorkpieceLibraryController,
)
from src.applications.workpiece_library.domain.workpiece_schema import WorkpieceRecord


class TestWorkpieceLibraryController(unittest.TestCase):
    def test_selection_changes_save_without_apply_button(self):
        model = MagicMock()
        view = MagicMock()
        controller = WorkpieceLibraryController(model, view, MagicMock())

        controller._on_selection_applied(())
        controller._on_selection_applied(("stored-2",))
        controller._on_selection_applied(None)

        self.assertEqual(
            [call.args[0] for call in model.save_selection.call_args_list],
            [(), ("stored-2",), None],
        )

    def test_show_selected_combines_with_search(self):
        model = MagicMock()
        model.schema.id_key = "id"
        model.schema.name_key = "name"
        view = MagicMock()
        view.checked_ids.return_value = {"stored-2"}
        controller = WorkpieceLibraryController(model, view, MagicMock())
        controller._all_records = [
            WorkpieceRecord({"id": "stored-1", "name": "First"}),
            WorkpieceRecord({"id": "stored-2", "name": "Second"}),
        ]

        controller._on_show_selected_changed(True)
        self.assertEqual(
            [record.get("id") for record in view.set_records.call_args.args[0]],
            ["stored-2"],
        )
        controller._on_search("First")
        self.assertEqual(view.set_records.call_args.args[0], [])

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
