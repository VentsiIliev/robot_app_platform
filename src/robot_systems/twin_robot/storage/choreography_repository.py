from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

from src.robot_systems.twin_robot.domain import ChoreographyDefinition


class ChoreographyRepository:
    """Simple JSON repository owned by the twin robot system."""

    def __init__(self, root_dir: str):
        self._root = Path(root_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, choreography_id: str) -> Path:
        safe = "".join(c for c in str(choreography_id).strip() if c.isalnum() or c in {"-", "_"})
        if not safe:
            raise ValueError("Invalid choreography ID")
        return self._root / f"{safe}.json"

    def list(self) -> List[ChoreographyDefinition]:
        result: List[ChoreographyDefinition] = []
        for path in sorted(self._root.glob("*.json")):
            try:
                result.append(self._load_path(path))
            except Exception:
                continue
        return result

    def get(self, choreography_id: str) -> ChoreographyDefinition:
        path = self._path(choreography_id)
        if not path.exists():
            raise FileNotFoundError(str(path))
        return self._load_path(path)

    def save(self, choreography: ChoreographyDefinition) -> None:
        path = self._path(choreography.choreography_id)
        tmp = path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(choreography.to_dict(), handle, indent=2)
        os.replace(tmp, path)

    def delete(self, choreography_id: str) -> None:
        path = self._path(choreography_id)
        if path.exists():
            path.unlink()

    @staticmethod
    def _load_path(path: Path) -> ChoreographyDefinition:
        with path.open("r", encoding="utf-8") as handle:
            return ChoreographyDefinition.from_dict(json.load(handle))
