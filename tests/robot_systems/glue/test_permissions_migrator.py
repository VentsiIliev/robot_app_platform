"""
Tests for src/robot_systems/glue/domain/permissions/permissions_migrator.y_pixels

Verifies that ensure_permissions_current adds missing app_ids, removes stale keys,
saves back only when changes were made, and preserves existing values untouched.
"""
import unittest
from unittest.mock import MagicMock, call

from src.engine.auth.i_permissions_repository import IPermissionsRepository
from src.robot_systems.glue.domain.permissions.permissions_migrator import ensure_permissions_current


def _repo(data: dict) -> IPermissionsRepository:
    repo = MagicMock(spec=IPermissionsRepository)
    # get_all returns a snapshot; set_allowed_role_values captured for assertions
    repo.get_all.return_value = dict(data)
    return repo


class TestEnsurePermissionsCurrent(unittest.TestCase):

    def test_adds_missing_app_id_with_admin_default(self):
        repo = _repo({})
        ensure_permissions_current(repo, known_app_ids=["dashboard"])
        repo.set_allowed_role_values.assert_called_once_with("dashboard", ["Admin"])

    def test_does_not_overwrite_existing_entry(self):
        repo = _repo({"dashboard": ["Admin", "Operator"]})
        ensure_permissions_current(repo, known_app_ids=["dashboard"])
        repo.set_allowed_role_values.assert_not_called()

    def test_removes_stale_key_no_longer_in_known_ids(self):
        repo = _repo({"old_app": ["Admin"]})
        # Capture what was written back
        written = {}
        repo.set_allowed_role_values.side_effect = lambda k, v: written.update({k: v})
        ensure_permissions_current(repo, known_app_ids=[])
        # old_app must not appear in any set_allowed_role_values call
        self.assertNotIn("old_app", written)

    def test_no_writes_when_already_in_sync(self):
        repo = _repo({"dashboard": ["Admin"], "settings": ["Admin"]})
        ensure_permissions_current(repo, known_app_ids=["dashboard", "settings"])
        repo.set_allowed_role_values.assert_not_called()

    def test_adds_multiple_missing_apps(self):
        repo = _repo({})
        ensure_permissions_current(repo, known_app_ids=["app_a", "app_b", "app_c"])
        calls = {c.args[0] for c in repo.set_allowed_role_values.call_args_list}
        self.assertEqual(calls, {"app_a", "app_b", "app_c"})

    def test_mixed_add_and_remove(self):
        repo = _repo({"stale_app": ["Admin"], "kept_app": ["Admin", "Operator"]})
        written = {}
        repo.set_allowed_role_values.side_effect = lambda k, v: written.update({k: v})
        ensure_permissions_current(repo, known_app_ids=["kept_app", "new_app"])
        # new_app should be added
        self.assertIn("new_app", written)
        # kept_app already exists and has correct values — not rewritten
        self.assertNotIn("kept_app", written)
        # stale_app is not in known_ids — not in written (no set call for it)
        self.assertNotIn("stale_app", written)

    def test_empty_known_ids_removes_all_stale_keys(self):
        repo = _repo({"app_a": ["Admin"], "app_b": ["Admin"]})
        written = {}
        repo.set_allowed_role_values.side_effect = lambda k, v: written.update({k: v})
        ensure_permissions_current(repo, known_app_ids=[])
        self.assertEqual(written, {})


if __name__ == "__main__":
    unittest.main()
