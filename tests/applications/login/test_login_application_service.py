"""
Tests for:
  src/applications/login/i_login_application_service.py
  src/applications/login/login_application_service.py
  src/applications/login/stub_login_application_service.py

LoginApplicationService delegates auth to IAuthenticationService, manages
first-run detection, admin creation, robot positioning, and QR scanning.
All hardware dependencies are optional and safely no-op when absent.
"""
import unittest
from typing import Optional, Tuple
from unittest.mock import MagicMock, call

from src.applications.user_management.domain.i_user_repository import IUserRepository
from src.applications.user_management.domain.user import Role
from src.applications.user_management.domain.user_schema import UserRecord
from src.engine.auth.i_authenticated_user import IAuthenticatedUser
from src.engine.auth.i_authentication_service import IAuthenticationService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.applications.login.i_login_application_service import ILoginApplicationService
from src.applications.login.i_qr_scanner import IQrScanner
from src.applications.login.login_application_service import LoginApplicationService
from src.applications.login.stub_login_application_service import StubLoginApplicationService


# ── Helpers ────────────────────────────────────────────────────────────────────

def _mock_auth(user: Optional[IAuthenticatedUser] = None) -> IAuthenticationService:
    svc = MagicMock(spec=IAuthenticationService)
    svc.authenticate.return_value = user
    svc.authenticate_qr.return_value = user
    return svc


def _mock_repo(records: list = None) -> IUserRepository:
    repo = MagicMock(spec=IUserRepository)
    repo.get_all.return_value = records or []
    repo.add.return_value = True
    return repo


def _mock_user() -> IAuthenticatedUser:
    u = MagicMock(spec=IAuthenticatedUser)
    u.user_id = "1"
    return u


def _mock_scanner(payload: Optional[str] = None) -> IQrScanner:
    scanner = MagicMock(spec=IQrScanner)
    scanner.scan.return_value = payload
    return scanner


def _make_service(
    auth=None,
    repo=None,
    robot=None,
    scanner=None,
    login_position=None,
) -> LoginApplicationService:
    return LoginApplicationService(
        auth_service   = auth    or _mock_auth(),
        user_repository= repo    or _mock_repo(),
        robot_service  = robot,
        qr_scanner     = scanner,
        login_position = login_position,
    )


# ── Interface conformance ──────────────────────────────────────────────────────

class TestInterface(unittest.TestCase):

    def test_login_application_service_satisfies_interface(self):
        self.assertIsInstance(_make_service(), ILoginApplicationService)

    def test_stub_satisfies_interface(self):
        self.assertIsInstance(StubLoginApplicationService(), ILoginApplicationService)


# ── authenticate ───────────────────────────────────────────────────────────────

class TestAuthenticate(unittest.TestCase):

    def test_delegates_to_auth_service(self):
        user = _mock_user()
        auth = _mock_auth(user)
        svc  = _make_service(auth=auth)
        result = svc.authenticate("1", "pw")
        auth.authenticate.assert_called_once_with("1", "pw")
        self.assertIs(result, user)

    def test_returns_none_when_auth_fails(self):
        svc = _make_service(auth=_mock_auth(None))
        self.assertIsNone(svc.authenticate("1", "wrong"))

    def test_delegates_qr_to_auth_service(self):
        user = _mock_user()
        auth = _mock_auth(user)
        svc  = _make_service(auth=auth)
        result = svc.authenticate_qr("1:pw")
        auth.authenticate_qr.assert_called_once_with("1:pw")
        self.assertIs(result, user)


# ── is_first_run ───────────────────────────────────────────────────────────────

class TestIsFirstRun(unittest.TestCase):

    def test_returns_true_when_repo_is_empty(self):
        svc = _make_service(repo=_mock_repo([]))
        self.assertTrue(svc.is_first_run())

    def test_returns_false_when_repo_has_users(self):
        record = MagicMock(spec=UserRecord)
        svc = _make_service(repo=_mock_repo([record]))
        self.assertFalse(svc.is_first_run())


# ── create_first_admin ─────────────────────────────────────────────────────────

