import sys
import unittest
from unittest.mock import MagicMock

from src.applications.workpiece_editor.controller.workpiece_editor_controller import WorkpieceEditorController
from src.applications.workpiece_editor.editor_core.config.workpiece_form_schema import WorkpieceFormSchema
from src.applications.workpiece_editor.service.i_workpiece_editor_service import IWorkpieceEditorService
from src.applications.workpiece_editor.view.workpiece_editor_view import WorkpieceEditorView
from src.applications.workpiece_editor.workpiece_editor_factory import WorkpieceEditorFactory
from src.engine.core.i_messaging_service import IMessagingService


def _make_service():
    svc = MagicMock(spec=IWorkpieceEditorService)
    svc.get_form_schema.return_value    = WorkpieceFormSchema(fields=[])
    svc.get_segment_config.return_value = MagicMock()
    return svc


def _make_factory():
    messaging = MagicMock(spec=IMessagingService)
    return WorkpieceEditorFactory(messaging=messaging), messaging


class TestWorkpieceEditorFactory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_create_view_raises_not_implemented(self):
        factory, _ = _make_factory()
        with self.assertRaises(NotImplementedError):
            factory._create_view()

    def test_build_returns_workpiece_editor_view(self):
        factory, _ = _make_factory()
        result = factory.build(_make_service())
        self.assertIsInstance(result, WorkpieceEditorView)

    def test_build_attaches_controller_to_view(self):
        factory, _ = _make_factory()
        view = factory.build(_make_service())
        self.assertIsInstance(view._controller, WorkpieceEditorController)

    def test_build_calls_get_form_schema(self):
        factory, _ = _make_factory()
        svc = _make_service()
        factory.build(svc)
        svc.get_form_schema.assert_called_once()

    def test_build_calls_get_segment_config(self):
        factory, _ = _make_factory()
        svc = _make_service()
        factory.build(svc)
        svc.get_segment_config.assert_called_once()

    def test_controller_uses_messaging_from_factory_init(self):
        factory, messaging = _make_factory()
        view = factory.build(_make_service())
        self.assertIs(view._controller._broker, messaging)

    def test_two_builds_produce_independent_views(self):
        factory, _ = _make_factory()
        v1 = factory.build(_make_service())
        v2 = factory.build(_make_service())
        self.assertIsNot(v1, v2)
        self.assertIsNot(v1._controller, v2._controller)


if __name__ == "__main__":
    unittest.main()

