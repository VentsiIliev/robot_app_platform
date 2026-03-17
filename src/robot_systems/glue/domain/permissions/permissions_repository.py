import json
import os

from src.engine.auth.i_permissions_repository import IPermissionsRepository

_DEFAULT_ROLES = ["Admin"]


class PermissionsRepository(IPermissionsRepository):
    """JSON-backed permissions store.

    Stores and retrieves role value strings (e.g. "Admin", "Operator", "Viewer")
    keyed by stable app_id. Never imports Role — works exclusively with strings.
    """

    def __init__(self, file_path: str) -> None:
        self._path = file_path
        self._data: dict[str, list[str]] = self._load()

    # ── IPermissionsRepository ─────────────────────────────────────────────────

    def get_allowed_role_values(self, app_id: str) -> list[str]:
        return list(self._data.get(app_id, _DEFAULT_ROLES))

    def set_allowed_role_values(self, app_id: str, role_values: list[str]) -> None:
        self._data[app_id] = list(role_values)
        self._save()

    def get_all(self) -> dict[str, list[str]]:
        return {k: list(v) for k, v in self._data.items()}

    # ── internals ─────────────────────────────────────────────────────────────

    def _load(self) -> dict[str, list[str]]:
        if not os.path.exists(self._path):
            self._write({})
            return {}
        with open(self._path, "r") as f:
            return json.load(f)

    def _save(self) -> None:
        self._write(self._data)

    def _write(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True) if os.path.dirname(self._path) else None
        with open(self._path, "w") as f:
            json.dump(data, f, indent=2)
