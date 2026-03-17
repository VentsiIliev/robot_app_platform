"""
Tests for src/applications/user_management/model/permissions_model.py

PermissionsModel wraps IPermissionsAdminService and provides the pure logic
for the App Permissions tab: reading the current permissions, toggling a
single role for an app, and persisting immediately via the service.
"""
import unittest
from unittest.mock import MagicMock, call

from src.engine.auth.i_permissions_admin_service import IPermissionsAdminService
from src.applications.user_management.model.permissions_model import PermissionsModel


# ── Helpers ────────────────────────────────────────────────────────────────────

def _svc(perms: dict = None) -> IPermissionsAdminService:
    svc = MagicMock(spec=IPermissionsAdminService)
    svc.get_all_permissions.return_value = dict(perms or {})
    return svc


# ── Construction ───────────────────────────────────────────────────────────────

class TestPermissionsModelInit(unittest.TestCase):

    def test_get_known_app_ids_returns_provided_list(self):
        model = PermissionsModel(_svc(), known_app_ids=["dashboard", "settings"])
        self.assertEqual(model.get_known_app_ids(), ["dashboard", "settings"])

    def test_get_role_values_returns_all_three_roles(self):
        model = PermissionsModel(_svc(), known_app_ids=[])
        self.assertEqual(model.get_role_values(), ["Admin", "Operator", "Viewer"])


# ── get_permissions ────────────────────────────────────────────────────────────

class TestGetPermissions(unittest.TestCase):

    def test_returns_stored_roles_for_known_app(self):
        svc   = _svc({"dashboard": ["Admin", "Operator"]})
        model = PermissionsModel(svc, ["dashboard"])
        self.assertEqual(model.get_permissions()["dashboard"], ["Admin", "Operator"])

    def test_defaults_to_admin_for_unlisted_known_app(self):
        svc   = _svc({})
        model = PermissionsModel(svc, ["new_app"])
        self.assertEqual(model.get_permissions()["new_app"], ["Admin"])

    def test_excludes_stale_apps_not_in_known_list(self):
        svc   = _svc({"stale_app": ["Admin"], "dashboard": ["Admin"]})
        model = PermissionsModel(svc, ["dashboard"])
        self.assertNotIn("stale_app", model.get_permissions())

    def test_all_known_apps_present_in_result(self):
        svc   = _svc({"app_a": ["Admin"]})
        model = PermissionsModel(svc, ["app_a", "app_b"])
        perms = model.get_permissions()
        self.assertIn("app_a", perms)
        self.assertIn("app_b", perms)


# ── set_permission ─────────────────────────────────────────────────────────────

class TestSetPermission(unittest.TestCase):

    def test_adding_role_calls_set_permissions_with_role_included(self):
        svc   = _svc({"dashboard": ["Admin"]})
        model = PermissionsModel(svc, ["dashboard"])
        model.set_permission("dashboard", "Operator", allowed=True)
        stored = svc.set_permissions.call_args[0][1]
        self.assertIn("Operator", stored)
        self.assertIn("Admin", stored)

    def test_removing_role_calls_set_permissions_without_role(self):
        svc   = _svc({"dashboard": ["Admin", "Operator"]})
        model = PermissionsModel(svc, ["dashboard"])
        model.set_permission("dashboard", "Operator", allowed=False)
        stored = svc.set_permissions.call_args[0][1]
        self.assertNotIn("Operator", stored)
        self.assertIn("Admin", stored)

    def test_set_permission_passes_correct_app_id(self):
        svc   = _svc({"dashboard": ["Admin"]})
        model = PermissionsModel(svc, ["dashboard"])
        model.set_permission("dashboard", "Viewer", allowed=True)
        svc.set_permissions.assert_called_once()
        self.assertEqual(svc.set_permissions.call_args[0][0], "dashboard")

    def test_adding_already_present_role_is_idempotent(self):
        svc   = _svc({"dashboard": ["Admin", "Operator"]})
        model = PermissionsModel(svc, ["dashboard"])
        model.set_permission("dashboard", "Operator", allowed=True)
        stored = svc.set_permissions.call_args[0][1]
        self.assertEqual(stored.count("Operator"), 1)

    def test_removing_absent_role_is_safe(self):
        svc   = _svc({"dashboard": ["Admin"]})
        model = PermissionsModel(svc, ["dashboard"])
        model.set_permission("dashboard", "Viewer", allowed=False)
        stored = svc.set_permissions.call_args[0][1]
        self.assertNotIn("Viewer", stored)
        self.assertIn("Admin", stored)

    def test_set_permission_persists_immediately(self):
        svc   = _svc({"dashboard": ["Admin"]})
        model = PermissionsModel(svc, ["dashboard"])
        model.set_permission("dashboard", "Operator", allowed=True)
        svc.set_permissions.assert_called_once()

    def test_unlisted_app_gets_admin_default_before_toggling(self):
        """If service has no entry for an app, default to ['Admin'] before toggle."""
        svc   = _svc({})
        model = PermissionsModel(svc, ["new_app"])
        model.set_permission("new_app", "Operator", allowed=True)
        stored = svc.set_permissions.call_args[0][1]
        self.assertIn("Admin", stored)
        self.assertIn("Operator", stored)


if __name__ == "__main__":
    unittest.main()
