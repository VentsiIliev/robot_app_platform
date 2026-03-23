import sys
import unittest
from unittest.mock import MagicMock, patch

from src.applications.user_management.domain.i_user_repository import IUserRepository
from src.applications.user_management.domain.default_schema import DEFAULT_USER_SCHEMA
from src.applications.user_management.domain.user_schema import UserRecord
from src.applications.user_management.service.user_management_application_service import UserManagementApplicationService

_SVC_MOD = "src.applications.user_management.service.user_management_application_service"


def _make_repo(schema=None):
    repo = MagicMock(spec=IUserRepository)
    repo.get_schema.return_value = schema or DEFAULT_USER_SCHEMA
    repo.get_all.return_value = []
    return repo


def _record(uid, email=""):
    return UserRecord({"id": uid, "firstName": "A", "lastName": "B",
                       "password": "pw", "role": "Admin", "email": email})


class TestAppServiceSchema(unittest.TestCase):

    def test_get_schema_delegates_to_repo(self):
        repo = _make_repo()
        svc = UserManagementApplicationService(repo)
        result = svc.get_schema()
        repo.get_schema.assert_called_once()
        self.assertIs(result, DEFAULT_USER_SCHEMA)


class TestAppServiceGetAll(unittest.TestCase):

    def test_get_all_users_delegates_to_repo(self):
        repo = _make_repo()
        repo.get_all.return_value = [_record("1")]
        svc = UserManagementApplicationService(repo)
        result = svc.get_all_users()
        repo.get_all.assert_called_once()
        self.assertEqual(len(result), 1)


class TestAppServiceAddUser(unittest.TestCase):

    def test_add_user_success(self):
        repo = _make_repo()
        repo.add.return_value = True
        svc = UserManagementApplicationService(repo)
        ok, msg = svc.add_user(_record("5"))
        self.assertTrue(ok)
        self.assertIn("5", msg)

    def test_add_user_duplicate_returns_false(self):
        repo = _make_repo()
        repo.add.return_value = False
        svc = UserManagementApplicationService(repo)
        ok, msg = svc.add_user(_record("5"))
        self.assertFalse(ok)
        self.assertIn("already exists", msg)

    def test_add_user_exception_returns_false(self):
        repo = _make_repo()
        repo.add.side_effect = RuntimeError("disk full")
        svc = UserManagementApplicationService(repo)
        ok, msg = svc.add_user(_record("5"))
        self.assertFalse(ok)
        self.assertIn("disk full", msg)


class TestAppServiceUpdateUser(unittest.TestCase):

    def test_update_user_success(self):
        repo = _make_repo()
        repo.update.return_value = True
        svc = UserManagementApplicationService(repo)
        ok, msg = svc.update_user(_record("1"))
        self.assertTrue(ok)
        self.assertIn("1", msg)

    def test_update_user_not_found_returns_false(self):
        repo = _make_repo()
        repo.update.return_value = False
        svc = UserManagementApplicationService(repo)
        ok, msg = svc.update_user(_record("1"))
        self.assertFalse(ok)
        self.assertIn("not found", msg)

    def test_update_user_exception_returns_false(self):
        repo = _make_repo()
        repo.update.side_effect = IOError("read error")
        svc = UserManagementApplicationService(repo)
        ok, msg = svc.update_user(_record("1"))
        self.assertFalse(ok)
        self.assertIn("read error", msg)


class TestAppServiceDeleteUser(unittest.TestCase):

    def test_delete_user_success(self):
        repo = _make_repo()
        repo.delete.return_value = True
        svc = UserManagementApplicationService(repo)
        ok, msg = svc.delete_user("1")
        self.assertTrue(ok)

    def test_delete_user_not_found_returns_false(self):
        repo = _make_repo()
        repo.delete.return_value = False
        svc = UserManagementApplicationService(repo)
        ok, msg = svc.delete_user("1")
        self.assertFalse(ok)
        self.assertIn("not found", msg)

    def test_delete_user_exception_returns_false(self):
        repo = _make_repo()
        repo.delete.side_effect = RuntimeError("boom")
        svc = UserManagementApplicationService(repo)
        ok, msg = svc.delete_user("1")
        self.assertFalse(ok)
        self.assertIn("boom", msg)


class TestAppServiceGenerateQr(unittest.TestCase):

    def test_generate_qr_success_with_mocked_qrcode(self):
        repo = _make_repo()
        svc = UserManagementApplicationService(repo)
        record = _record("7")
        mock_qr = MagicMock()
        mock_qrcode_mod = MagicMock()
        mock_qrcode_mod.make.return_value = mock_qr
        with patch.dict(sys.modules, {"qrcode": mock_qrcode_mod}):
            ok, msg, path = svc.generate_qr(record)
        self.assertTrue(ok)
        self.assertEqual(msg, "QR generated")
        self.assertIsNotNone(path)
        self.assertIn("qr_user_7", path)

    def test_generate_qr_exception_returns_false(self):
        repo = _make_repo()
        svc = UserManagementApplicationService(repo)
        # Force ImportError by removing qrcode from sys.modules
        with patch.dict(sys.modules, {"qrcode": None}):
            ok, msg, path = svc.generate_qr(_record("1"))
        self.assertFalse(ok)
        self.assertIsNone(path)


class TestAppServiceSendAccessPackage(unittest.TestCase):

    def test_no_email_returns_false(self):
        svc = UserManagementApplicationService(_make_repo())
        ok, msg = svc.send_access_package(_record("1", email=""), "/tmp/qr.png")
        self.assertFalse(ok)
        self.assertIn("no email", msg)

    def test_email_sender_missing_returns_false(self):
        svc = UserManagementApplicationService(_make_repo())
        # _email_sender.y_pixels doesn't exist — ImportError is caught
        ok, msg = svc.send_access_package(_record("1", email="user@test.com"), "/tmp/qr.png")
        self.assertFalse(ok)

    def test_email_sender_success_with_mock(self):
        svc = UserManagementApplicationService(_make_repo())
        mock_sender = MagicMock()
        mock_sender.send_user_access_package.return_value = (True, "Sent!")
        module_key = "src.applications.user_management.service._email_sender"
        with patch.dict(sys.modules, {module_key: mock_sender}):
            ok, msg = svc.send_access_package(_record("1", email="u@t.com"), "/tmp/qr.png")
        self.assertTrue(ok)
        self.assertEqual(msg, "Sent!")


if __name__ == "__main__":
    unittest.main()

