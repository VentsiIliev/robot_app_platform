from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FieldDescriptor:
    key:               str
    label:             str
    widget:            str             # "text" | "password" | "combo" | "email" | "int"
    required:          bool = True
    table_display:     bool = True     # show as column in the table
    read_only_on_edit: bool = False    # e.g. ID field
    options:           Optional[List[str]] = None   # for "combo" widget
    mask_in_table:     bool = False    # show "****" instead of real value (passwords)


@dataclass
class UserSchema:
    fields:  List[FieldDescriptor]
    id_key:  str = "id"               # which field is the primary key

    def get_table_fields(self) -> List[FieldDescriptor]:
        return [f for f in self.fields if f.table_display]

    def get_table_headers(self) -> List[str]:
        return [f.label for f in self.get_table_fields()]

    def get_filterable_labels(self) -> List[str]:
        return ["All"] + [
            f.label for f in self.get_table_fields()
            if not f.mask_in_table
        ]


class UserRecord:
    """Generic user record backed by a plain dict — works with any schema."""

    def __init__(self, data: Dict[str, Any]):
        self._data = dict(data)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def get_id(self, id_key: str) -> Any:
        return self._data.get(id_key)

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._data)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> UserRecord:
        return UserRecord(data)

    def __repr__(self) -> str:
        return f"UserRecord({self._data})"

