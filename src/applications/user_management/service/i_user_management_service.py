from abc import ABC, abstractmethod
from typing import List, Optional
from src.applications.user_management.domain.user_schema import UserRecord, UserSchema


class IUserManagementService(ABC):

    @abstractmethod
    def get_schema(self) -> UserSchema: ...

    @abstractmethod
    def get_all_users(self) -> List[UserRecord]: ...

    @abstractmethod
    def add_user(self, record: UserRecord) -> tuple[bool, str]: ...

    @abstractmethod
    def update_user(self, record: UserRecord) -> tuple[bool, str]: ...

    @abstractmethod
    def delete_user(self, user_id) -> tuple[bool, str]: ...

    @abstractmethod
    def generate_qr(self, record: UserRecord) -> tuple[bool, str, Optional[str]]:
        """Returns (success, message, qr_image_path)."""
        ...

    @abstractmethod
    def send_access_package(self, record: UserRecord, qr_image_path: str) -> tuple[bool, str]: ...