class TestCreateFirstAdmin(unittest.TestCase):

    def test_returns_true_on_success(self):
        repo = _mock_repo()
        svc  = _make_service(repo=repo)
        success, _ = svc.create_first_admin("1", "Alice", "Smith", "pw123")
        self.assertTrue(success)

    def test_calls_repo_add(self):
        repo = _mock_repo()
        svc  = _make_service(repo=repo)
        svc.create_first_admin("1", "Alice", "Smith", "pw123")
        repo.add.assert_called_once()

    def test_stored_record_has_admin_role(self):
        repo = _mock_repo()
        svc  = _make_service(repo=repo)
        svc.create_first_admin("1", "Alice", "Smith", "pw123")
        stored: UserRecord = repo.add.call_args[0][0]
        self.assertEqual(stored.get("role"), Role.ADMIN.value)

    def test_stored_record_has_correct_fields(self):
        repo = _mock_repo()
        svc  = _make_service(repo=repo)
        svc.create_first_admin("42", "Alice", "Smith", "pw123")
        stored: UserRecord = repo.add.call_args[0][0]
        self.assertEqual(str(stored.get("id")), "42")
        self.assertEqual(stored.get("firstName"), "Alice")
        self.assertEqual(stored.get("lastName"),  "Smith")
        self.assertEqual(stored.get("password"),  "pw123")

    def test_returns_false_when_repo_add_fails(self):
        repo = _mock_repo()
        repo.add.return_value = False
        svc  = _make_service(repo=repo)
        success, _ = svc.create_first_admin("1", "Alice", "Smith", "pw123")
        self.assertFalse(success)


# ── move_to_login_pos ──────────────────────────────────────────────────────────

class TestMoveToLoginPos(unittest.TestCase):

    def test_calls_robot_move_ptp_with_configured_position(self):
        robot    = MagicMock(spec=IRobotService)
        position = [100.0, 200.0, 300.0, 0.0, 0.0, 0.0]
        svc      = _make_service(robot=robot, login_position=position)
        svc.move_to_login_pos()
        robot.move_ptp.assert_called_once()
        args = robot.move_ptp.call_args[0]
        self.assertEqual(args[0], position)

    def test_does_nothing_when_no_robot_service(self):
        svc = _make_service(robot=None)
        svc.move_to_login_pos()   # must not raise

    def test_does_nothing_when_no_position_configured(self):
        robot = MagicMock(spec=IRobotService)
        svc   = _make_service(robot=robot, login_position=None)
        svc.move_to_login_pos()
        robot.move_ptp.assert_not_called()


# ── try_qr_login ──────────────────────────────────────────────────────────────

class TestTryQrLogin(unittest.TestCase):

    def test_returns_none_when_no_scanner(self):
        svc = _make_service(scanner=None)
        self.assertIsNone(svc.try_qr_login())

    def test_returns_none_when_scanner_finds_nothing(self):
        svc = _make_service(scanner=_mock_scanner(None))
        self.assertIsNone(svc.try_qr_login())

    def test_returns_user_id_and_password_on_valid_payload(self):
        svc = _make_service(scanner=_mock_scanner("5:secret"))
        result = svc.try_qr_login()
        self.assertEqual(result, ("5", "secret"))

    def test_returns_none_on_malformed_payload(self):
        svc = _make_service(scanner=_mock_scanner("no-colon"))
        self.assertIsNone(svc.try_qr_login())

    def test_password_may_contain_colon(self):
        """Split on first colon only — password colons are preserved."""
        svc = _make_service(scanner=_mock_scanner("1:pass:word"))
        result = svc.try_qr_login()
        self.assertEqual(result, ("1", "pass:word"))


# ── StubLoginApplicationService ───────────────────────────────────────────────

class TestStubLoginApplicationService(unittest.TestCase):

    def setUp(self):
        self.stub = StubLoginApplicationService()

    def test_authenticate_always_returns_stub_user(self):
        result = self.stub.authenticate("any", "any")
        self.assertIsInstance(result, IAuthenticatedUser)

    def test_authenticate_qr_always_returns_stub_user(self):
        result = self.stub.authenticate_qr("any")
        self.assertIsInstance(result, IAuthenticatedUser)

    def test_is_first_run_returns_false_by_default(self):
        self.assertFalse(self.stub.is_first_run())

    def test_create_first_admin_returns_success(self):
        success, _ = self.stub.create_first_admin("1", "A", "B", "pw")
        self.assertTrue(success)

    def test_move_to_login_pos_does_not_raise(self):
        self.stub.move_to_login_pos()  # must not raise

    def test_try_qr_login_returns_none_by_default(self):
        self.assertIsNone(self.stub.try_qr_login())


if __name__ == "__main__":
    unittest.main()
