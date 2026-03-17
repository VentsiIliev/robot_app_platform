from typing import Optional

from src.applications.user_management.domain.i_user_repository import IUserRepository
from src.applications.user_management.domain.user import User
from src.engine.auth.i_authenticated_user import IAuthenticatedUser
from src.engine.auth.i_authentication_service import IAuthenticationService
from src.robot_systems.glue.domain.auth.authenticated_user import AuthenticatedUser


class AuthenticationService(IAuthenticationService):
    """Verifies credentials against IUserRepository and returns AuthenticatedUser.

    Lives at robot-system level: may import application-layer types (User,
    IUserRepository) and engine-level interfaces (IAuthenticatedUser).
    Lockout tracking is handled internally — not exposed on IAuthenticationService.
    """

    def __init__(self, repository: IUserRepository) -> None:
        self._repo = repository

    # ── IAuthenticationService ─────────────────────────────────────────────────

    def authenticate(self, user_id: str, password: str) -> Optional[IAuthenticatedUser]:
        record = self._repo.get_by_id(user_id)
        if record is None:
            return None
        if record.get("password") != password:
            return None
        return AuthenticatedUser(User.from_dict(record.to_dict()))

    def authenticate_qr(self, qr_payload: str) -> Optional[IAuthenticatedUser]:
        """QR payload format: 'user_id:password'.
        Note: future versions should use a signed token instead of plain credentials.
        """
        try:
            parts = qr_payload.split(":", 1)
            if len(parts) != 2:
                return None
            user_id, password = parts
            return self.authenticate(user_id, password)
        except Exception:
            return None
