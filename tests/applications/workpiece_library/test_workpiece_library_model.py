"""
Tests for src/applications/workpiece_library/model/workpiece_library_model.py
"""
import unittest
from unittest.mock import MagicMock

from src.applications.workpiece_library.model.workpiece_library_model import WorkpieceLibraryModel
from src.applications.workpiece_library.service.i_workpiece_library_service import IWorkpieceLibraryService
from src.applications.workpiece_library.domain.workpiece_schema import WorkpieceRecord, WorkpieceSchema, WorkpieceFieldDescriptor


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_schema():
    return WorkpieceSchema(
        id_key="workpieceId", name_key="name",
        fields=[WorkpieceFieldDescriptor(key="workpieceId", label="ID")],
    )


def _record(wp_id: str):
    return WorkpieceRecord({"workpieceId": wp_id, "name": f"WP {wp_id}"})


def _make_service(records=None):
    svc = MagicMock(spec=IWorkpieceLibraryService)
    recs = records if records is not None else [_record("A"), _record("B")]
    svc.list_all.return_value   = list(recs)
    svc.get_schema.return_value = _make_schema()
    svc.delete.return_value     = (True, "Deleted")
    svc.update.return_value     = (True, "Updated")
    svc.get_thumbnail.return_value = None
    svc.load_raw.return_value   = None
    return svc


# ══════════════════════════════════════════════════════════════════════════════
# Delegation
# ══════════════════════════════════════════════════════════════════════════════

class TestWorkpieceLibraryModelDelegation(unittest.TestCase):

    def test_load_delegates_to_service_list_all(self):
        svc   = _make_service()
        model = WorkpieceLibraryModel(svc)
        model.load()
        svc.list_all.assert_called()

    def test_load_returns_records(self):
        recs  = [_record("X"), _record("Y")]
        svc   = _make_service(recs)
        model = WorkpieceLibraryModel(svc)
        result = model.load()
        self.assertEqual(len(result), 2)

    def test_get_all_returns_cached_records_after_load(self):
        recs  = [_record("X")]
        svc   = _make_service(recs)
        model = WorkpieceLibraryModel(svc)
        model.load()
        self.assertEqual(len(model.get_all()), 1)

    def test_delete_delegates_to_service(self):
        svc   = _make_service()
        model = WorkpieceLibraryModel(svc)
        model.load()
        ok, msg = model.delete("A")
        svc.delete.assert_called_once_with("A")
        self.assertTrue(ok)

    def test_delete_success_refreshes_records(self):
        svc   = _make_service()
        model = WorkpieceLibraryModel(svc)
        model.load()
        svc.list_all.reset_mock()
        model.delete("A")
        svc.list_all.assert_called()

    def test_delete_failure_does_not_refresh(self):
        svc   = _make_service()
        svc.delete.return_value = (False, "not found")
        model = WorkpieceLibraryModel(svc)
        model.load()
        svc.list_all.reset_mock()
        model.delete("NO-SUCH")
        svc.list_all.assert_not_called()

    def test_update_delegates_to_service(self):
        svc   = _make_service()
        model = WorkpieceLibraryModel(svc)
        model.load()
        ok, _ = model.update("A", {"name": "New"})
        svc.update.assert_called_once_with("A", {"name": "New"})
        self.assertTrue(ok)

    def test_get_thumbnail_delegates_to_service(self):
        svc   = _make_service()
        model = WorkpieceLibraryModel(svc)
        model.get_thumbnail("A")
        svc.get_thumbnail.assert_called_once_with("A")

    def test_load_raw_delegates_to_service(self):
        svc   = _make_service()
        model = WorkpieceLibraryModel(svc)
        model.load_raw("A")
        svc.load_raw.assert_called_once_with("A")

    def test_schema_provided_at_construction(self):
        svc   = _make_service()
        model = WorkpieceLibraryModel(svc)
        self.assertIsNotNone(model.schema)

    def test_save_is_no_op(self):
        model = WorkpieceLibraryModel(_make_service())
        model.save()   # must not raise


if __name__ == "__main__":
    unittest.main()
