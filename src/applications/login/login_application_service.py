from typing import List, Optional, Tuple

from src.applications.login.i_login_application_service import ILoginApplicationService
from src.applications.login.i_qr_scanner import IQrScanner
from src.applications.user_management.domain.i_user_repository import IUserRepository
from src.applications.user_management.domain.user_schema import UserRecord
from src.engine.auth.i_authenticated_user import IAuthenticatedUser
from src.engine.auth.i_authentication_service import IAuthenticationService
from src.engine.robot.interfaces.i_robot_service import IRobotService

_LOGIN_MOVE_TOOL = 0
_LOGIN_MOVE_USER = 0
_LOGIN_MOVE_VEL  = 20.0
_LOGIN_MOVE_ACC  = 20.0


class LoginApplicationService(ILoginApplicationService):
    """Application service for the login flow.

    Delegates auth to IAuthenticationService. Manages first-run detection,
    admin creation, optional robot positioning, and optional QR scanning.
    robot_service and qr_scanner are optional — features degrade gracefully
    when absent (useful in development or non-robot configurations).
    """

    def __init__(
        self,
        auth_service:    IAuthenticationService,
        user_repository: IUserRepository,
        robot_service:   Optional[IRobotService]  = None,
        qr_scanner:      Optional[IQrScanner]     = None,
        login_position:  Optional[List[float]]    = None,
        admin_role_value: str = "Admin",
    ) -> None:
        self._auth          = auth_service
        self._repo          = user_repository
        self._robot         = robot_service
        self._scanner       = qr_scanner
        self._login_pos     = login_position
        self._admin_role_value = str(admin_role_value)

    # ── ILoginApplicationService ───────────────────────────────────────────────

    def authenticate(self, user_id: str, password: str) -> Optional[IAuthenticatedUser]:
        return self._auth.authenticate(user_id, password)

    def authenticate_qr(self, qr_payload: str) -> Optional[IAuthenticatedUser]:
        return self._auth.authenticate_qr(qr_payload)

    def try_qr_login(self) -> Optional[Tuple[str, str]]:
        if self._scanner is None:
            return None
        payload = self._scanner.scan()
        if payload is None:
            return None
        parts = payload.split(":", 1)
        if len(parts) != 2:
            return None
        return parts[0], parts[1]

    def move_to_login_pos(self) -> None:
        if self._robot is None or self._login_pos is None:
            return
        self._robot.move_ptp(
            self._login_pos,
            _LOGIN_MOVE_TOOL,
            _LOGIN_MOVE_USER,
            _LOGIN_MOVE_VEL,
            _LOGIN_MOVE_ACC,
        )

    def is_first_run(self) -> bool:
        return len(self._repo.get_all()) == 0

    def create_first_admin(
        self, user_id: str, first_name: str, last_name: str, password: str
    ) -> Tuple[bool, str]:
        record = UserRecord.from_dict({
            "id":        user_id,
            "firstName": first_name,
            "lastName":  last_name,
            "password":  password,
            "role":      self._admin_role_value,
            "email":     "",
        })
        success = self._repo.add(record)
        return (True, "Admin created.") if success else (False, "Failed to create admin user.")
