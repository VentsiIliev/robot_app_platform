from src.engine.auth.i_authenticated_user import IAuthenticatedUser
from src.engine.auth.i_permissions_admin_service import IPermissionsAdminService
from src.engine.auth.i_permissions_repository import IPermissionsRepository

_USER_MANAGEMENT_APP_ID = "user_management"

class AuthorizationService(IPermissionsAdminService):
    """Role-based app filtering backed by IPermissionsRepository.

    Comparison is done on role.value strings — no concrete Role type is imported.
    """

    def __init__(
        self,
        repository: IPermissionsRepository,
        protected_app_role_values: dict[str, list[str]] | None = None,
    ) -> None:
        self._repo = repository
        self._protected_app_role_values = {
            str(app_id): list(role_values)
            for app_id, role_values in (protected_app_role_values or {}).items()
        }

    # ── IAuthorizationService ──────────────────────────────────────────────────

    def get_visible_apps(self, user: IAuthenticatedUser, all_specs: list) -> list:
        return [spec for spec in all_specs if self.can_access(user, spec.app_id)]

    def can_access(self, user: IAuthenticatedUser, app_id: str) -> bool:
        allowed = self._repo.get_allowed_role_values(app_id)
        return self._role_value(user) in allowed

    # ── IPermissionsAdminService ───────────────────────────────────────────────

    def get_all_permissions(self) -> dict[str, list[str]]:
        return self._repo.get_all()

    def set_permissions(self, app_id: str, role_values: list[str]) -> None:
        protected_roles = self._protected_app_role_values.get(app_id, [])
        if protected_roles:
            role_values = list(set(role_values) | set(protected_roles))
        self._repo.set_allowed_role_values(app_id, role_values)

    @staticmethod
    def _role_value(user: IAuthenticatedUser) -> str:
        role = user.role
        return str(getattr(role, "value", role))
