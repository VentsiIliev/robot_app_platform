import sys
import unittest
from unittest.mock import MagicMock

from src.applications.workpiece_editor.editor_core.config.workpiece_form_schema import WorkpieceFormSchema
from src.applications.workpiece_editor.view.workpiece_editor_view import WorkpieceEditorView


def _make_view():
    return WorkpieceEditorView(schema=WorkpieceFormSchema(fields=[]), segment_config=MagicMock())


class TestWorkpieceEditorViewConstruction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_can_be_constructed_without_raising(self):
        view = _make_view()
        self.assertIsNotNone(view)

    def test_editor_attribute_exists_after_construction(self):
        view = _make_view()
        self.assertTrue(hasattr(view, "_editor"))


class TestWorkpieceEditorViewSignals(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self._view = _make_view()

    def test_on_save_cb_emits_save_requested(self):
        received = []
        self._view.save_requested.connect(lambda d: received.append(d))
        self._view._on_save_cb({"key": "value"})
        self.assertEqual(received, [{"key": "value"}])

    def test_on_execute_cb_emits_execute_requested(self):
        received = []
        self._view.execute_requested.connect(lambda d: received.append(d))
        self._view._on_execute_cb({"op": "run"})
        self.assertEqual(received, [{"op": "run"}])

    def test_on_camera_feed_cb_does_not_raise(self):
        self._view._on_camera_feed_cb()


class TestWorkpieceEditorViewCaptureHandler(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self._view = _make_view()

    def test_capture_cb_returns_empty_without_handler(self):
        self.assertEqual(self._view._on_capture_cb(), [])

    def test_set_capture_handler_is_called_on_capture(self):
        handler = MagicMock(return_value=[1, 2, 3])
        self._view.set_capture_handler(handler)
        result = self._view._on_capture_cb()
        handler.assert_called_once()
        self.assertEqual(result, [1, 2, 3])

    def test_handler_returning_none_yields_empty_list(self):
        self._view.set_capture_handler(lambda: None)
        self.assertEqual(self._view._on_capture_cb(), [])

    def test_handler_exception_returns_empty_list(self):
        self._view.set_capture_handler(MagicMock(side_effect=RuntimeError("cam error")))
        self.assertEqual(self._view._on_capture_cb(), [])


class TestWorkpieceEditorViewPublicApi(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self._view = _make_view()
        self._view._editor = None  # guarantee no editor for most tests

    # ── update_camera_feed ────────────────────────────────────────────

    def test_update_camera_feed_none_image_is_noop(self):
        self._view.update_camera_feed(None)  # no raise

    def test_update_camera_feed_no_editor_is_noop(self):
        self._view.update_camera_feed(MagicMock())  # no raise

    def test_update_camera_feed_calls_set_image_when_editor_present(self):
        mock_editor = MagicMock()
        self._view._editor = mock_editor
        image = MagicMock()
        self._view.update_camera_feed(image)
        mock_editor.set_image.assert_called_once_with(image)

    def test_update_camera_feed_editor_without_set_image_is_noop(self):
        self._view._editor = MagicMock(spec=[])  # no attributes
        self._view.update_camera_feed(MagicMock())  # no raise

    # ── update_contours ───────────────────────────────────────────────

    def test_update_contours_no_editor_is_noop(self):
        self._view.update_contours([1, 2, 3])  # no raise

    def test_update_contours_calls_set_contours_on_inner_editor(self):
        mock_editor = MagicMock()
        self._view._editor = mock_editor
        self._view.update_contours([1, 2, 3])
        inner = mock_editor.contourEditor.editor_with_rulers.editor
        inner.set_contours.assert_called_once_with([1, 2, 3])

    def test_update_contours_attribute_error_is_silenced(self):
        mock_editor = MagicMock()
        mock_editor.contourEditor.editor_with_rulers.editor.set_contours.side_effect = AttributeError
        self._view._editor = mock_editor
        self._view.update_contours([1, 2, 3])  # no raise

    # ── clean_up ──────────────────────────────────────────────────────

    def test_clean_up_with_no_editor_is_noop(self):
        self._view.clean_up()
        self.assertIsNone(self._view._editor)

    def test_clean_up_with_mock_editor_sets_editor_to_none(self):
        mock_editor = MagicMock()
        mock_editor.contourEditor.editor_with_rulers.editor._event_bus = None
        self._view._editor = mock_editor
        self._view.clean_up()
        self.assertIsNone(self._view._editor)

    def test_clean_up_disconnects_event_bus_signals(self):
        mock_editor = MagicMock()
        bus = MagicMock()
        mock_editor.contourEditor.editor_with_rulers.editor._event_bus = bus
        self._view._editor = mock_editor
        self._view.clean_up()
        # each signal's disconnect() should have been attempted
        self.assertTrue(bus.segment_visibility_changed.disconnect.called
                        or bus.points_changed.disconnect.called)


if __name__ == "__main__":
    unittest.main()

