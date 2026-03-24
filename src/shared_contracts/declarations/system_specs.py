from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Type

from src.engine.repositories.interfaces import ISettingsSerializer


@dataclass(frozen=True)
class FolderSpec:
    folder_id: int
    name: str
    display_name: str
    translation_key: str = ""

    def __post_init__(self):
        object.__setattr__(
            self, "translation_key",
            self.translation_key or f"folder.{self.name.lower()}"
        )


@dataclass(frozen=True)
class ApplicationSpec:
    name: str
    folder_id: int
    icon: str = "fa5s.cog"
    factory: Optional[Callable] = field(default=None, compare=False)
    app_id: str = ""

    def __post_init__(self):
        if not self.app_id:
            object.__setattr__(self, "app_id", self.name.lower().replace(" ", "_"))


@dataclass(frozen=True)
class ShellSetup:
    folders: List[FolderSpec] = field(default_factory=list)
    applications: List[ApplicationSpec] = field(default_factory=list)


@dataclass(frozen=True)
class RolePolicy:
    role_values: List[str] = field(default_factory=list)
    admin_role_value: str = "Admin"
    default_permission_role_values: List[str] = field(default_factory=list)
    protected_app_role_values: Dict[str, List[str]] = field(default_factory=dict)

    def __post_init__(self):
        role_values = [str(role) for role in self.role_values]
        admin_role_value = str(self.admin_role_value)
        default_roles = [str(role) for role in self.default_permission_role_values]
        protected = {
            str(app_id): [str(role) for role in role_values]
            for app_id, role_values in self.protected_app_role_values.items()
        }
        object.__setattr__(self, "role_values", role_values)
        object.__setattr__(self, "admin_role_value", admin_role_value)
        object.__setattr__(self, "default_permission_role_values", default_roles)
        object.__setattr__(self, "protected_app_role_values", protected)

        known_roles = set(role_values)
        if role_values and admin_role_value not in known_roles:
            raise ValueError(
                f"RolePolicy admin_role_value '{admin_role_value}' must be present in role_values"
            )
        if any(role not in known_roles for role in default_roles):
            raise ValueError("RolePolicy default_permission_role_values must all be present in role_values")
        for app_id, required_roles in protected.items():
            if any(role not in known_roles for role in required_roles):
                raise ValueError(
                    f"RolePolicy protected_app_role_values for '{app_id}' contains unknown roles"
                )


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    service_type: Type
    required: bool = True
    description: str = ""
    builder: Optional[Callable] = field(default=None, compare=False)


@dataclass(frozen=True)
class SystemMetadata:
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    settings_root: str = os.path.join("storage", "settings")
    translations_root: str = os.path.join("storage", "translations")


@dataclass(frozen=True)
class SettingsSpec:
    name: str
    serializer: ISettingsSerializer
    storage_key: str
    required: bool = True
