import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

@dataclass
class Glue:
    name: str
    description: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        self.name = self.name.strip()
        self.description = self.description.strip() if self.description else ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Glue':
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            glue_id=data.get("id"),
        )

    def __init__(self, name: str, description: str = "", glue_id: str = None):
        self.id = glue_id if glue_id else str(uuid.uuid4())
        self.name = name.strip()
        self.description = description.strip() if description else ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
        }


@dataclass
class GlueCatalog:
    glue_types: List[Glue] = field(default_factory=list)

    def get_by_id(self, glue_id: str) -> Optional[Glue]:
        return next((g for g in self.glue_types if g.id == glue_id), None)

    def get_by_name(self, name: str) -> Optional[Glue]:
        return next((g for g in self.glue_types if g.name.lower() == name.lower()), None)

    def get_all_names(self) -> List[str]:
        return [g.name for g in self.glue_types]

    def get_all_ids(self) -> List[str]:
        return [g.id for g in self.glue_types]

    def add(self, glue: Glue) -> None:
        if self.get_by_name(glue.name) is not None:
            raise ValueError(f"Glue type '{glue.name}' already exists")
        self.glue_types.append(glue)

    def remove_by_id(self, glue_id: str) -> bool:
        before = len(self.glue_types)
        self.glue_types = [g for g in self.glue_types if g.id != glue_id]
        return len(self.glue_types) < before

    @property
    def count(self) -> int:
        return len(self.glue_types)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GlueCatalog':
        return cls(
            glue_types=[Glue.from_dict(g) for g in data.get("glue_types", [])]
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"glue_types": [g.to_dict() for g in self.glue_types]}


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------

_DEFAULT_CATALOG = GlueCatalog(
    glue_types=[
        Glue(name="Type A", description="Standard glue type A"),
        Glue(name="Type B", description="Standard glue type B"),
    ]
)


class GlueCatalogSerializer(ISettingsSerializer[GlueCatalog]):

    @property
    def settings_type(self) -> str:
        return "glue_catalog"

    def get_default(self) -> GlueCatalog:
        return _DEFAULT_CATALOG

    def to_dict(self, settings: GlueCatalog) -> Dict[str, Any]:
        return settings.to_dict()

    def from_dict(self, data: Dict[str, Any]) -> GlueCatalog:
        return GlueCatalog.from_dict(data)