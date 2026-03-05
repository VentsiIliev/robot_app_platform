import os
import tempfile
import unittest

from src.applications.user_management.domain.csv_user_repository import CsvUserRepository
from src.applications.user_management.domain.default_schema import DEFAULT_USER_SCHEMA
from src.applications.user_management.domain.user_schema import UserRecord


def _record(uid, first="Alice", last="Test", role="Admin", email="a@b.com"):
    return UserRecord({"id": uid, "firstName": first, "lastName": last,
                       "password": "pw", "role": role, "email": email})


class TestCsvUserRepositoryInit(unittest.TestCase):

    def test_creates_file_if_not_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "users.csv")
            CsvUserRepository(path, DEFAULT_USER_SCHEMA)
            self.assertTrue(os.path.exists(path))

    def test_get_all_returns_empty_on_fresh_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = CsvUserRepository(os.path.join(tmp, "users.csv"), DEFAULT_USER_SCHEMA)
            self.assertEqual(repo.get_all(), [])

    def test_get_schema_returns_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = CsvUserRepository(os.path.join(tmp, "users.csv"), DEFAULT_USER_SCHEMA)
            self.assertIs(repo.get_schema(), DEFAULT_USER_SCHEMA)


class TestCsvUserRepositoryAdd(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._repo = CsvUserRepository(os.path.join(self._tmp.name, "users.csv"), DEFAULT_USER_SCHEMA)

    def tearDown(self):
        self._tmp.cleanup()

    def test_add_returns_true_for_new_record(self):
        self.assertTrue(self._repo.add(_record("1")))

    def test_add_persists_record(self):
        self._repo.add(_record("1", first="Bob"))
        records = self._repo.get_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].get("firstName"), "Bob")

    def test_add_returns_false_for_duplicate_id(self):
        self._repo.add(_record("1"))
        self.assertFalse(self._repo.add(_record("1")))

    def test_add_multiple_records(self):
        self._repo.add(_record("1"))
        self._repo.add(_record("2"))
        self.assertEqual(len(self._repo.get_all()), 2)


class TestCsvUserRepositoryGetById(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._repo = CsvUserRepository(os.path.join(self._tmp.name, "users.csv"), DEFAULT_USER_SCHEMA)
        self._repo.add(_record("10", first="Alice"))
        self._repo.add(_record("20", first="Bob"))

    def tearDown(self):
        self._tmp.cleanup()

    def test_get_by_id_returns_correct_record(self):
        r = self._repo.get_by_id("10")
        self.assertIsNotNone(r)
        self.assertEqual(r.get("firstName"), "Alice")

    def test_get_by_id_returns_none_for_missing(self):
        self.assertIsNone(self._repo.get_by_id("999"))


class TestCsvUserRepositoryUpdate(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._repo = CsvUserRepository(os.path.join(self._tmp.name, "users.csv"), DEFAULT_USER_SCHEMA)
        self._repo.add(_record("1", first="Alice"))

    def tearDown(self):
        self._tmp.cleanup()

    def test_update_existing_returns_true(self):
        self.assertTrue(self._repo.update(_record("1", first="Updated")))

    def test_update_existing_persists_change(self):
        self._repo.update(_record("1", first="Updated"))
        self.assertEqual(self._repo.get_by_id("1").get("firstName"), "Updated")

    def test_update_nonexistent_returns_false(self):
        self.assertFalse(self._repo.update(_record("999", first="X")))

    def test_update_does_not_change_count(self):
        self._repo.update(_record("1", first="Updated"))
        self.assertEqual(len(self._repo.get_all()), 1)


class TestCsvUserRepositoryDelete(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._repo = CsvUserRepository(os.path.join(self._tmp.name, "users.csv"), DEFAULT_USER_SCHEMA)
        self._repo.add(_record("1"))
        self._repo.add(_record("2"))

    def tearDown(self):
        self._tmp.cleanup()

    def test_delete_existing_returns_true(self):
        self.assertTrue(self._repo.delete("1"))

    def test_delete_removes_record(self):
        self._repo.delete("1")
        self.assertIsNone(self._repo.get_by_id("1"))

    def test_delete_leaves_other_records_intact(self):
        self._repo.delete("1")
        self.assertEqual(len(self._repo.get_all()), 1)

    def test_delete_nonexistent_returns_false(self):
        self.assertFalse(self._repo.delete("999"))


class TestCsvUserRepositoryExists(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._repo = CsvUserRepository(os.path.join(self._tmp.name, "users.csv"), DEFAULT_USER_SCHEMA)
        self._repo.add(_record("1"))

    def tearDown(self):
        self._tmp.cleanup()

    def test_exists_true_for_added_record(self):
        self.assertTrue(self._repo.exists("1"))

    def test_exists_false_for_missing(self):
        self.assertFalse(self._repo.exists("999"))

    def test_exists_false_after_delete(self):
        self._repo.delete("1")
        self.assertFalse(self._repo.exists("1"))


if __name__ == "__main__":
    unittest.main()

