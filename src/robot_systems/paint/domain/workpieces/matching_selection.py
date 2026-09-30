"""Persist the paint workpieces allowed as matching candidates."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Iterable


class PaintMatchingSelection:
    """None means all saved workpieces; an empty tuple means no candidates."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._lock = RLock()
        self._selected_ids: tuple[str, ...] | None = None
        if self._path.exists():
            data = json.loads(self._path.read_text(encoding="utf-8"))
            ids = data["selected_ids"]
            self._selected_ids = None if ids is None else self._normalize(ids)

    def get_selected_ids(self) -> tuple[str, ...] | None:
        with self._lock:
            return self._selected_ids

    def set_selected_ids(self, ids: Iterable[str] | None) -> None:
        selected = None if ids is None else self._normalize(ids)
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=self._path.parent,
                    prefix=".matching_selection_", suffix=".json", delete=False,
                ) as handle:
                    temporary_path = handle.name
                    json.dump({"selected_ids": selected}, handle)
                os.replace(temporary_path, self._path)
                self._selected_ids = selected
            finally:
                if temporary_path and os.path.exists(temporary_path):
                    os.unlink(temporary_path)

    @staticmethod
    def _normalize(ids: Iterable[str]) -> tuple[str, ...]:
        if isinstance(ids, (str, bytes)):
            raise ValueError("Workpiece IDs must be a collection.")
        selected = tuple(dict.fromkeys(str(item).strip() for item in ids))
        if any(not item for item in selected):
            raise ValueError("Workpiece IDs cannot be blank.")
        return selected
