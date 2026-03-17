"""
Tests for src/applications/user_management/controller/permissions_controller.py

Covers the pure controller logic: load populates the view, checkbox signals
are forwarded to the model, and the deferral notice is shown on load.
Qt is fully mocked — no display required.
"""
import unittest
from unittest.mock import MagicMock, call, patch

from src.applications.user_management.controller.permissions_controller import PermissionsController
from src.applications.user_management.model.permissions_model import PermissionsModel


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_model(
    app_ids: list = None,
    perms:   dict = None,
) -> PermissionsModel:
    model = MagicMock(spec=PermissionsModel)
    model.get_known_app_ids.return_value = list(app_ids or [])
    model.get_role_values.return_value   = ["Admin", "Operator", "Viewer"]
    model.get_permissions.return_value   = dict(perms or {})
    return model


def _make_view():
    view = MagicMock()
    return view


# ── Load ───────────────────────────────────────────────────────────────────────

class TestPermissionsControllerLoad(unittest.TestCase):

    def test_load_calls_set_permissions_on_view(self):
        model = _make_model(
            app_ids=["dashboard"],
            perms={"dashboard": ["Admin", "Operator"]},
        )
        view       = _make_view()
        controller = PermissionsController(model, view)
        controller.load()
        view.set_permissions.assert_called_once_with(
            app_ids    = ["dashboard"],
            role_values= ["Admin", "Operator", "Viewer"],
            permissions= {"dashboard": ["Admin", "Operator"]},
        )

    def test_load_shows_deferral_notice(self):
        model      = _make_model()
        view       = _make_view()
        controller = PermissionsController(model, view)
        controller.load()
        view.set_notice.assert_called_once()
        notice_text = view.set_notice.call_args[0][0]
        self.assertIn("next login", notice_text.lower())


# ── Checkbox signal ────────────────────────────────────────────────────────────

class TestPermissionsControllerCheckbox(unittest.TestCase):

    def test_permission_toggled_delegates_to_model(self):
        model      = _make_model()
        view       = _make_view()
        controller = PermissionsController(model, view)
        controller.load()

        # Simulate the view emitting permission_toggled(app_id, role_value, allowed)
        toggle_slot = view.permission_toggled.connect.call_args[0][0]
        toggle_slot("dashboard", "Operator", True)

        model.set_permission.assert_called_once_with("dashboard", "Operator", True)

    def test_permission_toggled_refreshes_view(self):
        model = _make_model(
            app_ids=["dashboard"],
            perms={"dashboard": ["Admin", "Operator"]},
        )
        view       = _make_view()
        controller = PermissionsController(model, view)
        controller.load()

        toggle_slot = view.permission_toggled.connect.call_args[0][0]
        toggle_slot("dashboard", "Viewer", True)

        # set_permissions should be called twice: once on load, once after toggle
        self.assertEqual(view.set_permissions.call_count, 2)


if __name__ == "__main__":
    unittest.main()
