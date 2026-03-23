from __future__ import annotations

import json
import os

from src.engine.auth.i_permissions_repository import IPermissionsRepository


class JsonPermissionsRepository(IPermissionsRepository):
    """JSON-backed permissions store."""

    def __init__(self, file_path: str, default_role_values: list[str] | None = None) -> None:
        self._path = file_path
        self._default_role_values = list(default_role_values or [])
        self._data: dict[str, list[str]] = self._load()

    def get_allowed_role_values(self, app_id: str) -> list[str]:
        return list(self._data.get(app_id, self._default_role_values))

    def set_allowed_role_values(self, app_id: str, role_values: list[str]) -> None:
        self._data[app_id] = list(role_values)
        self._save()

    def get_all(self) -> dict[str, list[str]]:
        return {k: list(v) for k, v in self._data.items()}

    def _load(self) -> dict[str, list[str]]:
        if not os.path.exists(self._path):
            self._write({})
            return {}
        with open(self._path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self) -> None:
        self._write(self._data)

    def _write(self, data: dict[str, list[str]]) -> None:
        parent = os.path.dirname(self._path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
