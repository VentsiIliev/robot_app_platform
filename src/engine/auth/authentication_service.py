from __future__ import annotations

from typing import Optional

from src.engine.auth.authenticated_user import AuthenticatedUser
from src.engine.auth.i_authenticated_user import IAuthenticatedUser
from src.engine.auth.i_authentication_service import IAuthenticationService
from src.engine.auth.i_auth_user_repository import IAuthUserRepository


class AuthenticationService(IAuthenticationService):
    """Reusable credential verification backed by IAuthUserRepository."""

    def __init__(self, repository: IAuthUserRepository) -> None:
        self._repo = repository

    def authenticate(self, user_id: str, password: str) -> Optional[IAuthenticatedUser]:
        record = self._repo.get_by_id(user_id)
        if record is None:
            return None
        if record.password != password:
            return None
        return AuthenticatedUser(record)

    def authenticate_qr(self, qr_payload: str) -> Optional[IAuthenticatedUser]:
        try:
            user_id, password = qr_payload.split(":", 1)
        except ValueError:
            return None
        return self.authenticate(user_id, password)
