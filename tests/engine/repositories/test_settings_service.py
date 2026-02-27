"""
Unit tests for SettingsService.

These are pure unit tests — all repositories are mocked, no disk I/O.

Covered:
- get() caches on first load and returns cache on subsequent calls
- reload() always calls repo.load() regardless of cache
- save() persists via repo and updates the in-memory cache
- Unknown key raises KeyError on get(), reload(), save(), and get_repo()
- get_repo() returns the repository instance
"""
import unittest
from unittest.mock import MagicMock

from src.engine.repositories.settings_service import SettingsService


def _make_repo(load_value=None):
    repo = MagicMock()
    repo.load.return_value = load_value or {"key": "value"}
    return repo


class TestSettingsServiceUnknownKey(unittest.TestCase):

    def setUp(self):
        self.service = SettingsService(repos={"existing": _make_repo()})

    def test_get_unknown_key_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.service.get("nonexistent")

    def test_reload_unknown_key_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.service.reload("nonexistent")

    def test_save_unknown_key_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.service.save("nonexistent", object())

    def test_get_repo_unknown_key_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.service.get_repo("nonexistent")

    def test_key_error_message_lists_available_keys(self):
        with self.assertRaises(KeyError) as ctx:
            self.service.get("nonexistent")
        self.assertIn("existing", str(ctx.exception))


class TestSettingsServiceCaching(unittest.TestCase):

    def test_get_calls_repo_load_on_first_access(self):
        repo = _make_repo(load_value="first")
        service = SettingsService({"cfg": repo})

        result = service.get("cfg")

        repo.load.assert_called_once()
        self.assertEqual(result, "first")

    def test_get_returns_cached_value_on_second_call(self):
        repo = _make_repo(load_value="cached")
        service = SettingsService({"cfg": repo})

        first = service.get("cfg")
        second = service.get("cfg")

        # repo.load should only be called once
        repo.load.assert_called_once()
        self.assertIs(first, second)

    def test_reload_bypasses_cache_and_calls_repo(self):
        repo = _make_repo()
        repo.load.side_effect = ["first", "second"]
        service = SettingsService({"cfg": repo})

        service.get("cfg")        # primes cache
        reloaded = service.reload("cfg")

        self.assertEqual(repo.load.call_count, 2)
        self.assertEqual(reloaded, "second")

    def test_reload_updates_cache(self):
        repo = _make_repo()
        repo.load.side_effect = ["original", "updated"]
        service = SettingsService({"cfg": repo})

        service.get("cfg")
        service.reload("cfg")
        cached = service.get("cfg")   # must not call load again

        self.assertEqual(repo.load.call_count, 2)
        self.assertEqual(cached, "updated")


class TestSettingsServiceSave(unittest.TestCase):

    def test_save_calls_repo_save(self):
        repo = _make_repo()
        service = SettingsService({"cfg": repo})
        new_value = {"updated": True}

        service.save("cfg", new_value)

        repo.save.assert_called_once_with(new_value)

    def test_save_updates_cache_so_get_skips_reload(self):
        repo = _make_repo(load_value="old")
        service = SettingsService({"cfg": repo})
        new_value = "new"

        service.save("cfg", new_value)
        result = service.get("cfg")

        # repo.load should never be called because save already populated cache
        repo.load.assert_not_called()
        self.assertEqual(result, new_value)

    def test_save_then_get_returns_saved_value(self):
        repo = _make_repo(load_value="original")
        service = SettingsService({"cfg": repo})

        service.get("cfg")           # prime cache with "original"
        service.save("cfg", "saved")
        result = service.get("cfg")

        self.assertEqual(result, "saved")


class TestSettingsServiceGetRepo(unittest.TestCase):

    def test_get_repo_returns_correct_repository(self):
        repo_a = _make_repo()
        repo_b = _make_repo()
        service = SettingsService({"a": repo_a, "b": repo_b})

        self.assertIs(service.get_repo("a"), repo_a)
        self.assertIs(service.get_repo("b"), repo_b)


if __name__ == "__main__":
    unittest.main()
