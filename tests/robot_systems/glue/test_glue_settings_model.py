import unittest
from unittest.mock import MagicMock, call

from src.robot_systems.glue.glue_settings.model.glue_settings_model import GlueSettingsModel
from src.robot_systems.glue.glue_settings.model.mapper import GlueSettingsMapper
from src.robot_systems.glue.settings.glue import GlueSettings
from src.robot_systems.glue.settings.glue_types import Glue


def _make_service(settings=None, glue_types=None):
    svc = MagicMock()
    svc.load_settings.return_value   = settings    or GlueSettings()
    svc.load_glue_types.return_value = glue_types  or []
    return svc


class TestGlueSettingsModelLoad(unittest.TestCase):

    def test_load_calls_service(self):
        svc   = _make_service()
        model = GlueSettingsModel(svc)
        model.load()
        svc.load_settings.assert_called_once()

    def test_load_returns_settings(self):
        cfg   = GlueSettings(spray_width=9.9)
        model = GlueSettingsModel(_make_service(cfg))
        result = model.load()
        self.assertEqual(result.spray_width, 9.9)

    def test_settings_cached_after_load(self):
        cfg   = GlueSettings(motor_speed=5555.0)
        model = GlueSettingsModel(_make_service(cfg))
        model.load()
        self.assertEqual(model._settings.motor_speed, 5555.0)


class TestGlueSettingsModelSave(unittest.TestCase):

    def _loaded(self, settings=None):
        svc   = _make_service(settings)
        model = GlueSettingsModel(svc)
        model.load()
        return model, svc

    def test_save_calls_save_settings(self):
        model, svc = self._loaded()
        model.save(GlueSettingsMapper.to_flat_dict(GlueSettings()))
        svc.save_settings.assert_called_once()

    def test_save_updates_spray_width(self):
        model, svc = self._loaded(GlueSettings(spray_width=1.0))
        flat = GlueSettingsMapper.to_flat_dict(GlueSettings(spray_width=1.0))
        flat["spray_width"] = 8.8
        model.save(flat)
        saved = svc.save_settings.call_args[0][0]
        self.assertEqual(saved.spray_width, 8.8)

    def test_save_updates_spray_on(self):
        model, svc = self._loaded(GlueSettings(spray_on=False))
        flat = GlueSettingsMapper.to_flat_dict(GlueSettings(spray_on=False))
        flat["spray_on"] = True
        model.save(flat)
        saved = svc.save_settings.call_args[0][0]
        self.assertTrue(saved.spray_on)

    def test_save_updates_internal_cache(self):
        model, _ = self._loaded(GlueSettings(spray_width=1.0))
        flat = GlueSettingsMapper.to_flat_dict(GlueSettings())
        flat["spray_width"] = 7.7
        model.save(flat)
        self.assertEqual(model._settings.spray_width, 7.7)

    def test_save_without_load_uses_default_base(self):
        svc   = _make_service()
        model = GlueSettingsModel(svc)
        model.save({"spray_width": 3.3})   # no load() first — must not raise
        svc.save_settings.assert_called_once()

    def test_save_does_not_mutate_previous_settings(self):
        original = GlueSettings(spray_width=1.0)
        model, _ = self._loaded(original)
        flat = GlueSettingsMapper.to_flat_dict(original)
        flat["spray_width"] = 99.0
        model.save(flat)
        self.assertEqual(original.spray_width, 1.0)


class TestGlueSettingsModelGlueTypes(unittest.TestCase):

    def _loaded_model(self, types=None):
        types = types or [Glue(name="Type A"), Glue(name="Type B")]
        svc   = _make_service(glue_types=types)
        model = GlueSettingsModel(svc)
        model.load()
        return model, svc

    def test_load_glue_types_delegates(self):
        model, svc = self._loaded_model()
        model.load_glue_types()
        svc.load_glue_types.assert_called()

    def test_load_glue_types_returns_list(self):
        types = [Glue(name="X"), Glue(name="Y")]
        model, _ = self._loaded_model(types)
        result = model.load_glue_types()
        self.assertEqual([g.name for g in result], ["X", "Y"])

    def test_add_glue_type_delegates(self):
        model, svc = self._loaded_model()
        new_glue = Glue(name="New")
        svc.add_glue_type.return_value = new_glue
        result = model.add_glue_type("New", "desc")
        svc.add_glue_type.assert_called_once_with("New", "desc")
        self.assertEqual(result.name, "New")

    def test_update_glue_type_delegates(self):
        model, svc = self._loaded_model()
        updated = Glue(name="Updated")
        svc.update_glue_type.return_value = updated
        result = model.update_glue_type("some-id", "Updated", "new desc")
        svc.update_glue_type.assert_called_once_with("some-id", "Updated", "new desc")
        self.assertEqual(result.name, "Updated")

    def test_remove_glue_type_delegates(self):
        model, svc = self._loaded_model()
        model.remove_glue_type("some-id")
        svc.remove_glue_type.assert_called_once_with("some-id")


