"""
Tests for src/engine/auth/i_permissions_repository.py

Verifies the interface contract: any implementation must satisfy these behaviours.
Uses a minimal in-memory stub to prove the contract, not the JSON-backed implementation.
"""
import unittest

from src.engine.auth.i_permissions_repository import IPermissionsRepository


class _InMemoryPermissionsRepository(IPermissionsRepository):
    """Minimal in-memory stub — used only to verify the interface contract."""

    def __init__(self, data: dict = None):
        self._data: dict[str, list[str]] = data or {}

    def get_allowed_role_values(self, app_id: str) -> list[str]:
        return self._data.get(app_id, ["Admin"])

    def set_allowed_role_values(self, app_id: str, role_values: list[str]) -> None:
        self._data[app_id] = list(role_values)

    def get_all(self) -> dict[str, list[str]]:
        return dict(self._data)


class TestIPermissionsRepository(unittest.TestCase):

    def test_cannot_instantiate_directly(self):
        with self.assertRaises(TypeError):
            IPermissionsRepository()

    def test_get_allowed_role_values_returns_list_of_strings(self):
        repo = _InMemoryPermissionsRepository({"dashboard": ["Admin", "Operator"]})
        result = repo.get_allowed_role_values("dashboard")
        self.assertIsInstance(result, list)
        self.assertTrue(all(isinstance(v, str) for v in result))

    def test_get_allowed_role_values_defaults_to_admin_when_missing(self):
        repo = _InMemoryPermissionsRepository()
        result = repo.get_allowed_role_values("unknown_app")
        self.assertEqual(result, ["Admin"])

    def test_set_allowed_role_values_persists(self):
        repo = _InMemoryPermissionsRepository()
        repo.set_allowed_role_values("my_app", ["Admin", "Viewer"])
        self.assertEqual(repo.get_allowed_role_values("my_app"), ["Admin", "Viewer"])

    def test_set_allowed_role_values_overwrites_existing(self):
        repo = _InMemoryPermissionsRepository({"my_app": ["Admin", "Operator"]})
        repo.set_allowed_role_values("my_app", ["Admin"])
        self.assertEqual(repo.get_allowed_role_values("my_app"), ["Admin"])

    def test_get_all_returns_full_mapping(self):
        data = {"app_a": ["Admin"], "app_b": ["Admin", "Operator"]}
        repo = _InMemoryPermissionsRepository(data)
        result = repo.get_all()
        self.assertEqual(result, data)

    def test_get_all_returns_copy_not_reference(self):
        repo = _InMemoryPermissionsRepository({"app_a": ["Admin"]})
        result = repo.get_all()
        result["injected"] = ["Admin"]
        self.assertNotIn("injected", repo.get_all())

    def test_set_does_not_store_reference_to_input_list(self):
        repo = _InMemoryPermissionsRepository()
        roles = ["Admin", "Operator"]
        repo.set_allowed_role_values("app_a", roles)
        roles.append("Viewer")
        self.assertNotIn("Viewer", repo.get_allowed_role_values("app_a"))


if __name__ == "__main__":
    unittest.main()
