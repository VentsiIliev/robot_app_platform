import logging
import os
import tempfile
from typing import List, Optional

from src.applications.user_management.domain.i_user_repository import IUserRepository
from src.applications.user_management.domain.user_schema import UserRecord, UserSchema
from src.applications.user_management.service.i_user_management_service import IUserManagementService

_logger = logging.getLogger(__name__)


class UserManagementApplicationService(IUserManagementService):

    def __init__(self, repository: IUserRepository):
        self._repo = repository

    def get_schema(self) -> UserSchema:
        return self._repo.get_schema()

    def get_all_users(self) -> List[UserRecord]:
        return self._repo.get_all()

    def add_user(self, record: UserRecord) -> tuple[bool, str]:
        try:
            uid = record.get_id(self._repo.get_schema().id_key)
            ok  = self._repo.add(record)
            return (True, f"User '{uid}' added") if ok else (False, f"User ID '{uid}' already exists")
        except Exception as exc:
            _logger.exception("add_user failed")
            return False, str(exc)

    def update_user(self, record: UserRecord) -> tuple[bool, str]:
        try:
            uid = record.get_id(self._repo.get_schema().id_key)
            ok  = self._repo.update(record)
            return (True, f"User '{uid}' updated") if ok else (False, f"User '{uid}' not found")
        except Exception as exc:
            _logger.exception("update_user failed")
            return False, str(exc)

    def delete_user(self, user_id) -> tuple[bool, str]:
        try:
            ok = self._repo.delete(user_id)
            return (True, f"User {user_id} deleted") if ok else (False, f"User {user_id} not found")
        except Exception as exc:
            _logger.exception("delete_user failed")
            return False, str(exc)

    def generate_qr(self, record: UserRecord) -> tuple[bool, str, Optional[str]]:
        try:
            import qrcode
            uid      = record.get_id(self._repo.get_schema().id_key)
            pwd      = record.get("password", "")
            data     = f"id = {uid}\npassword = {pwd}"
            qr       = qrcode.make(data)
            tmp_path = os.path.join(tempfile.gettempdir(), f"qr_user_{uid}.png")
            qr.save(tmp_path)
            return True, "QR generated", tmp_path
        except Exception as exc:
            _logger.exception("generate_qr failed")
            return False, str(exc), None

    def send_access_package(self, record: UserRecord, qr_image_path: str) -> tuple[bool, str]:
        email = record.get("email")
        if not email:
            return False, "User has no email address"
        try:
            from src.applications.user_management.service._email_sender import send_user_access_package
            return send_user_access_package(record, qr_image_path)
        except Exception as exc:
            _logger.exception("send_access_package failed")
            return False, str(exc)
