import copy
import unittest
from unittest.mock import MagicMock

from src.applications.workpiece_editor.controller.workpiece_editor_controller import (
    WorkpieceEditorController,
)


class TestProcessContourPreview(unittest.TestCase):

    def test_displays_processed_pixels_without_mutating_editor_data(self):
        controller = WorkpieceEditorController.__new__(WorkpieceEditorController)
        controller._logger = MagicMock()
        controller._captured_pickup_point = None

        raw_editor_data = {"contour": [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]}
        original = copy.deepcopy(raw_editor_data)
        workpiece_manager = MagicMock()
        workpiece_manager.export_editor_data.return_value = raw_editor_data

        inner = MagicMock()
        inner.workpiece_manager = workpiece_manager
        editor_frame = MagicMock()
        editor_frame.contourEditor.editor_with_rulers.editor = inner
        editor_frame.additional_data_form.get_data.return_value = {}
        controller._view = MagicMock()
        controller._view._editor = editor_frame

        controller._model = MagicMock()
        controller._model.execute_workpiece.return_value = (True, "prepared")
        controller._model.get_last_projection_source_paths.return_value = [
            [[10.0, 20.0], [11.0, 21.0], [12.0, 22.0]]
        ]
        controller._show_projection_source_plot = MagicMock()

        controller._on_process_contour()

        self.assertEqual(raw_editor_data, original)
        controller._model.execute_workpiece.assert_called_once()
        controller._show_projection_source_plot.assert_called_once_with(
            controller._model.get_last_projection_source_paths.return_value
        )
        editor_frame.set_verification_contours.assert_not_called()


if __name__ == "__main__":
    unittest.main()
