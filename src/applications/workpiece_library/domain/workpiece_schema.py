from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class WorkpieceFieldDescriptor:
    key:            str
    label:          str
    table_display:  bool = True
    detail_display: bool = True
    editable:       bool = False
    widget:         str  = "text"               # "text" | "combo"
    options:        List[Any] = field(default_factory=list)   # only for widget="combo"


@dataclass
class WorkpieceSchema:
    fields:   List[WorkpieceFieldDescriptor]
    id_key:   str = "workpieceId"
    name_key: str = "name"

    def get_table_fields(self) -> List[WorkpieceFieldDescriptor]:
        return [f for f in self.fields if f.table_display]

    def get_table_headers(self) -> List[str]:
        return [f.label for f in self.get_table_fields()]

    def get_detail_fields(self) -> List[WorkpieceFieldDescriptor]:
        return [f for f in self.fields if f.detail_display]

    def get_editable_fields(self) -> List[WorkpieceFieldDescriptor]:
        return [f for f in self.fields if f.editable]


class WorkpieceRecord:
    def __init__(self, data: Dict[str, Any]):
        self._data = dict(data)

    def get(self, key: str, default: Any = "") -> Any:
        return self._data.get(key, default)

    def get_id(self, id_key: str) -> Any:
        return self._data.get(id_key, "")

    def with_updates(self, updates: Dict[str, Any]) -> "WorkpieceRecord":
        merged = dict(self._data)
        merged.update(updates)
        return WorkpieceRecord(merged)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._data)

    def __repr__(self) -> str:
        return f"WorkpieceRecord({self._data})"
