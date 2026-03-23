from __future__ import annotations

from enum import Enum

from src.engine.auth.auth_user_record import AuthUserRecord
from src.engine.auth.i_authenticated_user import IAuthenticatedUser


class AuthenticatedUser(IAuthenticatedUser):
    """Default engine-level authenticated user wrapper."""

    def __init__(self, record: AuthUserRecord) -> None:
        self._record = record

    @property
    def user_id(self) -> str:
        return str(self._record.user_id)

    @property
    def role(self) -> Enum:
        return self._record.role

    @property
    def record(self) -> AuthUserRecord:
        return self._record
