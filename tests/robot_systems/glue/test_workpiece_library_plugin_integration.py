"""
Plugin integration tests for WorkpieceLibrary application.

Verifies:
- ApplicationSpec is declared in GlueRobotSystem.shell.applications
- factory produces a WidgetApplication
- settings_service is used to fetch catalog settings
"""
import unittest
from unittest.mock import MagicMock

from src.applications.base.widget_application import WidgetApplication
from src.engine.common_settings_ids import CommonSettingsID
from src.robot_systems.glue.glue_robot_system import GlueRobotSystem
from src.robot_systems.glue.component_ids import SettingsID


def _make_robot_system():
    catalog = MagicMock()
    catalog.get_all_names.return_value = ["Type A"]

    tc = MagicMock()
    tc.get_tool_options.return_value = []

    ss = MagicMock()
    ss.get.side_effect = lambda key: (
        catalog if key == SettingsID.GLUE_CATALOG else
        tc      if key == CommonSettingsID.TOOL_CHANGER_CONFIG else
        MagicMock()
    )

    app = MagicMock()
    app._settings_service = ss
    app.get_optional_service.return_value = None
    return app


def _spec():
    return next(
        (s for s in GlueRobotSystem.shell.applications if s.name == "WorkpieceLibrary"),
        None,
    )


class TestWorkpieceLibraryApplicationSpec(unittest.TestCase):

    def test_spec_declared(self):
        self.assertIsNotNone(_spec(), "WorkpieceLibrary ApplicationSpec missing")

    def test_spec_folder_id(self):
        self.assertEqual(_spec().folder_id, 1)

    def test_spec_has_factory(self):
        self.assertIsNotNone(_spec().factory)

    def test_spec_icon_set(self):
        self.assertIsNotNone(_spec().icon)


class TestWorkpieceLibraryApplicationFactory(unittest.TestCase):

    def test_factory_returns_widget_application(self):
        application = _spec().factory(_make_robot_system())
        self.assertIsInstance(application, WidgetApplication)

    def test_factory_fetches_catalog_settings(self):
        robot_app = _make_robot_system()
        _spec().factory(robot_app)
        # catalog is accessed via settings_service.get at factory build time
        robot_app._settings_service.get.assert_any_call(SettingsID.GLUE_CATALOG)

    def test_register_stores_messaging_service(self):
        application = _spec().factory(_make_robot_system())
        ms = MagicMock()
        application.register(ms)
        self.assertIs(application._messaging_service, ms)


if __name__ == "__main__":
    unittest.main()
