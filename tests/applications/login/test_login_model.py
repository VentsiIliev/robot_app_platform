"""
Tests for src/applications/login/model/login_model.py

LoginModel is a thin delegation layer over ILoginApplicationService
plus input validation logic.
"""
import unittest
from unittest.mock import MagicMock

from src.applications.login.i_login_application_service import ILoginApplicationService
from src.applications.login.model.login_model import LoginModel
from src.engine.auth.i_authenticated_user import IAuthenticatedUser


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_user() -> IAuthenticatedUser:
    u = MagicMock(spec=IAuthenticatedUser)
    u.user_id = "1"
    return u


def _svc(
    user=None,
    first_run: bool = False,
    admin_result: tuple = (True, "Created"),
) -> ILoginApplicationService:
    svc = MagicMock(spec=ILoginApplicationService)
    svc.authenticate.return_value      = user
    svc.authenticate_qr.return_value   = user
    svc.try_qr_login.return_value      = None
    svc.is_first_run.return_value      = first_run
    svc.create_first_admin.return_value = admin_result
    return svc


# ── Delegation ─────────────────────────────────────────────────────────────────

class TestLoginModelDelegation(unittest.TestCase):

    def test_is_first_run_delegates_to_service(self):
        svc   = _svc(first_run=True)
        model = LoginModel(svc)
        self.assertTrue(model.is_first_run())
        svc.is_first_run.assert_called_once()

    def test_authenticate_delegates_to_service(self):
        user  = _make_user()
        svc   = _svc(user=user)
        model = LoginModel(svc)
        result = model.authenticate("1", "pw")
        svc.authenticate.assert_called_once_with("1", "pw")
        self.assertIs(result, user)

    def test_authenticate_qr_delegates_to_service(self):
        user  = _make_user()
        svc   = _svc(user=user)
        model = LoginModel(svc)
        result = model.authenticate_qr("1:pw")
        svc.authenticate_qr.assert_called_once_with("1:pw")
        self.assertIs(result, user)

    def test_try_qr_login_delegates_to_service(self):
        svc   = _svc()
        svc.try_qr_login.return_value = ("5", "secret")
        model = LoginModel(svc)
        result = model.try_qr_login()
        svc.try_qr_login.assert_called_once()
        self.assertEqual(result, ("5", "secret"))

    def test_move_to_login_pos_delegates_to_service(self):
        svc   = _svc()
        model = LoginModel(svc)
        model.move_to_login_pos()
        svc.move_to_login_pos.assert_called_once()

    def test_create_first_admin_delegates_to_service(self):
        svc   = _svc(admin_result=(True, "Done"))
        model = LoginModel(svc)
        ok, msg = model.create_first_admin("1", "Alice", "Smith", "pw")
        svc.create_first_admin.assert_called_once_with("1", "Alice", "Smith", "pw")
        self.assertTrue(ok)
        self.assertEqual(msg, "Done")


# ── validate_login_input ───────────────────────────────────────────────────────

class TestValidateLoginInput(unittest.TestCase):

    def setUp(self):
        self.model = LoginModel(_svc())

    def test_valid_input_returns_none(self):
        self.assertIsNone(self.model.validate_login_input("42", "secret"))

    def test_empty_user_id_returns_error(self):
        error = self.model.validate_login_input("", "secret")
        self.assertIsNotNone(error)
        self.assertIn("id", error.lower())

    def test_non_numeric_user_id_returns_error(self):
        error = self.model.validate_login_input("abc", "secret")
        self.assertIsNotNone(error)
        self.assertIn("numeric", error.lower())

    def test_empty_password_returns_error(self):
        error = self.model.validate_login_input("42", "")
        self.assertIsNotNone(error)
        self.assertIn("password", error.lower())

    def test_whitespace_user_id_treated_as_empty(self):
        error = self.model.validate_login_input("   ", "pw")
        self.assertIsNotNone(error)

    def test_whitespace_password_treated_as_empty(self):
        error = self.model.validate_login_input("1", "   ")
        self.assertIsNotNone(error)


if __name__ == "__main__":
    unittest.main()
