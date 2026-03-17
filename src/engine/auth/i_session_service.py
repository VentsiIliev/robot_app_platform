from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional

from src.engine.auth.i_authenticated_user import IAuthenticatedUser


class ISessionService(ABC):

    @abstractmethod
    def login(self, user: IAuthenticatedUser) -> None:
        """Store the authenticated user as the current session."""

    @abstractmethod
    def logout(self) -> None:
        """Clear the current session. Safe to call when already logged out."""

    @property
    @abstractmethod
    def current_user(self) -> Optional[IAuthenticatedUser]:
        """The currently logged-in user, or None if not authenticated."""

    @property
    @abstractmethod
    def current_role(self) -> Optional[Enum]:
        """The current user's role, or None if not authenticated."""

    @abstractmethod
    def is_authenticated(self) -> bool:
        """True if a user is currently logged in."""
