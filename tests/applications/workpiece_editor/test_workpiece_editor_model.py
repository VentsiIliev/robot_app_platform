import unittest
from unittest.mock import MagicMock

from src.applications.workpiece_editor.service import IWorkpieceEditorService
from src.applications.workpiece_editor.model import WorkpieceEditorModel


def _make_service():
    svc = MagicMock(spec=IWorkpieceEditorService)
    svc.get_contours.return_value        = [[1, 2, 3]]
    svc.save_workpiece.return_value      = (True, "saved")
    svc.execute_workpiece.return_value   = (True, "executed")
    return svc


class TestWorkpieceEditorModelNoOps(unittest.TestCase):

    def test_load_does_not_raise(self):
        WorkpieceEditorModel(_make_service()).load()

    def test_save_no_args_does_not_raise(self):
        WorkpieceEditorModel(_make_service()).save()

    def test_save_with_args_does_not_raise(self):
        WorkpieceEditorModel(_make_service()).save({"form_data": {}})


class TestWorkpieceEditorModelDelegation(unittest.TestCase):

    def setUp(self):
        self._svc   = _make_service()
        self._model = WorkpieceEditorModel(self._svc)

    def test_get_contours_delegates_and_returns(self):
        result = self._model.get_contours()
        self._svc.get_contours.assert_called_once()
        self.assertEqual(result, [[1, 2, 3]])

    def test_save_workpiece_delegates_with_data(self):
        data = {"form_data": {"workpieceId": "1"}}
        ok, msg = self._model.save_workpiece(data)
        self._svc.save_workpiece.assert_called_once_with(data)
        self.assertTrue(ok)

    def test_save_workpiece_returns_service_result(self):
        self._svc.save_workpiece.return_value = (False, "err")
        ok, msg = self._model.save_workpiece({})
        self.assertFalse(ok)
        self.assertEqual(msg, "err")

    def test_execute_workpiece_delegates_with_data(self):
        data = {"form_data": {}}
        ok, msg = self._model.execute_workpiece(data)
        self._svc.execute_workpiece.assert_called_once_with(data)
        self.assertTrue(ok)

    def test_execute_workpiece_returns_service_result(self):
        self._svc.execute_workpiece.return_value = (False, "not ready")
        ok, _ = self._model.execute_workpiece({})
        self.assertFalse(ok)

    def test_set_editing_delegates_with_id(self):
        self._model.set_editing("storage-abc")
        self._svc.set_editing.assert_called_once_with("storage-abc")

    def test_set_editing_delegates_with_none(self):
        self._model.set_editing(None)
        self._svc.set_editing.assert_called_once_with(None)


if __name__ == "__main__":
    unittest.main()

