import threading
from enum import Enum
from typing import Optional

from src.engine.auth.i_authenticated_user import IAuthenticatedUser
from src.engine.auth.i_session_service import ISessionService


class UserSession(ISessionService):
    """Thread-safe session holder.

    Instantiated once in main.py and injected everywhere as ISessionService.
    Never access via a global — always inject.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._user: Optional[IAuthenticatedUser] = None

    # ── ISessionService ────────────────────────────────────────────────────────

    def login(self, user: IAuthenticatedUser) -> None:
        with self._lock:
            self._user = user

    def logout(self) -> None:
        with self._lock:
            self._user = None

    @property
    def current_user(self) -> Optional[IAuthenticatedUser]:
        with self._lock:
            return self._user

    @property
    def current_role(self) -> Optional[Enum]:
        with self._lock:
            return self._user.role if self._user else None

    def is_authenticated(self) -> bool:
        with self._lock:
            return self._user is not None
