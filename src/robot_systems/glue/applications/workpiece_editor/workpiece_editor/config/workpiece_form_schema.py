from __future__ import annotations
from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class WorkpieceFormFieldSpec:
    key:         str
    label:       str
    field_type:  str
    mandatory:   bool = False
    options:     Optional[List[Any]] = None
    icon_path:   str = ""
    placeholder: str = ""
    visible:     bool = True


@dataclass
class WorkpieceFormSchema:
    fields:  List[WorkpieceFormFieldSpec]
    id_key:  str = "workpieceId"

    def get_required_keys(self) -> List[str]:
        return [f.key for f in self.fields if f.mandatory]

    def get_field(self, key: str) -> Optional[WorkpieceFormFieldSpec]:
        return next((f for f in self.fields if f.key == key), None)

    def get_options(self, key: str) -> List[Any]:
        fd = self.get_field(key)
        return list(fd.options) if fd and fd.options else []
