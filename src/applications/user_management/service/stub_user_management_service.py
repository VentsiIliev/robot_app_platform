import logging
from typing import List, Optional

from src.applications.user_management.domain.default_schema import DEFAULT_USER_SCHEMA
from src.applications.user_management.domain.user_schema import UserRecord, UserSchema
from src.applications.user_management.service.i_user_management_service import IUserManagementService

_logger = logging.getLogger(__name__)

_STUB_RECORDS = [
    UserRecord({"id": "1", "firstName": "Alice", "lastName": "Admin",    "password": "admin123", "role": "Admin",    "email": "alice@example.com"}),
    UserRecord({"id": "2", "firstName": "Bob",   "lastName": "Operator", "password": "op456",    "role": "Operator", "email": "bob@example.com"}),
]


class StubUserManagementService(IUserManagementService):

    def __init__(self, schema: UserSchema = DEFAULT_USER_SCHEMA):
        self._schema  = schema
        self._records = [UserRecord(r.to_dict()) for r in _STUB_RECORDS]

    def get_schema(self) -> UserSchema:
        return self._schema

    def get_all_users(self) -> List[UserRecord]:
        _logger.info("Stub: get_all_users → %d records", len(self._records))
        return list(self._records)

    def add_user(self, record: UserRecord) -> tuple[bool, str]:
        uid = record.get_id(self._schema.id_key)
        if any(r.get_id(self._schema.id_key) == uid for r in self._records):
            return False, f"User {uid} already exists"
        self._records.append(record)
        _logger.info("Stub: add_user id=%s", uid)
        return True, f"User {uid} added"

    def update_user(self, record: UserRecord) -> tuple[bool, str]:
        uid = record.get_id(self._schema.id_key)
        for i, r in enumerate(self._records):
            if r.get_id(self._schema.id_key) == uid:
                self._records[i] = record
                _logger.info("Stub: update_user id=%s", uid)
                return True, f"User {uid} updated"
        return False, f"User {uid} not found"

    def delete_user(self, user_id) -> tuple[bool, str]:
        before = len(self._records)
        self._records = [r for r in self._records if r.get_id(self._schema.id_key) != user_id]
        if len(self._records) < before:
            _logger.info("Stub: delete_user id=%s", user_id)
            return True, f"User {user_id} deleted"
        return False, f"User {user_id} not found"

    def generate_qr(self, record: UserRecord) -> tuple[bool, str, Optional[str]]:
        _logger.info("Stub: generate_qr id=%s", record.get_id(self._schema.id_key))
        return True, "Stub QR generated", None

    def send_access_package(self, record: UserRecord, qr_image_path: str) -> tuple[bool, str]:
        email = record.get("email", "")
        _logger.info("Stub: send_access_package id=%s email=%s", record.get_id(self._schema.id_key), email)
        return True, f"Stub: package sent to {email}"
