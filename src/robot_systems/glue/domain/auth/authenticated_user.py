from enum import Enum

from src.applications.user_management.domain.user import User
from src.engine.auth.i_authenticated_user import IAuthenticatedUser


class AuthenticatedUser(IAuthenticatedUser):
    """Adapter: wraps the domain User and satisfies IAuthenticatedUser.

    Lives at robot-system level so it can import both User (application level)
    and IAuthenticatedUser (engine level) without violating layer rules.
    The engine only ever sees IAuthenticatedUser — never this class directly.
    """

    def __init__(self, user: User) -> None:
        self._user = user

    @property
    def user_id(self) -> str:
        return str(self._user.id)

    @property
    def role(self) -> Enum:
        return self._user.role

    @property
    def underlying_user(self) -> User:
        """Access the wrapped domain User when application-level details are needed."""
        return self._user
