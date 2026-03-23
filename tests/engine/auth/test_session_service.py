"""
Tests for src/engine/auth/user_session.y_pixels

Covers login, logout, current_user/current_role properties, is_authenticated,
and thread safety under concurrent access.
"""
import threading
import unittest
from enum import Enum
from unittest.mock import MagicMock

from src.engine.auth.i_authenticated_user import IAuthenticatedUser
from src.engine.auth.i_session_service import ISessionService
from src.engine.auth.user_session import UserSession


class _Role(Enum):
    ADMIN    = "Admin"
    OPERATOR = "Operator"


def _make_user(role: _Role = _Role.ADMIN) -> IAuthenticatedUser:
    u = MagicMock(spec=IAuthenticatedUser)
    u.user_id = "1"
    u.role    = role
    return u


class TestISessionService(unittest.TestCase):
    """Verify UserSession satisfies ISessionService."""

    def test_is_instance_of_i_session_service(self):
        self.assertIsInstance(UserSession(), ISessionService)


class TestUserSessionLogin(unittest.TestCase):

    def setUp(self):
        self.session = UserSession()

    def test_not_authenticated_initially(self):
        self.assertFalse(self.session.is_authenticated())

    def test_current_user_is_none_initially(self):
        self.assertIsNone(self.session.current_user)

    def test_current_role_is_none_initially(self):
        self.assertIsNone(self.session.current_role)

    def test_login_sets_authenticated(self):
        self.session.login(_make_user())
        self.assertTrue(self.session.is_authenticated())

    def test_login_sets_current_user(self):
        user = _make_user()
        self.session.login(user)
        self.assertIs(self.session.current_user, user)

    def test_login_sets_current_role(self):
        user = _make_user(_Role.OPERATOR)
        self.session.login(user)
        self.assertEqual(self.session.current_role, _Role.OPERATOR)


class TestUserSessionLogout(unittest.TestCase):

    def setUp(self):
        self.session = UserSession()
        self.session.login(_make_user())

    def test_logout_clears_authenticated(self):
        self.session.logout()
        self.assertFalse(self.session.is_authenticated())

    def test_logout_clears_current_user(self):
        self.session.logout()
        self.assertIsNone(self.session.current_user)

    def test_logout_clears_current_role(self):
        self.session.logout()
        self.assertIsNone(self.session.current_role)

    def test_logout_when_already_logged_out_is_safe(self):
        self.session.logout()
        self.session.logout()   # should not raise
        self.assertFalse(self.session.is_authenticated())


class TestUserSessionThreadSafety(unittest.TestCase):

    def test_concurrent_login_logout_does_not_raise(self):
        session = UserSession()
        errors  = []

        def login_logout():
            try:
                for _ in range(50):
                    session.login(_make_user())
                    _ = session.current_user
                    _ = session.current_role
                    _ = session.is_authenticated()
                    session.logout()
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=login_logout) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
