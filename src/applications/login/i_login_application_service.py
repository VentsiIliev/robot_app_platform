from abc import ABC, abstractmethod
from typing import Optional, Tuple

from src.engine.auth.i_authenticated_user import IAuthenticatedUser


class ILoginApplicationService(ABC):

    @abstractmethod
    def authenticate(self, user_id: str, password: str) -> Optional[IAuthenticatedUser]:
        """Verify credentials. Returns IAuthenticatedUser on success, None on failure."""

    @abstractmethod
    def authenticate_qr(self, qr_payload: str) -> Optional[IAuthenticatedUser]:
        """Verify a QR-encoded payload. Returns IAuthenticatedUser on success, None on failure."""

    @abstractmethod
    def try_qr_login(self) -> Optional[Tuple[str, str]]:
        """Poll the camera for a QR code.
        Returns (user_id, password) if a valid payload is detected, None otherwise."""

    @abstractmethod
    def move_to_login_pos(self) -> None:
        """Move the robot to the QR scan position. No-op if no robot is configured."""

    @abstractmethod
    def is_first_run(self) -> bool:
        """True if the user store is empty — setup wizard should be shown."""

    @abstractmethod
    def create_first_admin(
        self, user_id: str, first_name: str, last_name: str, password: str
    ) -> Tuple[bool, str]:
        """Create the initial admin user on first run.
        Returns (success, message)."""
