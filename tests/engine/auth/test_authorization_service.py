"""
Tests for src/engine/auth/authorization_service.y_pixels

Covers visible-app filtering, can_access, get_all_permissions, set_permissions,
and the Admin-always-has-access invariant on user_management.
"""
import unittest
from enum import Enum
from unittest.mock import MagicMock

from src.engine.auth.i_authenticated_user import IAuthenticatedUser
from src.engine.auth.i_permissions_repository import IPermissionsRepository
from src.engine.auth.authorization_service import AuthorizationService
from src.shared_contracts.declarations import ApplicationSpec


# ── Helpers ────────────────────────────────────────────────────────────────────

class _Role(Enum):
    ADMIN    = "Admin"
    OPERATOR = "Operator"
    VIEWER   = "Viewer"


def _user(role: _Role) -> IAuthenticatedUser:
    u = MagicMock(spec=IAuthenticatedUser)
    u.user_id = "1"
    u.role    = role
    return u


def _repo(data: dict) -> IPermissionsRepository:
    """Build a mock IPermissionsRepository from a plain dict."""
    repo = MagicMock(spec=IPermissionsRepository)
    repo.get_allowed_role_values.side_effect = lambda app_id: data.get(app_id, ["Admin"])
    repo.get_all.return_value = dict(data)
    return repo


def _spec(app_id: str) -> ApplicationSpec:
    return ApplicationSpec(name=app_id, folder_id=1, app_id=app_id)


# ── get_visible_apps ───────────────────────────────────────────────────────────

class TestGetVisibleApps(unittest.TestCase):

    def test_admin_sees_all_apps(self):
        repo = _repo({
            "dashboard": ["Admin", "Operator", "Viewer"],
            "settings":  ["Admin"],
        })
        svc   = AuthorizationService(repo)
        specs = [_spec("dashboard"), _spec("settings")]
        result = svc.get_visible_apps(_user(_Role.ADMIN), specs)
        self.assertEqual(result, specs)

    def test_operator_only_sees_permitted_apps(self):
        repo = _repo({
            "dashboard": ["Admin", "Operator"],
            "settings":  ["Admin"],
        })
        svc   = AuthorizationService(repo)
        specs = [_spec("dashboard"), _spec("settings")]
        result = svc.get_visible_apps(_user(_Role.OPERATOR), specs)
        self.assertEqual(result, [_spec("dashboard")])

    def test_viewer_sees_only_viewer_apps(self):
        repo = _repo({
            "dashboard": ["Admin", "Operator", "Viewer"],
            "settings":  ["Admin"],
        })
        svc   = AuthorizationService(repo)
        specs = [_spec("dashboard"), _spec("settings")]
        result = svc.get_visible_apps(_user(_Role.VIEWER), specs)
        self.assertEqual(result, [_spec("dashboard")])

    def test_unlisted_app_defaults_to_admin_only(self):
        repo  = _repo({})           # nothing stored
        svc   = AuthorizationService(repo)
        specs = [_spec("mystery_app")]
        result = svc.get_visible_apps(_user(_Role.OPERATOR), specs)
        self.assertEqual(result, [])

    def test_returns_empty_list_when_no_specs_match(self):
        repo  = _repo({"settings": ["Admin"]})
        svc   = AuthorizationService(repo)
        result = svc.get_visible_apps(_user(_Role.VIEWER), [_spec("settings")])
        self.assertEqual(result, [])


# ── can_access ─────────────────────────────────────────────────────────────────

class TestCanAccess(unittest.TestCase):

    def test_returns_true_when_role_is_allowed(self):
        repo = _repo({"dashboard": ["Admin", "Operator"]})
        svc  = AuthorizationService(repo)
        self.assertTrue(svc.can_access(_user(_Role.OPERATOR), "dashboard"))

    def test_returns_false_when_role_is_not_allowed(self):
        repo = _repo({"dashboard": ["Admin"]})
        svc  = AuthorizationService(repo)
        self.assertFalse(svc.can_access(_user(_Role.OPERATOR), "dashboard"))

    def test_unlisted_app_denies_non_admin(self):
        repo = _repo({})
        svc  = AuthorizationService(repo)
        self.assertFalse(svc.can_access(_user(_Role.OPERATOR), "unknown_app"))

    def test_unlisted_app_allows_admin(self):
        repo = _repo({})
        svc  = AuthorizationService(repo)
        self.assertTrue(svc.can_access(_user(_Role.ADMIN), "unknown_app"))


# ── get_all_permissions ────────────────────────────────────────────────────────

class TestGetAllPermissions(unittest.TestCase):

    def test_returns_full_map_from_repository(self):
        data = {"app_a": ["Admin"], "app_b": ["Admin", "Operator"]}
        repo = _repo(data)
        svc  = AuthorizationService(repo)
        self.assertEqual(svc.get_all_permissions(), data)


# ── set_permissions ────────────────────────────────────────────────────────────

class TestSetPermissions(unittest.TestCase):

    def test_delegates_to_repository(self):
        repo = MagicMock(spec=IPermissionsRepository)
        repo.get_allowed_role_values.return_value = ["Admin"]
        svc  = AuthorizationService(repo)
        svc.set_permissions("dashboard", ["Admin", "Operator"])
        repo.set_allowed_role_values.assert_called_once_with(
            "dashboard", ["Admin", "Operator"]
        )

    def test_user_management_always_retains_admin(self):
        repo = MagicMock(spec=IPermissionsRepository)
        svc  = AuthorizationService(repo, protected_app_role_values={"user_management": ["Admin"]})
        svc.set_permissions("user_management", ["Operator", "Viewer"])
        stored = repo.set_allowed_role_values.call_args[0][1]
        self.assertIn("Admin", stored)

    def test_user_management_retains_other_roles_alongside_admin(self):
        repo = MagicMock(spec=IPermissionsRepository)
        svc  = AuthorizationService(repo, protected_app_role_values={"user_management": ["Admin"]})
        svc.set_permissions("user_management", ["Admin", "Operator"])
        stored = repo.set_allowed_role_values.call_args[0][1]
        self.assertIn("Admin", stored)
        self.assertIn("Operator", stored)

    def test_other_apps_not_forced_to_include_admin(self):
        repo = MagicMock(spec=IPermissionsRepository)
        svc  = AuthorizationService(repo)
        svc.set_permissions("dashboard", ["Operator", "Viewer"])
        stored = repo.set_allowed_role_values.call_args[0][1]
        self.assertNotIn("Admin", stored)


if __name__ == "__main__":
    unittest.main()
