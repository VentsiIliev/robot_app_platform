"""
Tests for src/applications/login/controller/login_controller.py
"""
import unittest
from unittest.mock import MagicMock

from src.applications.login.model.login_model import LoginModel
from src.applications.login.controller.login_controller import LoginController
from src.engine.auth.i_authenticated_user import IAuthenticatedUser


# ── Helpers ──────────────────────────────────────────────────────────────────

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
    m.is_first_run.return_value         = first_run
    m.authenticate.return_value         = user
    m.try_qr_login.return_value         = qr_result
    m.validate_login_input.return_value = validation_error
    m.create_first_admin.return_value   = admin_result
    return m


def _make_view():
    v = MagicMock()
    v.login_submitted       = MagicMock()
    v.qr_scan_requested     = MagicMock()
    v.qr_tab_activated      = MagicMock()
    v.first_admin_submitted = MagicMock()
    return v


# ── load() ───────────────────────────────────────────────────────────────────

class TestLoginControllerLoad(unittest.TestCase):

    def test_load_connects_login_signal(self):
        ctrl = LoginController(_make_model(), _make_view())
        view = ctrl._view
        ctrl.load()
        view.login_submitted.connect.assert_called_once()

    def test_load_connects_qr_scan_signal(self):
        ctrl = LoginController(_make_model(), _make_view())
        view = ctrl._view
        ctrl.load()
        view.qr_scan_requested.connect.assert_called_once()

    def test_load_connects_qr_tab_activated_signal(self):
        ctrl = LoginController(_make_model(), _make_view())
        view = ctrl._view
        ctrl.load()
        view.qr_tab_activated.connect.assert_called_once()

    def test_load_connects_first_admin_signal(self):
        ctrl = LoginController(_make_model(), _make_view())
        view = ctrl._view
        ctrl.load()
        view.first_admin_submitted.connect.assert_called_once()

    def test_load_shows_first_run_when_first_run(self):
        ctrl = LoginController(_make_model(first_run=True), _make_view())
        ctrl.load()
        ctrl._view.show_first_run.assert_called_once()

    def test_load_shows_login_when_not_first_run(self):
        ctrl = LoginController(_make_model(first_run=False), _make_view())
        ctrl.load()
        ctrl._view.show_login.assert_called_once()


# ── _on_login_submitted ───────────────────────────────────────────────────────

class TestOnLoginSubmitted(unittest.TestCase):

    def test_validation_error_shown_without_authenticate(self):
        model = _make_model(validation_error="User id is required.")
        ctrl  = LoginController(model, _make_view())
        ctrl._on_login_submitted("", "pw")
        ctrl._view.show_error.assert_called_once_with("User id is required.")
        model.authenticate.assert_not_called()

    def test_failed_auth_shows_error(self):
        model = _make_model(user=None, validation_error=None)
        ctrl  = LoginController(model, _make_view())
        ctrl._on_login_submitted("1", "bad")
        ctrl._view.show_error.assert_called_once()

    def test_successful_auth_calls_accept_login(self):
        user  = _make_user()
        model = _make_model(user=user, validation_error=None)
        ctrl  = LoginController(model, _make_view())
        ctrl._on_login_submitted("1", "pw")
        ctrl._view.accept_login.assert_called_once_with(user)


# ── _on_qr_tab_activated ─────────────────────────────────────────────────────

class TestOnQrTabActivated(unittest.TestCase):

    def test_calls_move_to_login_pos(self):
        model = _make_model()
        ctrl  = LoginController(model, _make_view())
        ctrl._on_qr_tab_activated()
        model.move_to_login_pos.assert_called_once()


# ── _on_qr_scan_requested ────────────────────────────────────────────────────

class TestOnQrScanRequested(unittest.TestCase):

    def test_no_result_does_nothing(self):
        model = _make_model(qr_result=None)
        ctrl  = LoginController(model, _make_view())
        ctrl._on_qr_scan_requested()
        ctrl._view.accept_login.assert_not_called()
        ctrl._view.show_error.assert_not_called()

    def test_qr_result_authenticates_and_accepts(self):
        user  = _make_user()
        model = _make_model(user=user, qr_result=("1", "pw"))
        ctrl  = LoginController(model, _make_view())
        ctrl._on_qr_scan_requested()
        model.authenticate.assert_called_once_with("1", "pw")
        ctrl._view.accept_login.assert_called_once_with(user)

    def test_qr_result_bad_credentials_shows_error(self):
        model = _make_model(user=None, qr_result=("1", "bad"))
        ctrl  = LoginController(model, _make_view())
        ctrl._on_qr_scan_requested()
        ctrl._view.show_error.assert_called_once()
        ctrl._view.accept_login.assert_not_called()


# ── _on_first_admin_submitted ─────────────────────────────────────────────────

class TestOnFirstAdminSubmitted(unittest.TestCase):

    def test_create_success_logs_in(self):
        user  = _make_user()
        model = _make_model(user=user, admin_result=(True, "Created"))
        ctrl  = LoginController(model, _make_view())
        ctrl._on_first_admin_submitted("1", "Alice", "Smith", "pw")
        model.create_first_admin.assert_called_once_with("1", "Alice", "Smith", "pw")
        ctrl._view.accept_login.assert_called_once_with(user)

    def test_create_failure_shows_error(self):
        model = _make_model(user=None, admin_result=(False, "ID taken"))
        ctrl  = LoginController(model, _make_view())
        ctrl._on_first_admin_submitted("1", "Alice", "Smith", "pw")
        ctrl._view.show_error.assert_called_once_with("ID taken")
        ctrl._view.accept_login.assert_not_called()


if __name__ == "__main__":
    unittest.main()
