from src.engine.auth.i_permissions_repository import IPermissionsRepository

_DEFAULT_ROLES = ["Admin"]


def ensure_permissions_current(
    repo: IPermissionsRepository,
    known_app_ids: list[str],
) -> None:
    """Reconcile the permissions store against the live set of app_ids.

    - Adds missing app_ids with the safe default ["Admin"].
    - Stale keys (app_ids no longer in known_app_ids) are left untouched in
      storage but will never be queried — new apps start admin-only by default.
    - Writes to the repo only for entries that are genuinely missing.

    Called once at startup in main.y_pixels after PermissionsRepository is built.
    """
    existing = repo.get_all()
    for app_id in known_app_ids:
        if app_id not in existing:
            repo.set_allowed_role_values(app_id, list(_DEFAULT_ROLES))
