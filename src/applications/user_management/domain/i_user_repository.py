from abc import ABC, abstractmethod
from typing import List, Optional
from src.applications.user_management.domain.user_schema import UserRecord, UserSchema


class IUserRepository(ABC):

    @abstractmethod
    def get_schema(self) -> UserSchema: ...

    @abstractmethod
    def get_all(self) -> List[UserRecord]: ...

    @abstractmethod
    def get_by_id(self, user_id) -> Optional[UserRecord]: ...

    @abstractmethod
    def add(self, record: UserRecord) -> bool: ...

    @abstractmethod
    def update(self, record: UserRecord) -> bool: ...

    @abstractmethod
    def delete(self, user_id) -> bool: ...

    @abstractmethod
    def exists(self, user_id) -> bool: ...
