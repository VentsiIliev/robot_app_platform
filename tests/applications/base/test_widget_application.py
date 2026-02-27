"""
Unit tests for WidgetApplication.

These are pure unit tests — widget_factory is always a mock, no Qt needed.

Covered:
- register() stores the messaging service for later use
- register() called twice keeps the most recent service
- create_widget() delegates to widget_factory with the stored messaging service
- create_widget() returns exactly what widget_factory returns
- create_widget() before register() passes None to the factory (safe default)
- create_widget() can be called multiple times; factory is called each time
"""
import unittest
from unittest.mock import MagicMock

from src.applications.base.widget_application import WidgetApplication


class TestRegister(unittest.TestCase):

    def test_register_stores_messaging_service(self):
        app = WidgetApplication(widget_factory=MagicMock())
        ms  = MagicMock()
        app.register(ms)
        self.assertIs(app._messaging_service, ms)

    def test_register_twice_keeps_most_recent_service(self):
        app       = WidgetApplication(widget_factory=MagicMock())
        ms1, ms2  = MagicMock(), MagicMock()
        app.register(ms1)
        app.register(ms2)
        self.assertIs(app._messaging_service, ms2)

    def test_messaging_service_is_none_before_register(self):
        app = WidgetApplication(widget_factory=MagicMock())
        self.assertIsNone(app._messaging_service)


class TestCreateWidget(unittest.TestCase):

    def test_create_widget_calls_factory_with_messaging_service(self):
        factory = MagicMock()
        ms      = MagicMock()
        app     = WidgetApplication(widget_factory=factory)
        app.register(ms)

        app.create_widget()

        factory.assert_called_once_with(ms)

    def test_create_widget_returns_factory_result(self):
        widget  = MagicMock()
        factory = MagicMock(return_value=widget)
        app     = WidgetApplication(widget_factory=factory)
        app.register(MagicMock())

        result = app.create_widget()

        self.assertIs(result, widget)

    def test_create_widget_before_register_passes_none_to_factory(self):
        factory = MagicMock()
        app     = WidgetApplication(widget_factory=factory)

        app.create_widget()

        factory.assert_called_once_with(None)

    def test_create_widget_called_multiple_times_invokes_factory_each_time(self):
        factory = MagicMock(side_effect=[MagicMock(), MagicMock(), MagicMock()])
        app     = WidgetApplication(widget_factory=factory)
        app.register(MagicMock())

        app.create_widget()
        app.create_widget()
        app.create_widget()

        self.assertEqual(factory.call_count, 3)

    def test_create_widget_passes_updated_service_after_second_register(self):
        factory   = MagicMock()
        ms1, ms2  = MagicMock(), MagicMock()
        app       = WidgetApplication(widget_factory=factory)

        app.register(ms1)
        app.create_widget()

        app.register(ms2)
        app.create_widget()

        calls = factory.call_args_list
        self.assertEqual(calls[0].args[0], ms1)
        self.assertEqual(calls[1].args[0], ms2)


if __name__ == "__main__":
    unittest.main()
