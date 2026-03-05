import unittest

from src.applications.user_management.domain.user_schema import UserRecord
from src.applications.user_management.service.stub_user_management_service import StubUserManagementService
from src.applications.user_management.domain.default_schema import DEFAULT_USER_SCHEMA


def _record(uid, first="New", last="User", role="Operator", email="new@test.com"):
    return UserRecord({"id": uid, "firstName": first, "lastName": last,
                       "password": "pw", "role": role, "email": email})


class TestStubUserManagementServiceSchema(unittest.TestCase):

    def test_get_schema_returns_default_schema(self):
        svc = StubUserManagementService()
        self.assertIs(svc.get_schema(), DEFAULT_USER_SCHEMA)

    def test_accepts_custom_schema(self):
        from src.applications.user_management.domain.user_schema import UserSchema, FieldDescriptor
        custom = UserSchema(fields=[FieldDescriptor("id", "ID", "int")], id_key="id")
        svc = StubUserManagementService(schema=custom)
        self.assertIs(svc.get_schema(), custom)


class TestStubUserManagementServiceGetAll(unittest.TestCase):

    def test_get_all_users_returns_two_stub_records(self):
        self.assertEqual(len(StubUserManagementService().get_all_users()), 2)

    def test_get_all_users_contains_alice(self):
        ids = {r.get("firstName") for r in StubUserManagementService().get_all_users()}
        self.assertIn("Alice", ids)

    def test_get_all_users_returns_independent_list(self):
        svc = StubUserManagementService()
        lst = svc.get_all_users()
        lst.clear()
        self.assertEqual(len(svc.get_all_users()), 2)


class TestStubUserManagementServiceAdd(unittest.TestCase):

    def setUp(self):
        self._svc = StubUserManagementService()

    def test_add_user_new_id_returns_true(self):
        ok, msg = self._svc.add_user(_record("99"))
        self.assertTrue(ok)
        self.assertIn("99", msg)

    def test_add_user_duplicate_id_returns_false(self):
        ok, msg = self._svc.add_user(_record("1"))
        self.assertFalse(ok)
        self.assertIn("already exists", msg)

    def test_add_user_increases_count(self):
        self._svc.add_user(_record("99"))
        self.assertEqual(len(self._svc.get_all_users()), 3)


class TestStubUserManagementServiceUpdate(unittest.TestCase):

    def setUp(self):
        self._svc = StubUserManagementService()

    def test_update_user_existing_returns_true(self):
        ok, msg = self._svc.update_user(_record("1", first="Updated"))
        self.assertTrue(ok)

    def test_update_user_persists_change(self):
        self._svc.update_user(_record("1", first="Changed"))
        updated = next(r for r in self._svc.get_all_users() if r.get("id") == "1")
        self.assertEqual(updated.get("firstName"), "Changed")

    def test_update_user_not_found_returns_false(self):
        ok, msg = self._svc.update_user(_record("999"))
        self.assertFalse(ok)
        self.assertIn("not found", msg)


class TestStubUserManagementServiceDelete(unittest.TestCase):

    def setUp(self):
        self._svc = StubUserManagementService()

    def test_delete_user_existing_returns_true(self):
        ok, msg = self._svc.delete_user("1")
        self.assertTrue(ok)
        self.assertIn("deleted", msg)

    def test_delete_user_removes_from_list(self):
        self._svc.delete_user("1")
        ids = {r.get("id") for r in self._svc.get_all_users()}
        self.assertNotIn("1", ids)

    def test_delete_user_not_found_returns_false(self):
        ok, msg = self._svc.delete_user("999")
        self.assertFalse(ok)
        self.assertIn("not found", msg)


class TestStubUserManagementServiceQrAndEmail(unittest.TestCase):

    def setUp(self):
        self._svc = StubUserManagementService()

    def test_generate_qr_returns_true(self):
        record = self._svc.get_all_users()[0]
        ok, msg, path = self._svc.generate_qr(record)
        self.assertTrue(ok)

    def test_generate_qr_path_is_none(self):
        record = self._svc.get_all_users()[0]
        ok, msg, path = self._svc.generate_qr(record)
        self.assertIsNone(path)

    def test_send_access_package_returns_true(self):
        record = self._svc.get_all_users()[0]
        ok, msg = self._svc.send_access_package(record, "/tmp/qr.png")
        self.assertTrue(ok)

    def test_send_access_package_message_contains_email(self):
        record = self._svc.get_all_users()[0]
        ok, msg = self._svc.send_access_package(record, "/tmp/qr.png")
        email = record.get("email", "")
        self.assertIn(email, msg)


if __name__ == "__main__":
    unittest.main()

