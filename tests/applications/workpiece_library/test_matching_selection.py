import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from src.applications.workpiece_library.domain.workpiece_schema import (
    WorkpieceFieldDescriptor,
    WorkpieceRecord,
    WorkpieceSchema,
)
from src.applications.workpiece_library.view.workpiece_library_view import WorkpieceLibraryView
from src.applications.workpiece_library.workpiece_thumbnail import generate_thumbnail_bytes
from src.applications.workpiece_library.model.workpiece_library_model import WorkpieceLibraryModel
from src.applications.workpiece_library.controller.workpiece_library_controller import WorkpieceLibraryController
from src.applications.workpiece_library.service.stub_workpiece_library_service import StubWorkpieceLibraryService
from src.robot_systems.paint.domain.workpieces.matching_selection import PaintMatchingSelection


class TestMatchingSelectionView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_checked_workpieces_survive_search_and_save_automatically(self):
        schema = WorkpieceSchema(
            id_key="id", name_key="name",
            fields=[WorkpieceFieldDescriptor(key="name", label="Name")],
        )
        view = WorkpieceLibraryView(schema, selection_enabled=True, show_thumbnails=True)
        first = WorkpieceRecord({"id": "stored-1", "name": "First"})
        second = WorkpieceRecord({"id": "stored-2", "name": "Second"})
        applied = []
        selected_filter = []
        view.selection_requested.connect(applied.append)
        view.show_selected_changed.connect(selected_filter.append)
        view.set_available_ids(["stored-1", "stored-2"])
        view.set_records([first, second])
        view.set_selection(None)
        thumbnail = generate_thumbnail_bytes({"contour": [[0, 0], [10, 0], [10, 10]]})
        view.set_table_thumbnail("stored-1", thumbnail)

        self.assertFalse(hasattr(view, "_btn_apply_selection"))
        self.assertEqual(view.checked_ids(), {"stored-1", "stored-2"})
        self.assertFalse(view._table.item(0, 1).icon().isNull())
        view._btn_clear_selection.click()
        self.assertEqual(applied, [()])
        view._table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        self.assertEqual(applied[-1], ("stored-1",))
        view.set_records([second])
        view._table.item(0, 0).setCheckState(Qt.CheckState.Checked)
        self.assertIsNone(applied[-1])
        view.set_records([first, second])

        self.assertEqual(view._table.item(0, 0).checkState(), Qt.CheckState.Checked)
        self.assertEqual(view._table.item(1, 0).checkState(), Qt.CheckState.Checked)
        view._show_selected.click()
        self.assertEqual(selected_filter, [True])
        view._btn_match_all.click()
        self.assertIsNone(applied[-1])

    def test_clear_checkbox_and_select_all_persist_without_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "selection.json")
            selection = PaintMatchingSelection(path)
            service = StubWorkpieceLibraryService()
            model = WorkpieceLibraryModel(service, selection)
            view = WorkpieceLibraryView(model.schema, selection_enabled=True)
            controller = WorkpieceLibraryController(model, view, MagicMock())
            controller.load()

            view._btn_clear_selection.click()
            self.assertEqual(PaintMatchingSelection(path).get_selected_ids(), ())
            view._table.item(0, 0).setCheckState(Qt.CheckState.Checked)
            self.assertEqual(PaintMatchingSelection(path).get_selected_ids(), ("WP-001",))
            view._btn_match_all.click()
            self.assertIsNone(PaintMatchingSelection(path).get_selected_ids())


if __name__ == "__main__":
    unittest.main()