class TestGlueSettingsApplicationService(unittest.TestCase):

    def _make_ss(self, settings=None, catalog=None):
        from src.robot_systems.glue.settings.glue_types import GlueCatalog
        _settings = settings or GlueSettings()
        _catalog  = catalog  or GlueCatalog(glue_types=[Glue(name="Type A"), Glue(name="Type B")])
        ss = MagicMock()
        ss.get.side_effect = lambda key: (
            _settings if key == "glue_settings" else
            _catalog  if key == "glue_catalog"  else None
        )
        return ss, _settings, _catalog

    def test_load_settings_reads_correct_key(self):
        from src.robot_systems.glue.glue_settings.service.glue_settings_application_service import GlueSettingsApplicationService
        ss, cfg, _ = self._make_ss()
        svc = GlueSettingsApplicationService(ss)
        self.assertIs(svc.load_settings(), cfg)
        ss.get.assert_called_with("glue_settings")

    def test_save_settings_writes_correct_key(self):
        from src.robot_systems.glue.glue_settings.service.glue_settings_application_service import GlueSettingsApplicationService
        ss, _, _ = self._make_ss()
        svc = GlueSettingsApplicationService(ss)
        new = GlueSettings(spray_width=5.5)
        svc.save_settings(new)
        ss.save.assert_called_once_with("glue_settings", new)

    def test_load_glue_types_returns_list(self):
        from src.robot_systems.glue.glue_settings.service.glue_settings_application_service import GlueSettingsApplicationService
        ss, _, catalog = self._make_ss()
        svc   = GlueSettingsApplicationService(ss)
        types = svc.load_glue_types()
        self.assertEqual(len(types), len(catalog.glue_types))

    def test_add_glue_type_saves_catalog(self):
        from src.robot_systems.glue.glue_settings.service.glue_settings_application_service import GlueSettingsApplicationService
        from src.robot_systems.glue.settings.glue_types import GlueCatalog
        catalog = GlueCatalog(glue_types=[])
        ss, _, _ = self._make_ss(catalog=catalog)
        svc = GlueSettingsApplicationService(ss)
        result = svc.add_glue_type("New Type", "desc")
        self.assertEqual(result.name, "New Type")
        ss.save.assert_called_once()

    def test_update_glue_type_saves_catalog(self):
        from src.robot_systems.glue.glue_settings.service.glue_settings_application_service import GlueSettingsApplicationService
        from src.robot_systems.glue.settings.glue_types import GlueCatalog
        existing = Glue(name="Old", glue_id="fixed-id")
        catalog  = GlueCatalog(glue_types=[existing])
        ss, _, _ = self._make_ss(catalog=catalog)
        svc    = GlueSettingsApplicationService(ss)
        result = svc.update_glue_type("fixed-id", "New Name", "new desc")
        self.assertEqual(result.name, "New Name")
        ss.save.assert_called_once()

    def test_update_glue_type_missing_id_raises(self):
        from src.robot_systems.glue.glue_settings.service.glue_settings_application_service import GlueSettingsApplicationService
        ss, _, _ = self._make_ss()
        svc = GlueSettingsApplicationService(ss)
        with self.assertRaises(KeyError):
            svc.update_glue_type("nonexistent-id", "X", "")

    def test_remove_glue_type_saves_catalog(self):
        from src.robot_systems.glue.glue_settings.service.glue_settings_application_service import GlueSettingsApplicationService
        from src.robot_systems.glue.settings.glue_types import GlueCatalog
        existing = Glue(name="Old", glue_id="del-id")
        catalog  = GlueCatalog(glue_types=[existing])
        ss, _, _ = self._make_ss(catalog=catalog)
        svc = GlueSettingsApplicationService(ss)
        svc.remove_glue_type("del-id")
        ss.save.assert_called_once()

    def test_remove_glue_type_missing_id_raises(self):
        from src.robot_systems.glue.glue_settings.service.glue_settings_application_service import GlueSettingsApplicationService
        ss, _, _ = self._make_ss()
        svc = GlueSettingsApplicationService(ss)
        with self.assertRaises(KeyError):
            svc.remove_glue_type("nonexistent-id")


if __name__ == "__main__":
    unittest.main()