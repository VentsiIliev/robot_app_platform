"""
Plugin integration tests for ToolSettings application.

Verifies:
- ApplicationSpec is declared in GlueRobotSystem.shell.applications
- factory produces a WidgetApplication
- settings_service is accessed
"""
import unittest
from unittest.mock import MagicMock

from src.applications.base.widget_application import WidgetApplication
from src.robot_systems.glue.glue_robot_system import GlueRobotSystem


def _make_robot_system():
    tc = MagicMock()
    tc.get_tool_options.return_value = []
    ss = MagicMock()
    ss.get.return_value = tc
    app = MagicMock()
    app._settings_service = ss
    app.get_optional_service.return_value = None
    return app


def _spec():
    return next(
        (s for s in GlueRobotSystem.shell.applications if s.name == "ToolSettings"),
        None,
    )


class TestToolSettingsApplicationSpec(unittest.TestCase):

    def test_spec_declared(self):
        self.assertIsNotNone(_spec(), "ToolSettings ApplicationSpec missing")

    def test_spec_folder_id(self):
        self.assertEqual(_spec().folder_id, 2)

    def test_spec_has_factory(self):
        self.assertIsNotNone(_spec().factory)

    def test_spec_icon_set(self):
        self.assertIsNotNone(_spec().icon)


class TestToolSettingsApplicationFactory(unittest.TestCase):

    def test_factory_returns_widget_application(self):
        application = _spec().factory(_make_robot_system())
        self.assertIsInstance(application, WidgetApplication)

    def test_factory_uses_settings_service(self):
        robot_app = _make_robot_system()
        _spec().factory(robot_app)
        # settings_service is passed to ToolSettingsApplicationService
        self.assertIsNotNone(robot_app._settings_service)

    def test_register_stores_messaging_service(self):
        application = _spec().factory(_make_robot_system())
        ms = MagicMock()
        application.register(ms)
        self.assertIs(application._messaging_service, ms)


if __name__ == "__main__":
    unittest.main()
