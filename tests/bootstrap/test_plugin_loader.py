import unittest
from unittest.mock import MagicMock, patch

from src.bootstrap.plugin_loader import PluginLoader, _PluginManager, _WidgetFactory
from src.engine.core.i_messaging_service import IMessagingService


def _make_ms():
    return MagicMock(spec=IMessagingService)


def _make_plugin(name="MyPlugin"):
    plugin = MagicMock()
    plugin.__class__.__name__ = name
    return plugin


# ---------------------------------------------------------------------------
# _PluginManager
# ---------------------------------------------------------------------------

class TestPluginManager(unittest.TestCase):

    def test_register_stores_plugin(self):
        mgr    = _PluginManager()
        plugin = _make_plugin()
        mgr.register("Foo", plugin, folder_id=1)
        self.assertIs(mgr.get_plugin("Foo"), plugin)

    def test_register_sets_json_metadata_folder_id(self):
        mgr    = _PluginManager()
        plugin = _make_plugin()
        mgr.register("Foo", plugin, folder_id=3, icon="fa5s.cog")
        self.assertEqual(plugin._json_metadata["folder_id"], 3)

    def test_register_sets_json_metadata_icon(self):
        mgr    = _PluginManager()
        plugin = _make_plugin()
        mgr.register("Foo", plugin, folder_id=1, icon="fa5s.star")
        self.assertEqual(plugin._json_metadata["icon_str"], "fa5s.star")

    def test_register_default_icon(self):
        mgr    = _PluginManager()
        plugin = _make_plugin()
        mgr.register("Foo", plugin, folder_id=1)
        self.assertEqual(plugin._json_metadata["icon_str"], "fa5s.cog")

    def test_get_loaded_plugin_names(self):
        mgr = _PluginManager()
        mgr.register("A", _make_plugin(), folder_id=1)
        mgr.register("B", _make_plugin(), folder_id=2)
        self.assertIn("A", mgr.get_loaded_plugin_names())
        self.assertIn("B", mgr.get_loaded_plugin_names())

    def test_get_plugin_unknown_returns_none(self):
        mgr = _PluginManager()
        self.assertIsNone(mgr.get_plugin("NonExistent"))

    def test_register_multiple_plugins(self):
        mgr = _PluginManager()
        for i in range(5):
            mgr.register(f"Plugin{i}", _make_plugin(), folder_id=1)
        self.assertEqual(len(mgr.get_loaded_plugin_names()), 5)

    def test_register_overwrites_same_name(self):
        mgr  = _PluginManager()
        p1   = _make_plugin()
        p2   = _make_plugin()
        mgr.register("Same", p1, folder_id=1)
        mgr.register("Same", p2, folder_id=1)
        self.assertIs(mgr.get_plugin("Same"), p2)


# ---------------------------------------------------------------------------
# _WidgetFactory
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# _WidgetFactory
# ---------------------------------------------------------------------------

class TestWidgetFactory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import sys
        from PyQt6.QtWidgets import QApplication
        cls._qt_app = QApplication.instance() or QApplication(sys.argv)

    def test_create_widget_calls_plugin_create_widget(self):
        mgr    = _PluginManager()
        plugin = MagicMock()
        plugin.create_widget.return_value = MagicMock()
        mgr.register("Foo", plugin, folder_id=1)
        factory = _WidgetFactory(mgr)
        factory.create_widget("Foo")
        plugin.create_widget.assert_called_once()

    def test_create_widget_unknown_returns_fallback(self):
        from pl_gui.shell.base_app_widget.AppWidget import AppWidget
        mgr     = _PluginManager()
        factory = _WidgetFactory(mgr)
        widget  = factory.create_widget("Unknown")
        self.assertIsNotNone(widget)

    def test_create_widget_plugin_without_create_widget_returns_fallback(self):
        class _BarePlugin:
            pass  # supports __dict__ — _json_metadata can be set

        mgr = _PluginManager()
        plugin = _BarePlugin()
        mgr.register("Bare", plugin, folder_id=1)
        factory = _WidgetFactory(mgr)
        widget = factory.create_widget("Bare")
        self.assertIsNotNone(widget)


