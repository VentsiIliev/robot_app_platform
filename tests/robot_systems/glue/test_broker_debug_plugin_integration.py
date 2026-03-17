"""
Plugin integration tests for BrokerDebug application.

Verifies:
- ApplicationSpec is declared in GlueRobotSystem.shell.applications
- factory produces a WidgetApplication
"""
import unittest
from unittest.mock import MagicMock

from src.applications.base.widget_application import WidgetApplication
from src.robot_systems.glue.glue_robot_system import GlueRobotSystem


def _make_robot_system():
    app = MagicMock()
    app._settings_service = MagicMock()
    app.get_optional_service.return_value = None
    return app


def _spec():
    return next(
        (s for s in GlueRobotSystem.shell.applications if s.name == "BrokerDebug"),
        None,
    )


class TestBrokerDebugApplicationSpec(unittest.TestCase):

    def test_spec_declared(self):
        self.assertIsNotNone(_spec(), "BrokerDebug ApplicationSpec missing")

    def test_spec_folder_id(self):
        self.assertEqual(_spec().folder_id, 4)

    def test_spec_has_factory(self):
        self.assertIsNotNone(_spec().factory)

    def test_spec_icon_set(self):
        self.assertIsNotNone(_spec().icon)


class TestBrokerDebugApplicationFactory(unittest.TestCase):

    def test_factory_returns_widget_application(self):
        application = _spec().factory(_make_robot_system())
        self.assertIsInstance(application, WidgetApplication)

    def test_register_stores_messaging_service(self):
        application = _spec().factory(_make_robot_system())
        ms = MagicMock()
        application.register(ms)
        self.assertIs(application._messaging_service, ms)


if __name__ == "__main__":
    unittest.main()
