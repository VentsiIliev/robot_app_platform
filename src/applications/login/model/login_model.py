from typing import Optional, Tuple

from src.applications.login.i_login_application_service import ILoginApplicationService
from src.engine.auth.i_authenticated_user import IAuthenticatedUser


class LoginModel:

    def __init__(self, service: ILoginApplicationService) -> None:
        self._svc = service

    # ── Delegation ──────────────────────────────────────────────────────────

    def is_first_run(self) -> bool:
        return self._svc.is_first_run()

    def authenticate(self, user_id: str, password: str) -> Optional[IAuthenticatedUser]:
        return self._svc.authenticate(user_id, password)

    def authenticate_qr(self, qr_payload: str) -> Optional[IAuthenticatedUser]:
        return self._svc.authenticate_qr(qr_payload)

    def try_qr_login(self) -> Optional[Tuple[str, str]]:
        return self._svc.try_qr_login()

    def move_to_login_pos(self) -> None:
        self._svc.move_to_login_pos()

    def create_first_admin(
        self, user_id: str, first_name: str, last_name: str, password: str
    ) -> Tuple[bool, str]:
        return self._svc.create_first_admin(user_id, first_name, last_name, password)

    # ── Validation ──────────────────────────────────────────────────────────

    def validate_login_input(self, user_id: str, password: str) -> Optional[str]:
        uid = user_id.strip()
        pw  = password.strip()
        if not uid:
            return "User id is required."
        if not uid.isnumeric():
            return "User id must be numeric."
        if not pw:
            return "Password is required."
        return None
