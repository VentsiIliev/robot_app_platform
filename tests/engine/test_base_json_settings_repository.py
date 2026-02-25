import json
import unittest
from dataclasses import dataclass
from typing import Dict, Any
from unittest.mock import MagicMock, mock_open, patch

from src.engine.repositories.interfaces import (
    ISettingsSerializer,
    SettingsLoadError,
    SettingsSaveError,
)
from src.engine.repositories.json import BaseJsonSettingsRepository


@dataclass
class _FakeSettings:
    value: int = 42


class _FakeSerializer(ISettingsSerializer[_FakeSettings]):
    @property
    def settings_type(self) -> str:
        return "fake"

    def get_default(self) -> _FakeSettings:
        return _FakeSettings()

    def to_dict(self, settings: _FakeSettings) -> Dict[str, Any]:
        return {"value": settings.value}

    def from_dict(self, data: Dict[str, Any]) -> _FakeSettings:
        return _FakeSettings(value=data["value"])


class TestBaseJsonSettingsRepository(unittest.TestCase):

    def _make_repo(self, file_path=None):
        return BaseJsonSettingsRepository(
            serializer=_FakeSerializer(), file_path=file_path
        )

    # ------------------------------------------------------------------
    # load
    # ------------------------------------------------------------------

    def test_load_returns_default_when_no_file_path(self):
        repo = self._make_repo()
        result = repo.load()
        self.assertEqual(result, _FakeSettings())

    @patch("src.engine.repositories.json.base_json_settings_repository.os.path.exists", return_value=False)
    @patch("src.engine.repositories.json.base_json_settings_repository.os.makedirs")
    @patch("builtins.open", mock_open())
    def test_load_creates_default_file_when_missing(self, mock_makedirs, mock_exists):
        repo = self._make_repo("/some/dir/settings.json")
        result = repo.load()
        self.assertEqual(result, _FakeSettings())
        mock_makedirs.assert_called_once_with("/some/dir", exist_ok=True)

    @patch("src.engine.repositories.json.base_json_settings_repository.os.path.exists", return_value=True)
    def test_load_reads_existing_file(self, _mock_exists):
        data = json.dumps({"value": 99})
        repo = self._make_repo("/some/settings.json")
        with patch("builtins.open", mock_open(read_data=data)):
            result = repo.load()
        self.assertEqual(result.value, 99)

    @patch("src.engine.repositories.json.base_json_settings_repository.os.path.exists", return_value=True)
    def test_load_returns_default_on_json_decode_error(self, _mock_exists):
        repo = self._make_repo("/some/settings.json")
        with patch("builtins.open", mock_open(read_data="not-json")):
            result = repo.load()
        self.assertEqual(result, _FakeSettings())

    @patch("src.engine.repositories.json.base_json_settings_repository.os.path.exists", return_value=True)
    def test_load_raises_settings_load_error_on_unexpected_exception(self, _mock_exists):
        serializer = _FakeSerializer()
        serializer.from_dict = MagicMock(side_effect=RuntimeError("boom"))
        repo = BaseJsonSettingsRepository(serializer=serializer, file_path="/f.json")
        with patch("builtins.open", mock_open(read_data='{"value": 1}')):
            with self.assertRaises(SettingsLoadError):
                repo.load()

    # ------------------------------------------------------------------
    # save
    # ------------------------------------------------------------------

    def test_save_raises_when_no_file_path(self):
        repo = self._make_repo()
        with self.assertRaises(SettingsSaveError):
            repo.save(_FakeSettings())

    @patch("src.engine.repositories.json.base_json_settings_repository.os.makedirs")
    @patch("builtins.open", mock_open())
    def test_save_writes_file(self, mock_makedirs):
        repo = self._make_repo("/dir/settings.json")
        repo.save(_FakeSettings(value=7))
        mock_makedirs.assert_called_once_with("/dir", exist_ok=True)

    @patch("src.engine.repositories.json.base_json_settings_repository.os.makedirs", side_effect=OSError("no perm"))
    def test_save_raises_settings_save_error_on_write_failure(self, _mock_makedirs):
        repo = self._make_repo("/dir/settings.json")
        with self.assertRaises(SettingsSaveError):
            repo.save(_FakeSettings())

    # ------------------------------------------------------------------
    # exists
    # ------------------------------------------------------------------

    def test_exists_false_when_no_path(self):
        self.assertFalse(self._make_repo().exists())

    @patch("src.engine.repositories.json.base_json_settings_repository.os.path.exists", return_value=True)
    def test_exists_true_when_file_present(self, _):
        self.assertTrue(self._make_repo("/some/settings.json").exists())

    @patch("src.engine.repositories.json.base_json_settings_repository.os.path.exists", return_value=False)
    def test_exists_false_when_file_absent(self, _):
        self.assertFalse(self._make_repo("/some/settings.json").exists())


if __name__ == "__main__":
    unittest.main()

