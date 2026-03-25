"""
Tests for src/robot_systems/glue/domain/permissions/permissions_repository.y_pixels

Covers JSON persistence, default fallback, copy semantics, and round-trip fidelity.
Uses a temp file so tests are fully isolated and leave no side effects.
"""
import json
import os
import tempfile
import unittest

from src.engine.auth.json_permissions_repository import JsonPermissionsRepository


class TestJsonPermissionsRepository(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        self._tmp.close()
        self._path = self._tmp.name

    def tearDown(self):
        os.unlink(self._path)

    # ── helpers ────────────────────────────────────────────────────────────────

    def _make_repo(self, initial: dict = None) -> JsonPermissionsRepository:
        if initial is not None:
            with open(self._path, "w") as f:
                json.dump(initial, f)
        return JsonPermissionsRepository(self._path)

    # ── construction ───────────────────────────────────────────────────────────

    def test_loads_existing_file(self):
        repo = self._make_repo({"dashboard": ["Admin", "Operator"]})
        self.assertEqual(repo.get_allowed_role_values("dashboard"), ["Admin", "Operator"])

    def test_creates_empty_file_when_missing(self):
        os.unlink(self._path)
        repo = JsonPermissionsRepository(self._path)
        self.assertTrue(os.path.exists(self._path))
        self.assertEqual(repo.get_all(), {})

    def test_handles_empty_json_file(self):
        with open(self._path, "w") as f:
            f.write("{}")
        repo = JsonPermissionsRepository(self._path)
        self.assertEqual(repo.get_all(), {})

    # ── get_allowed_role_values ────────────────────────────────────────────────

    def test_returns_stored_roles(self):
        repo = self._make_repo({"my_app": ["Admin", "Viewer"]})
        self.assertEqual(repo.get_allowed_role_values("my_app"), ["Admin", "Viewer"])

    def test_defaults_to_admin_for_unknown_app(self):
        repo = self._make_repo({})
        self.assertEqual(repo.get_allowed_role_values("unknown"), ["Admin"])

    def test_returns_copy_not_internal_reference(self):
        repo = self._make_repo({"app": ["Admin"]})
        result = repo.get_allowed_role_values("app")
        result.append("Operator")
        self.assertEqual(repo.get_allowed_role_values("app"), ["Admin"])

    # ── set_allowed_role_values ────────────────────────────────────────────────

    def test_set_persists_to_disk(self):
        repo = self._make_repo({})
        repo.set_allowed_role_values("new_app", ["Admin", "Operator"])

        # Re-load from disk to confirm persistence
        repo2 = JsonPermissionsRepository(self._path)
        self.assertEqual(repo2.get_allowed_role_values("new_app"), ["Admin", "Operator"])

    def test_set_overwrites_existing_entry(self):
        repo = self._make_repo({"app": ["Admin", "Operator"]})
        repo.set_allowed_role_values("app", ["Admin"])
        self.assertEqual(repo.get_allowed_role_values("app"), ["Admin"])

    def test_set_does_not_store_input_reference(self):
        repo = self._make_repo({})
        roles = ["Admin"]
        repo.set_allowed_role_values("app", roles)
        roles.append("Operator")
        self.assertEqual(repo.get_allowed_role_values("app"), ["Admin"])

    # ── get_all ────────────────────────────────────────────────────────────────

    def test_get_all_returns_full_map(self):
        data = {"app_a": ["Admin"], "app_b": ["Admin", "Operator"]}
        repo = self._make_repo(data)
        self.assertEqual(repo.get_all(), data)

    def test_get_all_returns_copy(self):
        repo = self._make_repo({"app_a": ["Admin"]})
        result = repo.get_all()
        result["injected"] = ["Admin"]
        self.assertNotIn("injected", repo.get_all())

    # ── round-trip ─────────────────────────────────────────────────────────────

    def test_round_trip_multiple_apps(self):
        repo = self._make_repo({})
        repo.set_allowed_role_values("glue_dashboard", ["Admin", "Operator", "Viewer"])
        repo.set_allowed_role_values("robot_settings", ["Admin"])

        repo2 = JsonPermissionsRepository(self._path)
        self.assertEqual(
            repo2.get_allowed_role_values("glue_dashboard"),
            ["Admin", "Operator", "Viewer"],
        )
        self.assertEqual(repo2.get_allowed_role_values("robot_settings"), ["Admin"])


if __name__ == "__main__":
    unittest.main()
