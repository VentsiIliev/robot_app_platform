import unittest
import os
from unittest.mock import MagicMock, patch

from src.bootstrap.application_loader import ApplicationLoader, _ApplicationManager, _WidgetFactory
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.declarations.system_specs import ApplicationSpec


def _make_ms():
    return MagicMock(spec=IMessagingService)


def _make_application(name="MyApplication"):
    application = MagicMock()
    application.__class__.__name__ = name
    return application


def _make_spec(name="MyApplication", folder_id=1, icon="fa5s.cog"):
    return ApplicationSpec(name=name, folder_id=folder_id, icon=icon)


# ---------------------------------------------------------------------------
# _ApplicationManager
# ---------------------------------------------------------------------------

class TestApplicationManager(unittest.TestCase):

    def test_register_lazy_exposes_descriptor_metadata(self):
        mgr = _ApplicationManager()
        spec = _make_spec(name="Foo", folder_id=3, icon="fa5s.star")
        application = _make_application()
        mgr.register_lazy(spec, lambda: application)

        descriptor = mgr.get_descriptors()[0]
        self.assertEqual(descriptor.name, "Foo")
        self.assertEqual(descriptor.folder_id, 3)
        self.assertEqual(descriptor.icon_str, "fa5s.star")

    def test_get_loaded_application_names(self):
        mgr = _ApplicationManager()
        mgr.register_lazy(_make_spec(name="A", folder_id=1), _make_application)
        mgr.register_lazy(_make_spec(name="B", folder_id=2), _make_application)
        self.assertIn("A", mgr.get_loaded_application_names())
        self.assertIn("B", mgr.get_loaded_application_names())

    def test_get_application_unknown_returns_none(self):
        mgr = _ApplicationManager()
        self.assertIsNone(mgr.get_application("NonExistent"))

    def test_register_lazy_multiple_applications(self):
        mgr = _ApplicationManager()
        for i in range(5):
            mgr.register_lazy(_make_spec(name=f"Application{i}", folder_id=1), _make_application)
        self.assertEqual(len(mgr.get_loaded_application_names()), 5)

    def test_get_or_create_application_builds_and_caches(self):
        mgr = _ApplicationManager()
        application = _make_application()
        builder = MagicMock(return_value=application)
        mgr.register_lazy(_make_spec(name="Same", folder_id=1), builder)

        first = mgr.get_or_create_application("Same")
        second = mgr.get_or_create_application("Same")

        self.assertIs(first, application)
        self.assertIs(second, application)
        self.assertIs(mgr.get_application("Same"), application)
        builder.assert_called_once_with()


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
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._qt_app = QApplication.instance() or QApplication(sys.argv)

    def test_create_widget_calls_application_create_widget(self):
        mgr = _ApplicationManager()
        ms = _make_ms()
        application = MagicMock()
        application._lazy_registered = False
        application.create_widget.return_value = MagicMock()
        mgr.register_lazy(_make_spec(name="Foo", folder_id=1), lambda: application)
        factory = _WidgetFactory(mgr, ms)
        factory.create_widget("Foo")
        application.register.assert_called_once_with(ms)
        application.create_widget.assert_called_once()

    def test_create_widget_unknown_returns_fallback(self):
        mgr = _ApplicationManager()
        factory = _WidgetFactory(mgr, _make_ms())
        widget = factory.create_widget("Unknown")
        self.assertIsNotNone(widget)

    def test_create_widget_application_without_create_widget_returns_fallback(self):
        class _BareApplication:
            pass  # supports __dict__ — _json_metadata can be set

        mgr = _ApplicationManager()
        application = _BareApplication()
        mgr.register_lazy(_make_spec(name="Bare", folder_id=1), lambda: application)
        factory = _WidgetFactory(mgr, _make_ms())
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


class TestApplicationLoaderRegisterSpec(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import sys
        from PyQt6.QtWidgets import QApplication
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._qt_app = QApplication.instance() or QApplication(sys.argv)

    def test_register_spec_stores_descriptor_name(self):
        ms = _make_ms()
        loader = ApplicationLoader(ms)
        spec = _make_spec(name="MyApplication", folder_id=1)

        loader.register_spec(spec, builder=_make_application)

        self.assertIn("MyApplication", loader._manager.get_loaded_application_names())

    def test_register_spec_returns_self_for_chaining(self):
        loader = ApplicationLoader(_make_ms())
        result = loader.register_spec(_make_spec(name="X", folder_id=1), builder=_make_application)
        self.assertIs(result, loader)

    def test_register_spec_multiple_applications(self):
        loader = ApplicationLoader(_make_ms())
        for i in range(3):
            loader.register_spec(_make_spec(name=f"P{i}", folder_id=1), builder=_make_application)
        self.assertEqual(len(loader._manager.get_loaded_application_names()), 3)

    def test_register_spec_does_not_build_application_eagerly(self):
        loader = ApplicationLoader(_make_ms())
        builder = MagicMock(return_value=_make_application())

        loader.register_spec(_make_spec(name="Lazy", folder_id=1), builder=builder)

        self.assertIsNone(loader._manager.get_application("Lazy"))
        builder.assert_not_called()

    def test_widget_factory_registers_application_on_first_widget_creation(self):
        ms = _make_ms()
        loader = ApplicationLoader(ms)
        application = _make_application()
        application._lazy_registered = False
        application.create_widget.return_value = MagicMock()
        loader.register_spec(_make_spec(name="Lazy", folder_id=1), builder=lambda: application)

        _, widget_factory = loader.build_registry()
        widget_factory("Lazy")

        application.register.assert_called_once_with(ms)
        application.create_widget.assert_called_once_with()

    def test_widget_factory_builder_failure_returns_fallback_widget(self):
        loader = ApplicationLoader(_make_ms())
        loader.register_spec(
            _make_spec(name="Crasher", folder_id=1),
            builder=MagicMock(side_effect=RuntimeError("crash")),
        )

        _, widget_factory = loader.build_registry()
        widget = widget_factory("Crasher")

        self.assertIsNotNone(widget)

    def test_widget_factory_create_widget_failure_returns_fallback_widget(self):
        loader = ApplicationLoader(_make_ms())
        application = _make_application()
        application.create_widget.side_effect = RuntimeError("boom")
        loader.register_spec(_make_spec(name="Broken", folder_id=7, icon="fa5s.robot"), builder=lambda: application)

        descriptors, widget_factory = loader.build_registry()
        widget = widget_factory("Broken")

        self.assertEqual(descriptors[0].folder_id, 7)
        self.assertEqual(descriptors[0].icon_str, "fa5s.robot")
        self.assertIsNotNone(widget)


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
