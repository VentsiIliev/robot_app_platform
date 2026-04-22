import json
import logging
import os
import shutil
from datetime import datetime
from typing import List, Optional

import numpy as np

from src.robot_systems.glue.domain.workpieces.workpiece_thumbnail import generate_thumbnail_bytes

_logger = logging.getLogger(__name__)


def _numpy_to_python(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {key: _numpy_to_python(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_numpy_to_python(item) for item in obj]
    return obj


class JsonPaintWorkpieceRepository:
    def __init__(self, storage_root: str):
        self._root = os.path.abspath(storage_root)
        os.makedirs(self._root, exist_ok=True)
        _logger.info("JsonPaintWorkpieceRepository: root -> %s", self._root)

    def save(self, workpiece: dict) -> str:
        serialized = _numpy_to_python(workpiece)
        file_path = self._build_path()
        folder = os.path.dirname(file_path)
        ts = os.path.basename(folder)
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(serialized, handle, indent=2)
        thumb_bytes = generate_thumbnail_bytes(serialized)
        if thumb_bytes:
            thumb_path = os.path.join(folder, f"{ts}_thumbnail.png")
            with open(thumb_path, "wb") as handle:
                handle.write(thumb_bytes)
        return file_path

    def list_all(self) -> List[dict]:
        records: List[dict] = []
        for date_dir in sorted(os.listdir(self._root)):
            date_path = os.path.join(self._root, date_dir)
            if not os.path.isdir(date_path):
                continue
            for storage_id in sorted(os.listdir(date_path)):
                storage_path = os.path.join(date_path, storage_id)
                if not os.path.isdir(storage_path):
                    continue
                json_path = os.path.join(storage_path, f"{storage_id}_workpiece.json")
                if not os.path.exists(json_path):
                    continue
                try:
                    with open(json_path, "r", encoding="utf-8") as handle:
                        raw = json.load(handle)
                    thumb_path = os.path.join(storage_path, f"{storage_id}_thumbnail.png")
                    records.append(
                        {
                            "id": storage_id,
                            "name": raw.get("name", ""),
                            "date": date_dir,
                            "path": json_path,
                            "thumbnail_path": thumb_path if os.path.exists(thumb_path) else None,
                        }
                    )
                except Exception as exc:
                    _logger.warning("Could not read paint workpiece %s: %s", json_path, exc)
        return records

    def delete(self, storage_id: str) -> bool:
        path = self._find_file(storage_id)
        if path is None:
            return False
        try:
            shutil.rmtree(os.path.dirname(path))
            return True
        except Exception as exc:
            _logger.error("Failed to delete paint workpiece %s: %s", storage_id, exc)
            return False

    def get_thumbnail_bytes(self, storage_id: str) -> Optional[bytes]:
        path = self._find_file(storage_id)
        if path is None:
            return None
        folder = os.path.dirname(path)
        thumb_path = os.path.join(folder, f"{storage_id}_thumbnail.png")
        if os.path.exists(thumb_path):
            with open(thumb_path, "rb") as handle:
                return handle.read()
        try:
            with open(path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            thumb_bytes = generate_thumbnail_bytes(raw)
            if thumb_bytes:
                with open(thumb_path, "wb") as handle:
                    handle.write(thumb_bytes)
            return thumb_bytes
        except Exception:
            _logger.exception("Failed to generate thumbnail for %s", storage_id)
            return None

    def workpiece_id_exists(self, workpiece_id: str) -> bool:
        for meta in self.list_all():
            path = meta.get("path")
            if not path:
                continue
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    raw = json.load(handle)
                if str(raw.get("workpieceId", "")).strip() == str(workpiece_id).strip():
                    return True
            except Exception:
                _logger.debug("Failed while checking workpieceId existence", exc_info=True)
        return False

    def update(self, storage_id: str, data: dict) -> str:
        path = self._find_file(storage_id)
        if path is None:
            raise FileNotFoundError(f"Paint workpiece '{storage_id}' not found")
        serialized = _numpy_to_python(data)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(serialized, handle, indent=2)
        thumb_bytes = generate_thumbnail_bytes(serialized)
        if thumb_bytes:
            thumb_path = os.path.join(os.path.dirname(path), f"{storage_id}_thumbnail.png")
            with open(thumb_path, "wb") as handle:
                handle.write(thumb_bytes)
        return path

    def load_raw(self, storage_id: str) -> Optional[dict]:
        path = self._find_file(storage_id)
        if path is None:
            return None
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _build_path(self) -> str:
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        storage_id = now.strftime("%Y-%m-%d_%H-%M-%S-%f")
        folder = os.path.join(self._root, date_str, storage_id)
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, f"{storage_id}_workpiece.json")

    def _find_file(self, storage_id: str) -> Optional[str]:
        for date_dir in os.listdir(self._root):
            candidate = os.path.join(self._root, date_dir, storage_id, f"{storage_id}_workpiece.json")
            if os.path.exists(candidate):
                return candidate
        return None
