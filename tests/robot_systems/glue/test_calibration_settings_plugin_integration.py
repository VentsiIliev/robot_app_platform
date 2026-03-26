import unittest
from unittest.mock import MagicMock

from src.applications.base.widget_application import WidgetApplication
from src.engine.common_service_ids import CommonServiceID
from src.robot_systems.glue.glue_robot_system import GlueRobotSystem


def _make_robot_system():
    robot_system = MagicMock()
    robot_system._settings_service = MagicMock()
    robot_system.get_optional_service.return_value = None
    robot_system.get_service.return_value = MagicMock()
    return robot_system


def _spec():
    return next(
        (spec for spec in GlueRobotSystem.shell.applications if spec.name == "CalibrationSettings"),
        None,
    )


class TestCalibrationSettingsApplicationSpec(unittest.TestCase):
    def test_spec_declared(self):
        self.assertIsNotNone(_spec(), "CalibrationSettings ApplicationSpec missing")

    def test_spec_folder_id(self):
        self.assertEqual(_spec().folder_id, 2)

    def test_spec_has_factory(self):
        self.assertIsNotNone(_spec().factory)


class TestCalibrationSettingsApplicationFactory(unittest.TestCase):
    def test_factory_returns_widget_application(self):
        application = _spec().factory(_make_robot_system())
        self.assertIsInstance(application, WidgetApplication)

    def test_register_stores_messaging_service(self):
        application = _spec().factory(_make_robot_system())
        messaging = MagicMock()
        application.register(messaging)
        self.assertIs(application._messaging_service, messaging)
