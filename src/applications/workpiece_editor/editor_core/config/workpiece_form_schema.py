from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class FieldIcon:
    """
    Declarative icon descriptor — resolved to a QPixmap/QIcon at render time.
    Use the factory methods; never construct directly.
    """
    kind:  str        # "path" | "qta" | "none"
    value: str = ""
    color: str = "#ffffff"   # only relevant when kind == "qta"

    @staticmethod
    def none() -> "FieldIcon":
        return FieldIcon(kind="none")

    @staticmethod
    def from_path(path: str) -> "FieldIcon":
        return FieldIcon(kind="path", value=path)

    @staticmethod
    def from_qta(icon_id: str, color: str = "#333333") -> "FieldIcon":
        return FieldIcon(kind="qta", value=icon_id, color=color)


@dataclass
class WorkpieceFormFieldSpec:
    key:         str
    label:       str
    field_type:  str
    mandatory:   bool = False
    options:     Optional[List[Any]] = None
    icon:        FieldIcon = field(default_factory=FieldIcon.none)
    placeholder: str = ""
    default_value: Any = None
    visible:     bool = True


@dataclass
class WorkpieceFormSchema:
    fields:            List[WorkpieceFormFieldSpec]
    id_key:            str = "workpieceId"
    combo_key:         str = ""
    contour_key:       str = "contour"
    spray_pattern_key: str = "sprayPattern"
    editor_layer_config: Any = None

    def get_required_keys(self) -> List[str]:
        return [f.key for f in self.fields if f.mandatory]

    def get_field(self, key: str) -> Optional[WorkpieceFormFieldSpec]:
        return next((f for f in self.fields if f.key == key), None)

    def get_options(self, key: str) -> List[Any]:
        fd = self.get_field(key)
        return list(fd.options) if fd and fd.options else []
