from abc import abstractmethod
from typing import List

from src.engine.auth.i_authorization_service import IAuthorizationService


class IPermissionsAdminService(IAuthorizationService):
    """Extends IAuthorizationService with admin write operations.

    Only the permissions editor model should depend on this interface.
    main.y_pixels and runtime guards use the narrower IAuthorizationService.
    """

    @abstractmethod
    def get_all_permissions(self) -> dict[str, list[str]]:
        """Return the full app_id → role_values map for the admin editor UI."""

    @abstractmethod
    def set_permissions(self, app_id: str, role_values: list[str]) -> None:
        """Update and persist role access for app_id.
        Implementations may enforce robot-system-specific protected role invariants."""
