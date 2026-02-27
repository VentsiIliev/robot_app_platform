import unittest
from unittest.mock import MagicMock, patch

from src.bootstrap.application_loader import ApplicationLoader, _ApplicationManager, _WidgetFactory
from src.engine.core.i_messaging_service import IMessagingService


def _make_ms():
    return MagicMock(spec=IMessagingService)


def _make_application(name="MyApplication"):
    application = MagicMock()
    application.__class__.__name__ = name
    return application


# ---------------------------------------------------------------------------
# _ApplicationManager
# ---------------------------------------------------------------------------

class TestApplicationManager(unittest.TestCase):

    def test_register_stores_application(self):
        mgr    = _ApplicationManager()
        application = _make_application()
        mgr.register("Foo", application, folder_id=1)
        self.assertIs(mgr.get_application("Foo"), application)

    def test_register_sets_json_metadata_folder_id(self):
        mgr    = _ApplicationManager()
        application = _make_application()
        mgr.register("Foo", application, folder_id=3, icon="fa5s.cog")
        self.assertEqual(application._json_metadata["folder_id"], 3)

    def test_register_sets_json_metadata_icon(self):
        mgr    = _ApplicationManager()
        application = _make_application()
        mgr.register("Foo", application, folder_id=1, icon="fa5s.star")
        self.assertEqual(application._json_metadata["icon_str"], "fa5s.star")

    def test_register_default_icon(self):
        mgr    = _ApplicationManager()
        application = _make_application()
        mgr.register("Foo", application, folder_id=1)
        self.assertEqual(application._json_metadata["icon_str"], "fa5s.cog")

    def test_get_loaded_application_names(self):
        mgr = _ApplicationManager()
        mgr.register("A", _make_application(), folder_id=1)
        mgr.register("B", _make_application(), folder_id=2)
        self.assertIn("A", mgr.get_loaded_application_names())
        self.assertIn("B", mgr.get_loaded_application_names())

    def test_get_application_unknown_returns_none(self):
        mgr = _ApplicationManager()
        self.assertIsNone(mgr.get_application("NonExistent"))

    def test_register_multiple_applications(self):
        mgr = _ApplicationManager()
        for i in range(5):
            mgr.register(f"Application{i}", _make_application(), folder_id=1)
        self.assertEqual(len(mgr.get_loaded_application_names()), 5)

    def test_register_overwrites_same_name(self):
        mgr  = _ApplicationManager()
        p1   = _make_application()
        p2   = _make_application()
        mgr.register("Same", p1, folder_id=1)
        mgr.register("Same", p2, folder_id=1)
        self.assertIs(mgr.get_application("Same"), p2)


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

    def test_create_widget_calls_application_create_widget(self):
        mgr    = _ApplicationManager()
        application = MagicMock()
        application.create_widget.return_value = MagicMock()
        mgr.register("Foo", application, folder_id=1)
        factory = _WidgetFactory(mgr)
        factory.create_widget("Foo")
        application.create_widget.assert_called_once()

    def test_create_widget_unknown_returns_fallback(self):
        from pl_gui.shell.base_app_widget.AppWidget import AppWidget
        mgr     = _ApplicationManager()
        factory = _WidgetFactory(mgr)
        widget  = factory.create_widget("Unknown")
        self.assertIsNotNone(widget)

    def test_create_widget_application_without_create_widget_returns_fallback(self):
        class _BareApplication:
            pass  # supports __dict__ — _json_metadata can be set

        mgr = _ApplicationManager()
        application = _BareApplication()
        mgr.register("Bare", application, folder_id=1)
        factory = _WidgetFactory(mgr)
        widget = factory.create_widget("Bare")
        self.assertIsNotNone(widget)


# ---------------------------------------------------------------------------
# ApplicationLoader
# ---------------------------------------------------------------------------

class TestApplicationLoaderInit(unittest.TestCase):

    def test_init_stores_messaging_service(self):
        ms     = _make_ms()
        loader = ApplicationLoader(ms)
        self.assertIs(loader._messaging_service, ms)

    def test_init_creates_empty_manager(self):
        loader = ApplicationLoader(_make_ms())
        self.assertEqual(loader._manager.get_loaded_application_names(), [])


class TestApplicationLoaderLoad(unittest.TestCase):

    def test_load_calls_register_on_application(self):
        ms     = _make_ms()
        loader = ApplicationLoader(ms)
        application = _make_application()
        loader.load(application, folder_id=1, name="MyApplication")
        application.register.assert_called_once_with(ms)

    def test_load_passes_messaging_service_to_application(self):
        ms     = _make_ms()
        loader = ApplicationLoader(ms)
        application = _make_application()
        loader.load(application, folder_id=1, name="MyApplication")
        args = application.register.call_args[0]
        self.assertIs(args[0], ms)

    def test_load_uses_explicit_name(self):
        loader = ApplicationLoader(_make_ms())
        loader.load(_make_application(), folder_id=1, name="ExplicitName")
        self.assertIn("ExplicitName", loader._manager.get_loaded_application_names())

    def test_load_falls_back_to_class_name(self):
        loader = ApplicationLoader(_make_ms())
        application = _make_application("FallbackName")
        loader.load(application, folder_id=2)
        self.assertIn("FallbackName", loader._manager.get_loaded_application_names())

    def test_load_returns_self_for_chaining(self):
        loader = ApplicationLoader(_make_ms())
        result = loader.load(_make_application(), folder_id=1, name="X")
        self.assertIs(result, loader)

    def test_load_application_without_register_does_not_raise(self):
        loader = ApplicationLoader(_make_ms())
        application = object()            # no register attribute
        loader.load(application, folder_id=1, name="NoRegister")   # must not raise

    def test_load_application_register_raises_does_not_propagate(self):
        loader = ApplicationLoader(_make_ms())
        application = _make_application()
        application.register.side_effect = RuntimeError("crash")
        loader.load(application, folder_id=1, name="Crasher")   # must not raise

    def test_load_multiple_applications(self):
        loader = ApplicationLoader(_make_ms())
        for i in range(3):
            loader.load(_make_application(), folder_id=1, name=f"P{i}")
        self.assertEqual(len(loader._manager.get_loaded_application_names()), 3)

    def test_load_sets_folder_id_metadata(self):
        loader = ApplicationLoader(_make_ms())
        application = _make_application()
        loader.load(application, folder_id=7, name="FolderTest")
        self.assertEqual(application._json_metadata["folder_id"], 7)

    def test_load_sets_icon_metadata(self):
        loader = ApplicationLoader(_make_ms())
        application = _make_application()
        loader.load(application, folder_id=1, icon="fa5s.robot", name="IconTest")
        self.assertEqual(application._json_metadata["icon_str"], "fa5s.robot")


class TestApplicationLoaderBuildRegistry(unittest.TestCase):

    def test_build_registry_returns_tuple(self):
        loader = ApplicationLoader(_make_ms())
        result = loader.build_registry()
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_build_registry_descriptors_is_iterable(self):
        loader = ApplicationLoader(_make_ms())
        descriptors, _ = loader.build_registry()
        list(descriptors)   # must not raise

    def test_build_registry_widget_factory_is_callable(self):
        loader  = ApplicationLoader(_make_ms())
        _, factory = loader.build_registry()
        self.assertTrue(callable(factory) or hasattr(factory, "create_widget"))


if __name__ == "__main__":
    unittest.main()