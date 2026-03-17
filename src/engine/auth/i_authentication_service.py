from abc import ABC, abstractmethod
from typing import Optional

from src.engine.auth.i_authenticated_user import IAuthenticatedUser


class IAuthenticationService(ABC):

    @abstractmethod
    def authenticate(self, user_id: str, password: str) -> Optional[IAuthenticatedUser]:
        """Verify credentials. Returns IAuthenticatedUser on success, None on failure.
        Lockout tracking is handled internally — not exposed on this interface."""

    @abstractmethod
    def authenticate_qr(self, qr_payload: str) -> Optional[IAuthenticatedUser]:
        """Decode a QR payload and verify the embedded credentials."""
