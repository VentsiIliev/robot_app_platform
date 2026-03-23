from __future__ import annotations

from typing import Optional

from src.applications.user_management.domain.i_user_repository import IUserRepository
from src.engine.auth.auth_user_record import AuthUserRecord
from src.engine.auth.i_auth_user_repository import IAuthUserRepository


class AuthUserRepositoryAdapter(IAuthUserRepository):
    """Expose an application-level user repository through the auth contract."""

    def __init__(self, repository: IUserRepository) -> None:
        self._repository = repository

    def get_by_id(self, user_id: str) -> Optional[AuthUserRecord]:
        record = self._repository.get_by_id(user_id)
        if record is None:
            return None
        schema = self._repository.get_schema()
        data = record.to_dict()
        role_value = data.get("role")
        if role_value is None:
            raise RuntimeError(
                "User repository record is missing 'role'. "
                "Authentication requires a role field convertible to an Enum."
            )
        role = self._parse_role(role_value)
        return AuthUserRecord(
            user_id=str(data.get(schema.id_key, user_id)),
            password=str(data.get("password", "")),
            role=role,
            payload=data,
        )

    @staticmethod
    def _parse_role(role_value):
        if hasattr(role_value, "value"):
            return role_value
        return _RoleValue(str(role_value))


class _RoleValue(str):
    @property
    def value(self) -> str:
        return str(self)
