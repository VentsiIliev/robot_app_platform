from abc import ABC, abstractmethod
from typing import List

from src.engine.auth.i_authenticated_user import IAuthenticatedUser


class IAuthorizationService(ABC):
    """Read-only authorization contract.

    Used by main.y_pixels and any runtime access guard.
    Does not expose write operations — callers get only the access they need.
    """

    @abstractmethod
    def get_visible_apps(self, user: IAuthenticatedUser, all_specs: list) -> list:
        """Return the subset of all_specs the user's role may access."""

    @abstractmethod
    def can_access(self, user: IAuthenticatedUser, app_id: str) -> bool:
        """Return True if the user's role is allowed to access app_id."""
