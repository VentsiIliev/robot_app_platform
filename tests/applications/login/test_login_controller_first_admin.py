"""
Tests for the first-admin flow in LoginController.
"""
import unittest
from unittest.mock import MagicMock

from src.applications.login.model.login_model import LoginModel
from src.applications.login.controller.login_controller import LoginController
from src.engine.auth.i_authenticated_user import IAuthenticatedUser


def _make_user() -> IAuthenticatedUser:
    u = MagicMock(spec=IAuthenticatedUser)
    u.user_id = "1"
    return u


def _make_model(
    user=None,
    first_run=False,
    validation_error=None,
    admin_result=(True, "Created"),
):
    m = MagicMock(spec=LoginModel)
    m.is_first_run.return_value         = first_run
    m.authenticate.return_value         = user
    m.authenticate_qr.return_value      = user
    m.validate_login_input.return_value = validation_error
    m.create_first_admin.return_value   = admin_result
    return m


def _make_view():
    v = MagicMock()
    v.login_submitted       = MagicMock()
    v.qr_login_requested    = MagicMock()
    v.first_admin_submitted = MagicMock()
    return v


class TestFirstAdminFlow(unittest.TestCase):

    def test_load_connects_first_admin_signal(self):
        model = _make_model(first_run=True)
        view  = _make_view()
        ctrl  = LoginController(model, view)
        ctrl.load()
        view.first_admin_submitted.connect.assert_called_once()

    def test_create_admin_success_logs_in(self):
        user  = _make_user()
        model = _make_model(first_run=True, user=user, admin_result=(True, "Created"))
        view  = _make_view()
        ctrl  = LoginController(model, view)
        ctrl.load()
        ctrl._on_first_admin_submitted("1", "Alice", "Smith", "pw")
        model.create_first_admin.assert_called_once_with("1", "Alice", "Smith", "pw")
        view.accept_login.assert_called_once_with(user)

    def test_create_admin_failure_shows_error(self):
        model = _make_model(first_run=True, user=None, admin_result=(False, "ID taken"))
        view  = _make_view()
        ctrl  = LoginController(model, view)
        ctrl.load()
        ctrl._on_first_admin_submitted("1", "Alice", "Smith", "pw")
        view.show_error.assert_called_once_with("ID taken")
        view.accept_login.assert_not_called()


if __name__ == "__main__":
    unittest.main()
