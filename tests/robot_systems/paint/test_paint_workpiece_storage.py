from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

from src.robot_systems.paint.domain.workpieces.repository.json_paint_workpiece_repository import (
    JsonPaintWorkpieceRepository,
    _numpy_to_python,
)
from src.robot_systems.paint.domain.workpieces.service.paint_workpiece_service import (
    PaintWorkpieceService,
)


class TestNumpyToPython(unittest.TestCase):
    def test_converts_arrays_recursively(self) -> None:
        converted = _numpy_to_python(
            {
                "arr": np.array([[1, 2], [3, 4]]),
                "nested": [{"value": np.array([5.0, 6.0])}],
            }
        )

        self.assertEqual(converted["arr"], [[1, 2], [3, 4]])
        self.assertEqual(converted["nested"][0]["value"], [5.0, 6.0])


class TestJsonPaintWorkpieceRepository(unittest.TestCase):
    def test_save_list_load_update_thumbnail_delete_and_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch(
                "src.robot_systems.paint.domain.workpieces.repository.json_paint_workpiece_repository.generate_thumbnail_bytes",
                side_effect=[b"png", b"png2", b"regen"],
            ), patch(
                "src.robot_systems.paint.domain.workpieces.repository.json_paint_workpiece_repository.datetime"
            ) as dt:
                fixed_now = MagicMock()
                fixed_now.strftime.side_effect = [
                    "2026-05-06",
                    "2026-05-06_12-00-00-000001",
                ]
                dt.now.return_value = fixed_now
                repo = JsonPaintWorkpieceRepository(tmp)

                saved_path = repo.save(
                    {
                        "workpieceId": "wp-1",
                        "name": "Original",
                        "contour": np.array([[[1.0, 2.0]]]),
                    }
                )

                self.assertTrue(saved_path.endswith("_workpiece.json"))
                saved_file = Path(saved_path)
                self.assertTrue(saved_file.exists())
                saved_data = json.loads(saved_file.read_text(encoding="utf-8"))
                self.assertEqual(saved_data["contour"], [[[1.0, 2.0]]])

                records = repo.list_all()
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]["id"], "2026-05-06_12-00-00-000001")
                self.assertEqual(records[0]["name"], "Original")
                self.assertTrue(records[0]["thumbnail_path"].endswith("_thumbnail.png"))

                storage_id = records[0]["id"]
                self.assertEqual(repo.load_raw(storage_id)["workpieceId"], "wp-1")
                self.assertTrue(repo.workpiece_id_exists("wp-1"))
                self.assertFalse(repo.workpiece_id_exists("missing"))

                updated_path = repo.update(
                    storage_id,
                    {"workpieceId": "wp-1", "name": "Updated"},
                )
                self.assertEqual(updated_path, saved_path)
                self.assertEqual(repo.load_raw(storage_id)["name"], "Updated")

                thumb_path = saved_file.parent / f"{storage_id}_thumbnail.png"
                self.assertEqual(repo.get_thumbnail_bytes(storage_id), b"png2")
                thumb_path.unlink()
                self.assertEqual(repo.get_thumbnail_bytes(storage_id), b"regen")
                self.assertTrue(thumb_path.exists())

                self.assertTrue(repo.delete(storage_id))
                self.assertFalse(repo.delete(storage_id))
                self.assertIsNone(repo.load_raw(storage_id))
                self.assertIsNone(repo.get_thumbnail_bytes(storage_id))

    def test_list_all_skips_invalid_entries_and_missing_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = JsonPaintWorkpieceRepository(tmp)
            date_dir = Path(tmp) / "2026-05-06"
            (date_dir / "missing").mkdir(parents=True)
            bad_dir = date_dir / "bad"
            bad_dir.mkdir(parents=True)
            (bad_dir / "bad_workpiece.json").write_text("{bad json", encoding="utf-8")

            self.assertEqual(repo.list_all(), [])

    def test_update_missing_storage_id_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = JsonPaintWorkpieceRepository(tmp)
            with self.assertRaisesRegex(FileNotFoundError, "not found"):
                repo.update("missing", {"name": "x"})


class TestPaintWorkpieceService(unittest.TestCase):
    def test_service_delegates_success_paths(self) -> None:
        repo = MagicMock()
        repo.save.return_value = "/tmp/file.json"
        repo.list_all.return_value = [{"id": "a"}]
        repo.delete.return_value = True
        repo.get_thumbnail_bytes.return_value = b"img"
        repo.workpiece_id_exists.return_value = True
        repo.update.return_value = "/tmp/file.json"
        repo.load_raw.return_value = {"name": "x"}
        service = PaintWorkpieceService(repo)

        self.assertEqual(service.save({"name": "x"}), (True, "/tmp/file.json"))
        self.assertEqual(service.list_all(), [{"id": "a"}])
        self.assertEqual(service.delete("a"), (True, "Deleted"))
        self.assertEqual(service.get_thumbnail_bytes("a"), b"img")
        self.assertTrue(service.workpiece_id_exists("wp-1"))
        self.assertEqual(service.update("a", {"name": "y"}), (True, "/tmp/file.json"))
        self.assertEqual(service.load_raw("a"), {"name": "x"})

    def test_service_handles_repository_failures(self) -> None:
        repo = MagicMock()
        repo.save.side_effect = RuntimeError("save failed")
        repo.list_all.side_effect = RuntimeError("list failed")
        repo.delete.side_effect = RuntimeError("delete failed")
        repo.get_thumbnail_bytes.side_effect = RuntimeError("thumb failed")
        repo.workpiece_id_exists.side_effect = RuntimeError("exists failed")
        repo.update.side_effect = RuntimeError("update failed")
        repo.load_raw.side_effect = RuntimeError("load failed")
        service = PaintWorkpieceService(repo)

        self.assertEqual(service.save({}), (False, "save failed"))
        self.assertEqual(service.list_all(), [])
        self.assertEqual(service.delete("a"), (False, "delete failed"))
        self.assertIsNone(service.get_thumbnail_bytes("a"))
        self.assertFalse(service.workpiece_id_exists("wp-1"))
        self.assertEqual(service.update("a", {}), (False, "update failed"))
        self.assertIsNone(service.load_raw("a"))

    def test_delete_reports_not_found_when_repository_returns_false(self) -> None:
        repo = MagicMock()
        repo.delete.return_value = False
        service = PaintWorkpieceService(repo)

        self.assertEqual(service.delete("missing"), (False, "Workpiece 'missing' not found"))


if __name__ == "__main__":
    unittest.main()
