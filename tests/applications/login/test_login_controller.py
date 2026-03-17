"""
Tests for src/applications/login/controller/login_controller.py

LoginController wires LoginModel ↔ LoginView.
All Qt signals are replaced with MagicMock to avoid a QApplication.
"""
import unittest
from unittest.mock import MagicMock, call

from src.applications.login.model.login_model import LoginModel
from src.engine.auth.i_authenticated_user import IAuthenticatedUser


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_user() -> IAuthenticatedUser:
    u = MagicMock(spec=IAuthenticatedUser)
    u.user_id = "1"
    return u


def _make_model(
    user=None,
    first_run: bool = False,
    validation_error: str = None,
    admin_result=(True, "Created"),
    qr_result=None,
) -> LoginModel:
    m = MagicMock(spec=LoginModel)
    m.is_first_run.return_value        = first_run
    m.authenticate.return_value        = user
    m.authenticate_qr.return_value     = user
    m.try_qr_login.return_value        = qr_result
    m.validate_login_input.return_value = validation_error
    m.create_first_admin.return_value  = admin_result
    return m


def _make_view():
    """Build a view mock whose signals are plain MagicMocks (no Qt needed)."""
    v = MagicMock()
    v.login_submitted    = MagicMock()
    v.qr_login_requested = MagicMock()
    v.first_admin_submitted = MagicMock()
    return v


# ── Import controller (fails until file exists) ──────────────────────────────

from src.applications.login.controller.login_controller import LoginController


# ── load() ───────────────────────────────────────────────────────────────────

class TestLoginControllerLoad(unittest.TestCase):

    def test_load_connects_signals(self):
        model = _make_model()
        view  = _make_view()
        ctrl  = LoginController(model, view)
        ctrl.load()
        view.login_submitted.connect.assert_called_once()
        view.qr_login_requested.connect.assert_called_once()

    def test_load_shows_first_run_when_first_run(self):
        model = _make_model(first_run=True)
        view  = _make_view()
        ctrl  = LoginController(model, view)
        ctrl.load()
        view.show_first_run.assert_called_once()

    def test_load_shows_login_when_not_first_run(self):
        model = _make_model(first_run=False)
        view  = _make_view()
        ctrl  = LoginController(model, view)
        ctrl.load()
        view.show_login.assert_called_once()

    def test_load_calls_move_to_login_pos(self):
        model = _make_model()
        view  = _make_view()
        ctrl  = LoginController(model, view)
        ctrl.load()
        model.move_to_login_pos.assert_called_once()


# ── _on_login_submitted ───────────────────────────────────────────────────────

class TestLoginControllerOnLogin(unittest.TestCase):

    def test_validation_error_shown_without_authenticate(self):
        model = _make_model(validation_error="User id is required.")
        view  = _make_view()
        ctrl  = LoginController(model, view)
        ctrl._on_login_submitted("", "pw")
        view.show_error.assert_called_once_with("User id is required.")
        model.authenticate.assert_not_called()

    def test_failed_auth_shows_error(self):
        model = _make_model(user=None, validation_error=None)
        view  = _make_view()
        ctrl  = LoginController(model, view)
        ctrl._on_login_submitted("1", "bad")
        view.show_error.assert_called_once()
        model.authenticate.assert_called_once_with("1", "bad")

    def test_successful_auth_emits_logged_in(self):
        user  = _make_user()
        model = _make_model(user=user, validation_error=None)
        view  = _make_view()
        ctrl  = LoginController(model, view)
        ctrl._on_login_submitted("1", "pw")
        view.accept_login.assert_called_once_with(user)


# ── _on_qr_login_requested ───────────────────────────────────────────────────

class TestLoginControllerOnQr(unittest.TestCase):

    def test_failed_qr_shows_error(self):
        model = _make_model(user=None, validation_error=None)
        view  = _make_view()
        ctrl  = LoginController(model, view)
        ctrl._on_qr_login_requested("bad_payload")
        view.show_error.assert_called_once()

    def test_successful_qr_emits_logged_in(self):
        user  = _make_user()
        model = _make_model(user=user, validation_error=None)
        view  = _make_view()
        ctrl  = LoginController(model, view)
        ctrl._on_qr_login_requested("1:pw")
        view.accept_login.assert_called_once_with(user)


if __name__ == "__main__":
    unittest.main()
