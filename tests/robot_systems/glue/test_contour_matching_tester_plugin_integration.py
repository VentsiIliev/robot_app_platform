"""
Plugin integration tests for ContourMatchingTester application.

Verifies:
- ApplicationSpec is declared in GlueRobotSystem.shell.applications
- factory produces a WidgetApplication
- vision service is fetched as optional
"""
import unittest
from unittest.mock import MagicMock

from src.applications.base.widget_application import WidgetApplication
from src.robot_systems.glue.glue_robot_system import GlueRobotSystem
from src.robot_systems.glue.service_ids import ServiceID


def _make_robot_system():
    app = MagicMock()
    app._settings_service = MagicMock()
    app.get_optional_service.return_value = None
    return app


def _spec():
    return next(
        (s for s in GlueRobotSystem.shell.applications if s.name == "ContourMatchingTester"),
        None,
    )


class TestContourMatchingTesterApplicationSpec(unittest.TestCase):

    def test_spec_declared(self):
        self.assertIsNotNone(_spec(), "ContourMatchingTester ApplicationSpec missing")

    def test_spec_folder_id(self):
        self.assertEqual(_spec().folder_id, 4)

    def test_spec_has_factory(self):
        self.assertIsNotNone(_spec().factory)

    def test_spec_icon_set(self):
        self.assertIsNotNone(_spec().icon)


class TestContourMatchingTesterApplicationFactory(unittest.TestCase):

    def test_factory_returns_widget_application(self):
        application = _spec().factory(_make_robot_system())
        self.assertIsInstance(application, WidgetApplication)

    def test_factory_fetches_vision_service_as_optional(self):
        robot_app = _make_robot_system()
        _spec().factory(robot_app)
        robot_app.get_optional_service.assert_any_call(ServiceID.VISION)

    def test_register_stores_messaging_service(self):
        application = _spec().factory(_make_robot_system())
        ms = MagicMock()
        application.register(ms)
        self.assertIs(application._messaging_service, ms)


if __name__ == "__main__":
    unittest.main()
