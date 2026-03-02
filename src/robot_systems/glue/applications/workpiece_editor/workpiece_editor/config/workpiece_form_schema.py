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
    fields:            List[WorkpieceFormFieldSpec]
    id_key:            str = "workpieceId"
    # key of the dropdown field used as material/type selector in the per-segment settings panel
    material_type_key: str = ""
    # output dict keys produced by the adapter — must match what the workpiece model expects
    contour_key:       str = "contour"
    spray_pattern_key: str = "sprayPattern"

    def get_required_keys(self) -> List[str]:
        return [f.key for f in self.fields if f.mandatory]

    def get_field(self, key: str) -> Optional[WorkpieceFormFieldSpec]:
        return next((f for f in self.fields if f.key == key), None)

    def get_options(self, key: str) -> List[Any]:
        fd = self.get_field(key)
        return list(fd.options) if fd and fd.options else []
