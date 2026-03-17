"""
Tests for:
  src/robot_systems/glue/domain/auth/authenticated_user.py
  src/robot_systems/glue/domain/auth/authentication_service.py

AuthenticatedUser wraps the domain User and satisfies IAuthenticatedUser.
AuthenticationService verifies credentials against IUserRepository.
"""
import unittest
from unittest.mock import MagicMock

from src.applications.user_management.domain.user import Role, User
from src.applications.user_management.domain.user_schema import UserRecord
from src.applications.user_management.domain.i_user_repository import IUserRepository
from src.engine.auth.i_authenticated_user import IAuthenticatedUser
from src.engine.auth.i_authentication_service import IAuthenticationService
from src.robot_systems.glue.domain.auth.authenticated_user import AuthenticatedUser
from src.robot_systems.glue.domain.auth.authentication_service import AuthenticationService


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_user(user_id: int = 1, password: str = "pass123", role: Role = Role.OPERATOR) -> User:
    return User(id=user_id, firstName="Jane", lastName="Doe", password=password, role=role)


def _make_record(user: User) -> UserRecord:
    return UserRecord.from_dict(user.to_dict())


def _repo_with(user: User | None) -> IUserRepository:
    repo = MagicMock(spec=IUserRepository)
    repo.get_by_id.return_value = _make_record(user) if user else None
    return repo


# ── AuthenticatedUser ──────────────────────────────────────────────────────────

class TestAuthenticatedUser(unittest.TestCase):

    def setUp(self):
        self.user = _make_user(user_id=42, role=Role.ADMIN)
        self.auth_user = AuthenticatedUser(self.user)

    def test_satisfies_i_authenticated_user(self):
        self.assertIsInstance(self.auth_user, IAuthenticatedUser)

    def test_user_id_returns_string_of_int_id(self):
        self.assertEqual(self.auth_user.user_id, "42")

    def test_role_returns_the_users_role_enum(self):
        self.assertEqual(self.auth_user.role, Role.ADMIN)

    def test_role_value_matches(self):
        self.assertEqual(self.auth_user.role.value, "Admin")

    def test_underlying_user_is_accessible(self):
        self.assertIs(self.auth_user.underlying_user, self.user)


# ── AuthenticationService — interface conformance ─────────────────────────────

class TestAuthenticationServiceInterface(unittest.TestCase):

    def test_satisfies_i_authentication_service(self):
        svc = AuthenticationService(_repo_with(None))
        self.assertIsInstance(svc, IAuthenticationService)


# ── authenticate ───────────────────────────────────────────────────────────────

class TestAuthenticate(unittest.TestCase):

    def test_returns_authenticated_user_on_correct_credentials(self):
        user = _make_user(user_id=1, password="secret")
        svc  = AuthenticationService(_repo_with(user))
        result = svc.authenticate("1", "secret")
        self.assertIsInstance(result, IAuthenticatedUser)
        self.assertEqual(result.user_id, "1")

    def test_returns_none_on_wrong_password(self):
        user = _make_user(password="correct")
        svc  = AuthenticationService(_repo_with(user))
        self.assertIsNone(svc.authenticate("1", "wrong"))

    def test_returns_none_when_user_not_found(self):
        svc = AuthenticationService(_repo_with(None))
        self.assertIsNone(svc.authenticate("99", "any"))

    def test_role_on_returned_user_matches_stored_role(self):
        user = _make_user(role=Role.ADMIN, password="pw")
        svc  = AuthenticationService(_repo_with(user))
        result = svc.authenticate("1", "pw")
        self.assertEqual(result.role, Role.ADMIN)

    def test_looks_up_user_by_provided_user_id(self):
        repo = _repo_with(_make_user(user_id=7, password="pw"))
        svc  = AuthenticationService(repo)
        svc.authenticate("7", "pw")
        repo.get_by_id.assert_called_once_with("7")


# ── authenticate_qr ────────────────────────────────────────────────────────────

class TestAuthenticateQr(unittest.TestCase):

    def test_valid_payload_returns_authenticated_user(self):
        user = _make_user(user_id=1, password="pw")
        svc  = AuthenticationService(_repo_with(user))
        result = svc.authenticate_qr("1:pw")
        self.assertIsInstance(result, IAuthenticatedUser)

    def test_wrong_password_in_payload_returns_none(self):
        user = _make_user(password="correct")
        svc  = AuthenticationService(_repo_with(user))
        self.assertIsNone(svc.authenticate_qr("1:wrong"))

    def test_malformed_payload_returns_none(self):
        svc = AuthenticationService(_repo_with(None))
        self.assertIsNone(svc.authenticate_qr("no-colon-separator"))

    def test_empty_payload_returns_none(self):
        svc = AuthenticationService(_repo_with(None))
        self.assertIsNone(svc.authenticate_qr(""))


if __name__ == "__main__":
    unittest.main()