# ---------------------------------------------------------------------------
# PluginLoader
# ---------------------------------------------------------------------------

class TestPluginLoaderInit(unittest.TestCase):

    def test_init_stores_messaging_service(self):
        ms     = _make_ms()
        loader = PluginLoader(ms)
        self.assertIs(loader._messaging_service, ms)

    def test_init_creates_empty_manager(self):
        loader = PluginLoader(_make_ms())
        self.assertEqual(loader._manager.get_loaded_plugin_names(), [])


class TestPluginLoaderLoad(unittest.TestCase):

    def test_load_calls_register_on_plugin(self):
        ms     = _make_ms()
        loader = PluginLoader(ms)
        plugin = _make_plugin()
        loader.load(plugin, folder_id=1, name="MyPlugin")
        plugin.register.assert_called_once_with(ms)

    def test_load_passes_messaging_service_to_plugin(self):
        ms     = _make_ms()
        loader = PluginLoader(ms)
        plugin = _make_plugin()
        loader.load(plugin, folder_id=1, name="MyPlugin")
        args = plugin.register.call_args[0]
        self.assertIs(args[0], ms)

    def test_load_uses_explicit_name(self):
        loader = PluginLoader(_make_ms())
        loader.load(_make_plugin(), folder_id=1, name="ExplicitName")
        self.assertIn("ExplicitName", loader._manager.get_loaded_plugin_names())

    def test_load_falls_back_to_class_name(self):
        loader = PluginLoader(_make_ms())
        plugin = _make_plugin("FallbackName")
        loader.load(plugin, folder_id=2)
        self.assertIn("FallbackName", loader._manager.get_loaded_plugin_names())

    def test_load_returns_self_for_chaining(self):
        loader = PluginLoader(_make_ms())
        result = loader.load(_make_plugin(), folder_id=1, name="X")
        self.assertIs(result, loader)

    def test_load_plugin_without_register_does_not_raise(self):
        loader = PluginLoader(_make_ms())
        plugin = object()            # no register attribute
        loader.load(plugin, folder_id=1, name="NoRegister")   # must not raise

    def test_load_plugin_register_raises_does_not_propagate(self):
        loader = PluginLoader(_make_ms())
        plugin = _make_plugin()
        plugin.register.side_effect = RuntimeError("crash")
        loader.load(plugin, folder_id=1, name="Crasher")   # must not raise

    def test_load_multiple_plugins(self):
        loader = PluginLoader(_make_ms())
        for i in range(3):
            loader.load(_make_plugin(), folder_id=1, name=f"P{i}")
        self.assertEqual(len(loader._manager.get_loaded_plugin_names()), 3)

    def test_load_sets_folder_id_metadata(self):
        loader = PluginLoader(_make_ms())
        plugin = _make_plugin()
        loader.load(plugin, folder_id=7, name="FolderTest")
        self.assertEqual(plugin._json_metadata["folder_id"], 7)

    def test_load_sets_icon_metadata(self):
        loader = PluginLoader(_make_ms())
        plugin = _make_plugin()
        loader.load(plugin, folder_id=1, icon="fa5s.robot", name="IconTest")
        self.assertEqual(plugin._json_metadata["icon_str"], "fa5s.robot")


class TestPluginLoaderBuildRegistry(unittest.TestCase):

    def test_build_registry_returns_tuple(self):
        loader = PluginLoader(_make_ms())
        result = loader.build_registry()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_build_registry_descriptors_is_iterable(self):
        loader = PluginLoader(_make_ms())
        descriptors, _ = loader.build_registry()
        list(descriptors)   # must not raise

    def test_build_registry_widget_factory_is_callable(self):
        loader  = PluginLoader(_make_ms())
        _, factory = loader.build_registry()
        self.assertTrue(callable(factory) or hasattr(factory, "create_widget"))


if __name__ == "__main__":
    unittest.main()