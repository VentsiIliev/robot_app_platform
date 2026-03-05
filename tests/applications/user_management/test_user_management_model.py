import unittest
from unittest.mock import MagicMock

from src.applications.user_management.domain.default_schema import DEFAULT_USER_SCHEMA
from src.applications.user_management.domain.user_schema import UserRecord
from src.applications.user_management.model.user_management_model import UserManagementModel
from src.applications.user_management.service.i_user_management_service import IUserManagementService


def _make_service(records=None):
    svc = MagicMock(spec=IUserManagementService)
    svc.get_schema.return_value = DEFAULT_USER_SCHEMA
    svc.get_all_users.return_value = records or []
    svc.add_user.return_value    = (True, "added")
    svc.update_user.return_value = (True, "updated")
    svc.delete_user.return_value = (True, "deleted")
    svc.generate_qr.return_value = (True, "QR generated", "/tmp/qr.png")
    svc.send_access_package.return_value = (True, "Sent")
    return svc


def _record(uid):
    return UserRecord({"id": uid, "firstName": "A", "lastName": "B",
                       "password": "pw", "role": "Admin", "email": "a@b.com"})


class TestUserManagementModelInit(unittest.TestCase):

    def test_schema_is_loaded_from_service(self):
        model = UserManagementModel(_make_service())
        self.assertIs(model.schema, DEFAULT_USER_SCHEMA)

    def test_get_users_empty_before_load(self):
        model = UserManagementModel(_make_service())
        self.assertEqual(model.get_users(), [])


class TestUserManagementModelLoad(unittest.TestCase):

    def test_load_calls_get_all_users(self):
        svc = _make_service(records=[_record("1")])
        model = UserManagementModel(svc)
        model.load()
        svc.get_all_users.assert_called_once()

    def test_load_returns_records(self):
        records = [_record("1"), _record("2")]
        model = UserManagementModel(_make_service(records=records))
        result = model.load()
        self.assertEqual(len(result), 2)

    def test_load_updates_internal_cache(self):
        records = [_record("1")]
        model = UserManagementModel(_make_service(records=records))
        model.load()
        self.assertEqual(len(model.get_users()), 1)

    def test_save_is_noop(self):
        UserManagementModel(_make_service()).save()


class TestUserManagementModelAddUser(unittest.TestCase):

    def test_add_user_success_refreshes_records(self):
        fresh = [_record("1"), _record("99")]
        svc = _make_service()
        svc.get_all_users.return_value = fresh
        model = UserManagementModel(svc)
        ok, msg = model.add_user(_record("99"))
        self.assertTrue(ok)
        self.assertEqual(len(model.get_users()), 2)

    def test_add_user_failure_does_not_refresh(self):
        svc = _make_service()
        svc.add_user.return_value = (False, "exists")
        model = UserManagementModel(svc)
        model.add_user(_record("1"))
        svc.get_all_users.assert_not_called()

    def test_add_user_returns_service_result(self):
        svc = _make_service()
        svc.add_user.return_value = (False, "dup")
        model = UserManagementModel(svc)
        ok, msg = model.add_user(_record("1"))
        self.assertFalse(ok)
        self.assertEqual(msg, "dup")


class TestUserManagementModelUpdateUser(unittest.TestCase):

    def test_update_user_success_refreshes_records(self):
        fresh = [_record("1")]
        svc = _make_service(records=[_record("1")])
        svc.get_all_users.side_effect = [[_record("1")], fresh]
        model = UserManagementModel(svc)
        model.load()
        ok, _ = model.update_user(_record("1"))
        self.assertTrue(ok)

    def test_update_user_failure_does_not_refresh(self):
        svc = _make_service()
        svc.update_user.return_value = (False, "not found")
        model = UserManagementModel(svc)
        model.update_user(_record("1"))
        svc.get_all_users.assert_not_called()


class TestUserManagementModelDeleteUser(unittest.TestCase):

    def test_delete_user_success_refreshes_records(self):
        svc = _make_service(records=[_record("1")])
        svc.get_all_users.side_effect = [[_record("1")], []]
        model = UserManagementModel(svc)
        model.load()
        ok, _ = model.delete_user("1")
        self.assertTrue(ok)
        self.assertEqual(len(model.get_users()), 0)

    def test_delete_user_failure_does_not_refresh(self):
        svc = _make_service()
        svc.delete_user.return_value = (False, "not found")
        model = UserManagementModel(svc)
        model.delete_user("99")
        svc.get_all_users.assert_not_called()


class TestUserManagementModelQrAndEmail(unittest.TestCase):

    def test_generate_qr_delegates_to_service(self):
        svc = _make_service()
        model = UserManagementModel(svc)
        record = _record("1")
        ok, msg, path = model.generate_qr(record)
        svc.generate_qr.assert_called_once_with(record)
        self.assertTrue(ok)
        self.assertEqual(path, "/tmp/qr.png")

    def test_send_access_package_delegates_to_service(self):
        svc = _make_service()
        model = UserManagementModel(svc)
        record = _record("1")
        ok, msg = model.send_access_package(record, "/tmp/qr.png")
        svc.send_access_package.assert_called_once_with(record, "/tmp/qr.png")
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()

