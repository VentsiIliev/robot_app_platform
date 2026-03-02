from typing import List, Optional
from src.applications.base.i_application_model import IApplicationModel
from src.applications.user_management.domain.user_schema import UserRecord, UserSchema
from src.applications.user_management.service.i_user_management_service import IUserManagementService


class UserManagementModel(IApplicationModel):

    def __init__(self, service: IUserManagementService):
        self._service = service
        self._records: List[UserRecord] = []
        self._schema:  UserSchema       = service.get_schema()

    @property
    def schema(self) -> UserSchema:
        return self._schema

    def load(self) -> List[UserRecord]:
        self._records = self._service.get_all_users()
        return self._records

    def save(self, *args, **kwargs) -> None:
        pass

    def get_users(self) -> List[UserRecord]:
        return list(self._records)

    def add_user(self, record: UserRecord) -> tuple[bool, str]:
        ok, msg = self._service.add_user(record)
        if ok:
            self._records = self._service.get_all_users()
        return ok, msg

    def update_user(self, record: UserRecord) -> tuple[bool, str]:
        ok, msg = self._service.update_user(record)
        if ok:
            self._records = self._service.get_all_users()
        return ok, msg

    def delete_user(self, user_id) -> tuple[bool, str]:
        ok, msg = self._service.delete_user(user_id)
        if ok:
            self._records = self._service.get_all_users()
        return ok, msg

    def generate_qr(self, record: UserRecord) -> tuple[bool, str, Optional[str]]:
        return self._service.generate_qr(record)

    def send_access_package(self, record: UserRecord, qr_path: str) -> tuple[bool, str]:
        return self._service.send_access_package(record, qr_path)
