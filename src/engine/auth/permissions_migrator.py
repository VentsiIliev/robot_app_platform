from __future__ import annotations

from src.engine.auth.i_permissions_repository import IPermissionsRepository


def ensure_permissions_current(
    repo: IPermissionsRepository,
    known_app_ids: list[str],
    default_role_values: list[str],
) -> None:
    """Add missing app ids with the configured default role values."""
    existing = repo.get_all()
    for app_id in known_app_ids:
        if app_id not in existing:
            repo.set_allowed_role_values(app_id, list(default_role_values))
