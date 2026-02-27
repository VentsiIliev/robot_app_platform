"""
Unit tests for settings_service_factory.build_from_specs() in isolation.

Covered:
- Returns a SettingsService instance
- Lowercased class name used as storage subdirectory
- One repository created per SettingsSpec
- Multiple specs all accessible by name
- Empty spec list produces a service that raises KeyError for any key
- Absolute settings_root is used directly (no extra path resolution)
"""
import os
import tempfile
import unittest
from dataclasses import dataclass
from typing import Any, Dict

from src.engine.repositories.interfaces import ISettingsSerializer
from src.engine.repositories.settings_service import SettingsService
from src.engine.repositories.settings_service_factory import build_from_specs
from src.robot_systems.base_robot_system import SettingsSpec


# ── Minimal test doubles ───────────────────────────────────────────────────────

@dataclass
class _Cfg:
    value: str = "default"


class _Ser(ISettingsSerializer[_Cfg]):
    @property
    def settings_type(self) -> str:
        return "cfg"

    def get_default(self) -> _Cfg:
        return _Cfg()

    def to_dict(self, s: _Cfg) -> Dict[str, Any]:
        return {"value": s.value}

    def from_dict(self, d: Dict[str, Any]) -> _Cfg:
        return _Cfg(value=d.get("value", "default"))


class FakeSystem:
    """Dummy robot system class — name resolves to 'fakesystem'."""


class AnotherSystem:
    """A second system class — name resolves to 'anothersystem'."""


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestBuildFromSpecsReturnType(unittest.TestCase):

    def test_returns_settings_service_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = build_from_specs(
                specs=[SettingsSpec("cfg", _Ser(), "cfg.json")],
                settings_root=tmp,
                system_class=FakeSystem,
            )
            self.assertIsInstance(service, SettingsService)


class TestBuildFromSpecsDirectoryNaming(unittest.TestCase):

    def test_uses_lowercased_class_name_as_subdirectory(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = build_from_specs(
                specs=[SettingsSpec("cfg", _Ser(), "cfg.json")],
                settings_root=tmp,
                system_class=FakeSystem,
            )
            service.get("cfg")  # triggers file creation

            expected = os.path.join(tmp, "fakesystem", "cfg.json")
            self.assertTrue(os.path.exists(expected))

    def test_different_system_classes_use_different_subdirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc_a = build_from_specs([SettingsSpec("cfg", _Ser(), "cfg.json")], tmp, FakeSystem)
            svc_b = build_from_specs([SettingsSpec("cfg", _Ser(), "cfg.json")], tmp, AnotherSystem)

            svc_a.get("cfg")
            svc_b.get("cfg")

            self.assertTrue(os.path.exists(os.path.join(tmp, "fakesystem", "cfg.json")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "anothersystem", "cfg.json")))

    def test_storage_key_used_as_relative_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = build_from_specs(
                specs=[SettingsSpec("cfg", _Ser(), "sub/dir/cfg.json")],
                settings_root=tmp,
                system_class=FakeSystem,
            )
            service.get("cfg")

            expected = os.path.join(tmp, "fakesystem", "sub", "dir", "cfg.json")
            self.assertTrue(os.path.exists(expected))


class TestBuildFromSpecsMultipleSpecs(unittest.TestCase):

    def test_all_specs_are_accessible_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            specs = [
                SettingsSpec("alpha", _Ser(), "alpha.json"),
                SettingsSpec("beta",  _Ser(), "beta.json"),
                SettingsSpec("gamma", _Ser(), "gamma.json"),
            ]
            service = build_from_specs(specs, tmp, FakeSystem)

            for name in ("alpha", "beta", "gamma"):
                result = service.get(name)
                self.assertIsInstance(result, _Cfg)

    def test_each_spec_gets_its_own_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            specs = [
                SettingsSpec("a", _Ser(), "a.json"),
                SettingsSpec("b", _Ser(), "b.json"),
            ]
            service = build_from_specs(specs, tmp, FakeSystem)
            service.get("a")
            service.get("b")

            base = os.path.join(tmp, "fakesystem")
            self.assertTrue(os.path.exists(os.path.join(base, "a.json")))
            self.assertTrue(os.path.exists(os.path.join(base, "b.json")))

    def test_unknown_spec_name_raises_key_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            specs = [SettingsSpec("real", _Ser(), "real.json")]
            service = build_from_specs(specs, tmp, FakeSystem)

            with self.assertRaises(KeyError):
                service.get("not_registered")


class TestBuildFromSpecsEmptySpecs(unittest.TestCase):

    def test_empty_specs_returns_settings_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = build_from_specs([], tmp, FakeSystem)
            self.assertIsInstance(service, SettingsService)

    def test_empty_specs_service_raises_key_error_for_any_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = build_from_specs([], tmp, FakeSystem)

            with self.assertRaises(KeyError):
                service.get("anything")


if __name__ == "__main__":
    unittest.main()
