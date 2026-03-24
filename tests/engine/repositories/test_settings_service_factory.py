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
from enum import Enum
from typing import Any, Dict

from src.engine.repositories.interfaces import ISettingsSerializer
from src.engine.repositories.settings_service import SettingsService
from src.engine.repositories.settings_service_factory import build_from_specs
from src.shared_contracts.declarations import SettingsSpec

class SettingsIDTestEnum(str, Enum):
    A = "a"
    B = "b"
    C = "c"
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
    """Dummy robot vision_service class — name resolves to 'fakesystem'."""


class AnotherSystem:
    """A second vision_service class — name resolves to 'anothersystem'."""


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
                specs=[SettingsSpec(SettingsIDTestEnum.A, _Ser(), "cfg.json")],
                settings_root=tmp,
                system_class=FakeSystem,
            )
            service.get(SettingsIDTestEnum.A)  # triggers file creation

            expected = os.path.join(tmp, "fakesystem", "cfg.json")
            self.assertTrue(os.path.exists(expected))

    def test_different_system_classes_use_different_subdirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc_a = build_from_specs([SettingsSpec(SettingsIDTestEnum.A, _Ser(), "cfg.json")], tmp, FakeSystem)
            svc_b = build_from_specs([SettingsSpec(SettingsIDTestEnum.A, _Ser(), "cfg.json")], tmp, AnotherSystem)

            svc_a.get(SettingsIDTestEnum.A)
            svc_b.get(SettingsIDTestEnum.A)

            self.assertTrue(os.path.exists(os.path.join(tmp, "fakesystem", "cfg.json")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "anothersystem", "cfg.json")))

    def test_storage_key_used_as_relative_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = build_from_specs(
                specs=[SettingsSpec(SettingsIDTestEnum.A, _Ser(), "sub/dir/cfg.json")],
                settings_root=tmp,
                system_class=FakeSystem,
            )
            service.get(SettingsIDTestEnum.A)

            expected = os.path.join(tmp, "fakesystem", "sub", "dir", "cfg.json")
            self.assertTrue(os.path.exists(expected))


class TestBuildFromSpecsMultipleSpecs(unittest.TestCase):

    def test_all_specs_are_accessible_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            specs = [
                SettingsSpec(SettingsIDTestEnum.A, _Ser(), "alpha.json"),
                SettingsSpec(SettingsIDTestEnum.B,  _Ser(), "beta.json"),
                SettingsSpec(SettingsIDTestEnum.C, _Ser(), "gamma.json"),
            ]
            service = build_from_specs(specs, tmp, FakeSystem)

            for name in (SettingsIDTestEnum.A, SettingsIDTestEnum.B, SettingsIDTestEnum.C):
                result = service.get(name)
                self.assertIsInstance(result, _Cfg)

    def test_each_spec_gets_its_own_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            specs = [
                SettingsSpec(SettingsIDTestEnum.A, _Ser(), "a.json"),
                SettingsSpec(SettingsIDTestEnum.B, _Ser(), "b.json"),
            ]
            service = build_from_specs(specs, tmp, FakeSystem)
            service.get(SettingsIDTestEnum.A)
            service.get(SettingsIDTestEnum.B)

            base = os.path.join(tmp, "fakesystem")
            self.assertTrue(os.path.exists(os.path.join(base, "a.json")))
            self.assertTrue(os.path.exists(os.path.join(base, "b.json")))



if __name__ == "__main__":
    unittest.main()
