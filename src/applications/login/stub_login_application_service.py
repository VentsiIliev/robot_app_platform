from enum import Enum
from typing import Optional, Tuple

from src.applications.login.i_login_application_service import ILoginApplicationService
from src.engine.auth.i_authenticated_user import IAuthenticatedUser


class _StubUser(IAuthenticatedUser):
    @property
    def user_id(self) -> str:
        return "0"

    @property
    def role(self) -> Enum:
        class _R(Enum):
            ADMIN = "Admin"
        return _R.ADMIN


class StubLoginApplicationService(ILoginApplicationService):
    """Always authenticates successfully. Used in tests and standalone runners."""

    def authenticate(self, user_id: str, password: str) -> Optional[IAuthenticatedUser]:
        return _StubUser()

    def authenticate_qr(self, qr_payload: str) -> Optional[IAuthenticatedUser]:
        return _StubUser()

    def try_qr_login(self) -> Optional[Tuple[str, str]]:
        return None

    def move_to_login_pos(self) -> None:
        pass

    def is_first_run(self) -> bool:
        return False

    def create_first_admin(
        self, user_id: str, first_name: str, last_name: str, password: str
    ) -> Tuple[bool, str]:
        return True, "Stub: admin created."
