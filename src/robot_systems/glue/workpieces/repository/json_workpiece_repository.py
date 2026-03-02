import json
import logging
import os
import shutil
from datetime import datetime
from typing import List, Optional


from src.robot_systems.glue.workpieces.model.glue_workpiece import GlueWorkpiece
from src.robot_systems.glue.workpieces.repository.i_workpiece_repository import IWorkpieceRepository

_logger = logging.getLogger(__name__)


class JsonWorkpieceRepository(IWorkpieceRepository):
    """
    Stores workpieces as JSON files using the structure:
        <root>/<YYYY-MM-DD>/<YYYY-MM-DD_HH-MM-SS-ffffff>/<timestamp>_workpiece.json
    """

    def __init__(self, storage_root: str):
        self._root = os.path.abspath(storage_root)
        os.makedirs(self._root, exist_ok=True)
        _logger.info("JsonWorkpieceRepository: root → %s", self._root)

    # ── IWorkpieceRepository ─────────────────────────────────────────

    def save(self, workpiece) -> str:

        serialized  = GlueWorkpiece.serialize(workpiece)
        file_path   = self._build_path()

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(serialized, f, indent=2, default=str)

        _logger.info("Workpiece saved → %s", file_path)
        return file_path

    def load(self, workpiece_id: str):

        path = self._find_file(workpiece_id)
        if path is None:
            _logger.warning("Workpiece '%s' not found", workpiece_id)
            return None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return GlueWorkpiece.deserialize(data)

    def list_all(self) -> List[dict]:
        results = []
        for date_dir in sorted(os.listdir(self._root)):
            date_path = os.path.join(self._root, date_dir)
            if not os.path.isdir(date_path):
                continue
            for ts_dir in sorted(os.listdir(date_path)):
                ts_path = os.path.join(date_path, ts_dir)
                if not os.path.isdir(ts_path):
                    continue
                file_path = os.path.join(ts_path, f"{ts_dir}_workpiece.json")
                if not os.path.exists(file_path):
                    continue
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    results.append({
                        "id":    ts_dir,
                        "name":  data.get("name", ""),
                        "date":  date_dir,
                        "path":  file_path,
                    })
                except Exception as exc:
                    _logger.warning("Could not read workpiece at %s: %s", file_path, exc)
        return results

    def delete(self, workpiece_id: str) -> bool:
        path = self._find_file(workpiece_id)
        if path is None:
            return False
        folder = os.path.dirname(path)
        try:
            shutil.rmtree(folder)
            _logger.info("Deleted workpiece folder: %s", folder)
            return True
        except Exception as exc:
            _logger.error("Failed to delete workpiece '%s': %s", workpiece_id, exc)
            return False

    # ── helpers ──────────────────────────────────────────────────────

    def _build_path(self) -> str:
        now      = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        ts_str   = now.strftime("%Y-%m-%d_%H-%M-%S-%f")
        folder   = os.path.join(self._root, date_str, ts_str)
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, f"{ts_str}_workpiece.json")

    def _find_file(self, workpiece_id: str) -> Optional[str]:
        """Scan root to locate the JSON file for a given timestamp-id."""
        for date_dir in os.listdir(self._root):
            candidate = os.path.join(
                self._root, date_dir, workpiece_id, f"{workpiece_id}_workpiece.json"
            )
            if os.path.exists(candidate):
                return candidate
        return None