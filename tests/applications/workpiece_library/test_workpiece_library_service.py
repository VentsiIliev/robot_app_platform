"""
Tests for workpiece_library service layer.

Covers:
- StubWorkpieceLibraryService — interface compliance + in-memory CRUD behaviour
"""
import unittest

from src.applications.workpiece_library.service.i_workpiece_library_service import IWorkpieceLibraryService
from src.applications.workpiece_library.service.stub_workpiece_library_service import StubWorkpieceLibraryService
from src.applications.workpiece_library.domain.workpiece_schema import WorkpieceRecord


# ══════════════════════════════════════════════════════════════════════════════
# StubWorkpieceLibraryService — interface
# ══════════════════════════════════════════════════════════════════════════════

class TestStubWorkpieceLibraryServiceInterface(unittest.TestCase):

    def test_implements_interface(self):
        self.assertIsInstance(StubWorkpieceLibraryService(), IWorkpieceLibraryService)


# ══════════════════════════════════════════════════════════════════════════════
# list_all
# ══════════════════════════════════════════════════════════════════════════════

class TestWorkpieceLibraryServiceListAll(unittest.TestCase):

    def setUp(self):
        self._svc = StubWorkpieceLibraryService()

    def test_list_all_returns_list(self):
        result = self._svc.list_all()
        self.assertIsInstance(result, list)

    def test_list_all_returns_workpiece_records(self):
        records = self._svc.list_all()
        for r in records:
            self.assertIsInstance(r, WorkpieceRecord)

    def test_list_all_returns_stub_records(self):
        records = self._svc.list_all()
        self.assertGreater(len(records), 0)

    def test_list_all_returns_copy(self):
        a = self._svc.list_all()
        b = self._svc.list_all()
        self.assertIsNot(a, b)


# ══════════════════════════════════════════════════════════════════════════════
# delete
# ══════════════════════════════════════════════════════════════════════════════

class TestWorkpieceLibraryServiceDelete(unittest.TestCase):

    def setUp(self):
        self._svc = StubWorkpieceLibraryService()

    def _first_id(self):
        schema = self._svc.get_schema()
        return self._svc.list_all()[0].get_id(schema.id_key)

    def test_delete_existing_returns_true(self):
        ok, msg = self._svc.delete(self._first_id())
        self.assertTrue(ok)
        self.assertIsInstance(msg, str)

    def test_delete_existing_removes_record(self):
        before = len(self._svc.list_all())
        self._svc.delete(self._first_id())
        self.assertEqual(len(self._svc.list_all()), before - 1)

    def test_delete_not_found_returns_false(self):
        ok, msg = self._svc.delete("NO-SUCH-ID")
        self.assertFalse(ok)
        self.assertIsInstance(msg, str)

    def test_delete_not_found_does_not_change_list(self):
        before = len(self._svc.list_all())
        self._svc.delete("NO-SUCH-ID")
        self.assertEqual(len(self._svc.list_all()), before)


# ══════════════════════════════════════════════════════════════════════════════
# update
# ══════════════════════════════════════════════════════════════════════════════

class TestWorkpieceLibraryServiceUpdate(unittest.TestCase):

    def setUp(self):
        self._svc = StubWorkpieceLibraryService()

    def _first_id(self):
        schema = self._svc.get_schema()
        return self._svc.list_all()[0].get_id(schema.id_key)

    def test_update_existing_returns_true(self):
        ok, msg = self._svc.update(self._first_id(), {"name": "Updated"})
        self.assertTrue(ok)

    def test_update_not_found_returns_false(self):
        ok, msg = self._svc.update("NO-SUCH-ID", {"name": "X"})
        self.assertFalse(ok)


# ══════════════════════════════════════════════════════════════════════════════
# get_thumbnail
# ══════════════════════════════════════════════════════════════════════════════

class TestWorkpieceLibraryServiceGetThumbnail(unittest.TestCase):

    def test_get_thumbnail_returns_none_for_stub(self):
        svc = StubWorkpieceLibraryService()
        self.assertIsNone(svc.get_thumbnail("WP-001"))

    def test_get_thumbnail_unknown_id_returns_none(self):
        svc = StubWorkpieceLibraryService()
        self.assertIsNone(svc.get_thumbnail("DOES-NOT-EXIST"))


# ══════════════════════════════════════════════════════════════════════════════
# load_raw
# ══════════════════════════════════════════════════════════════════════════════

class TestWorkpieceLibraryServiceLoadRaw(unittest.TestCase):

    def test_load_raw_returns_none_for_stub(self):
        svc = StubWorkpieceLibraryService()
        self.assertIsNone(svc.load_raw("WP-001"))

    def test_load_raw_unknown_id_returns_none(self):
        svc = StubWorkpieceLibraryService()
        self.assertIsNone(svc.load_raw("DOES-NOT-EXIST"))


if __name__ == "__main__":
    unittest.main()
