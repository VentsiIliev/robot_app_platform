from src.engine.auth.i_authenticated_user import IAuthenticatedUser
from src.engine.auth.i_permissions_admin_service import IPermissionsAdminService
from src.engine.auth.i_permissions_repository import IPermissionsRepository

_USER_MANAGEMENT_APP_ID = "user_management"


class AuthorizationService(IPermissionsAdminService):
    """Role-based app filtering backed by IPermissionsRepository.

    Comparison is done on role.value strings — no concrete Role type is imported.
    """

    def __init__(self, repository: IPermissionsRepository) -> None:
        self._repo = repository

    # ── IAuthorizationService ──────────────────────────────────────────────────

    def get_visible_apps(self, user: IAuthenticatedUser, all_specs: list) -> list:
        return [spec for spec in all_specs if self.can_access(user, spec.app_id)]

    def can_access(self, user: IAuthenticatedUser, app_id: str) -> bool:
        allowed = self._repo.get_allowed_role_values(app_id)
        return user.role.value in allowed

    # ── IPermissionsAdminService ───────────────────────────────────────────────

    def get_all_permissions(self) -> dict[str, list[str]]:
        return self._repo.get_all()

    def set_permissions(self, app_id: str, role_values: list[str]) -> None:
        if app_id == _USER_MANAGEMENT_APP_ID:
            role_values = list(set(role_values) | {"Admin"})
        self._repo.set_allowed_role_values(app_id, role_values)
