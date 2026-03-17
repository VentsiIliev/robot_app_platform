from src.applications.user_management.domain.user import Role
from src.engine.auth.i_permissions_admin_service import IPermissionsAdminService

_DEFAULT_ROLES = ["Admin"]
_ALL_ROLE_VALUES = [r.value for r in Role]


class PermissionsModel:
    """Pure-logic model for the App Permissions tab.

    Wraps IPermissionsAdminService and filters results to only the known app_ids
    registered in the current RobotSystem shell. Each set_permission call
    persists immediately — no separate save step needed.
    """

    def __init__(
        self,
        service: IPermissionsAdminService,
        known_app_ids: list[str],
    ) -> None:
        self._service       = service
        self._known_app_ids = list(known_app_ids)

    # ── Read ───────────────────────────────────────────────────────────────────

    def get_known_app_ids(self) -> list[str]:
        return list(self._known_app_ids)

    def get_role_values(self) -> list[str]:
        """Column headers for the permissions table."""
        return list(_ALL_ROLE_VALUES)

    def get_permissions(self) -> dict[str, list[str]]:
        """Return permissions for known apps only.
        Apps missing from the service default to ['Admin']."""
        all_perms = self._service.get_all_permissions()
        return {
            app_id: list(all_perms.get(app_id, _DEFAULT_ROLES))
            for app_id in self._known_app_ids
        }

    # ── Write ──────────────────────────────────────────────────────────────────

    def set_permission(self, app_id: str, role_value: str, allowed: bool) -> None:
        """Toggle a single role for an app and persist immediately."""
        current = list(self._service.get_all_permissions().get(app_id, _DEFAULT_ROLES))
        if allowed:
            if role_value not in current:
                current.append(role_value)
        else:
            current = [r for r in current if r != role_value]
        self._service.set_permissions(app_id, current)
