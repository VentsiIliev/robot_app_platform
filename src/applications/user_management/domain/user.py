from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Role(Enum):
    ADMIN     = "Admin"
    OPERATOR  = "Operator"
    VIEWER    = "Viewer"
    DEVELOPER = "Developer"



class UserField(Enum):
    ID         = "id"
    FIRST_NAME = "firstName"
    LAST_NAME  = "lastName"
    PASSWORD   = "password"
    ROLE       = "role"
    EMAIL      = "email"


@dataclass
class User:
    id:         int
    firstName:  str
    lastName:   str
    password:   str
    role:       Role
    email:      Optional[str] = None

    def get_full_name(self) -> str:
        return f"{self.firstName} {self.lastName}"

    def to_dict(self) -> dict:
        return {
            UserField.ID.value:         self.id,
            UserField.FIRST_NAME.value: self.firstName,
            UserField.LAST_NAME.value:  self.lastName,
            UserField.PASSWORD.value:   self.password,
            UserField.ROLE.value:       self.role.value,
            UserField.EMAIL.value:      self.email or "",
        }

    @staticmethod
    def from_dict(data: dict) -> User:
        role_val = data.get(UserField.ROLE.value, Role.OPERATOR.value)
        try:
            role = Role(role_val)
        except ValueError:
            role = Role.OPERATOR
        email = data.get(UserField.EMAIL.value) or None
        return User(
            id        = int(data[UserField.ID.value]),
            firstName = data[UserField.FIRST_NAME.value],
            lastName  = data[UserField.LAST_NAME.value],
            password  = data[UserField.PASSWORD.value],
            role      = role,
            email     = email,
        )

