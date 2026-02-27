"""
Unit tests for BaseJsonSettingsRepository.

Covered:
- No file_path → returns serializer default (no disk access)
- Missing file → creates file with defaults and returns them
- Existing valid JSON → deserializes via serializer.from_dict
- Corrupt JSON (JSONDecodeError) → returns default, does NOT raise
- Empty file → treated as corrupt, returns default, does NOT raise
- save() writes serialized JSON to disk
- save() creates intermediate directories
- save() raises SettingsSaveError when no file_path is set
- exists() returns False when no path, file missing, or file present
"""
import json
import os
import tempfile
import unittest
from dataclasses import dataclass
from typing import Any, Dict

from src.engine.repositories.interfaces import (
    ISettingsSerializer,
    SettingsSaveError,
)
from src.engine.repositories.json.base_json_settings_repository import (
    BaseJsonSettingsRepository,
)


# ── Minimal test double ────────────────────────────────────────────────────────

@dataclass
class _Config:
    name: str = "default"
    count: int = 0


class _Serializer(ISettingsSerializer[_Config]):
    @property
    def settings_type(self) -> str:
        return "test_config"

    def get_default(self) -> _Config:
        return _Config()

    def to_dict(self, settings: _Config) -> Dict[str, Any]:
        return {"name": settings.name, "count": settings.count}

    def from_dict(self, data: Dict[str, Any]) -> _Config:
        return _Config(
            name=data.get("name", "default"),
            count=data.get("count", 0),
        )


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestLoadNoFilePath(unittest.TestCase):

    def test_returns_default_when_no_file_path(self):
        repo = BaseJsonSettingsRepository(serializer=_Serializer(), file_path=None)
        result = repo.load()
        self.assertIsInstance(result, _Config)
        self.assertEqual(result.name, "default")


class TestLoadMissingFile(unittest.TestCase):

    def test_creates_file_with_defaults_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cfg.json")
            repo = BaseJsonSettingsRepository(serializer=_Serializer(), file_path=path)

            result = repo.load()

            self.assertTrue(os.path.exists(path))
            self.assertIsInstance(result, _Config)
            self.assertEqual(result.name, "default")

    def test_created_file_contains_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cfg.json")
            repo = BaseJsonSettingsRepository(serializer=_Serializer(), file_path=path)
            repo.load()

            with open(path) as f:
                data = json.load(f)
            self.assertIn("name", data)
            self.assertIn("count", data)


class TestLoadExistingFile(unittest.TestCase):

    def test_loads_and_deserializes_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cfg.json")
            with open(path, "w") as f:
                json.dump({"name": "loaded", "count": 42}, f)

            repo = BaseJsonSettingsRepository(serializer=_Serializer(), file_path=path)
            result = repo.load()

            self.assertEqual(result.name, "loaded")
            self.assertEqual(result.count, 42)

    def test_partial_json_uses_from_dict_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cfg.json")
            with open(path, "w") as f:
                json.dump({"name": "partial"}, f)  # missing "count"

            repo = BaseJsonSettingsRepository(serializer=_Serializer(), file_path=path)
            result = repo.load()

            self.assertEqual(result.name, "partial")
            self.assertEqual(result.count, 0)  # from_dict default


class TestLoadCorruptFile(unittest.TestCase):

    def test_corrupt_json_returns_default_without_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cfg.json")
            with open(path, "w") as f:
                f.write("{ this is not : valid json !!!")

            repo = BaseJsonSettingsRepository(serializer=_Serializer(), file_path=path)
            result = repo.load()   # must not raise

            self.assertIsInstance(result, _Config)
            self.assertEqual(result.name, "default")

    def test_empty_file_returns_default_without_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cfg.json")
            open(path, "w").close()  # create empty file

            repo = BaseJsonSettingsRepository(serializer=_Serializer(), file_path=path)
            result = repo.load()   # must not raise

            self.assertIsInstance(result, _Config)
            self.assertEqual(result.name, "default")


class TestSave(unittest.TestCase):

    def test_save_writes_json_to_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cfg.json")
            repo = BaseJsonSettingsRepository(serializer=_Serializer(), file_path=path)

            repo.save(_Config(name="saved", count=7))

            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data["name"], "saved")
            self.assertEqual(data["count"], 7)

    def test_save_roundtrip_via_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cfg.json")
            repo = BaseJsonSettingsRepository(serializer=_Serializer(), file_path=path)

            repo.save(_Config(name="roundtrip", count=99))
            result = repo.load()

            self.assertEqual(result.name, "roundtrip")
            self.assertEqual(result.count, 99)

    def test_save_creates_intermediate_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a", "b", "c", "cfg.json")
            repo = BaseJsonSettingsRepository(serializer=_Serializer(), file_path=path)

            repo.save(_Config(name="deep"))

            self.assertTrue(os.path.exists(path))

    def test_save_raises_settings_save_error_when_no_file_path(self):
        repo = BaseJsonSettingsRepository(serializer=_Serializer(), file_path=None)

        with self.assertRaises(SettingsSaveError):
            repo.save(_Config())


class TestExists(unittest.TestCase):

    def test_exists_false_when_no_file_path(self):
        repo = BaseJsonSettingsRepository(serializer=_Serializer(), file_path=None)
        self.assertFalse(repo.exists())

    def test_exists_false_when_file_not_on_disk(self):
        repo = BaseJsonSettingsRepository(
            serializer=_Serializer(), file_path="/tmp/does_not_exist_xyz.json"
        )
        self.assertFalse(repo.exists())

    def test_exists_true_when_file_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cfg.json")
            open(path, "w").close()

            repo = BaseJsonSettingsRepository(serializer=_Serializer(), file_path=path)
            self.assertTrue(repo.exists())


if __name__ == "__main__":
    unittest.main()
