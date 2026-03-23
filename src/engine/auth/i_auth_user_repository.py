from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.engine.auth.auth_user_record import AuthUserRecord


class IAuthUserRepository(ABC):
    @abstractmethod
    def get_by_id(self, user_id: str) -> Optional[AuthUserRecord]:
        """Return the auth-facing record for the given user id, or None."""
