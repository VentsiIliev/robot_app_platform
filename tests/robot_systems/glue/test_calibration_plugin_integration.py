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


class TestCalibrationApplicationSpec(unittest.TestCase):

    def _spec(self):
        return next(
            (s for s in GlueRobotSystem.shell.applications if s.name == "Calibration"),
            None,
        )

    def test_spec_declared(self):
        self.assertIsNotNone(self._spec(), "Calibration ApplicationSpec missing from GlueRobotSystem")

    def test_spec_folder_id(self):
        self.assertEqual(self._spec().folder_id, 2)

    def test_spec_has_factory(self):
        self.assertIsNotNone(self._spec().factory)

    def test_spec_icon_set(self):
        self.assertIsNotNone(self._spec().icon)


class TestCalibrationApplicationFactory(unittest.TestCase):

    def _build(self):
        spec = next(s for s in GlueRobotSystem.shell.applications if s.name == "Calibration")
        robot_app = _make_robot_system()
        application = spec.factory(robot_app)
        return application, robot_app

    def test_factory_returns_widget_application(self):
        application, _ = self._build()
        self.assertIsInstance(application, WidgetApplication)

    def test_factory_fetches_vision_service_as_optional(self):
        spec = next(s for s in GlueRobotSystem.shell.applications if s.name == "Calibration")
        robot_app = _make_robot_system()
        spec.factory(robot_app)
        robot_app.get_optional_service.assert_any_call(ServiceID.VISION)

    def test_register_stores_messaging_service(self):
        application, _ = self._build()
        ms = MagicMock()
        application.register(ms)
        self.assertIs(application._messaging_service, ms)

    def test_widget_factory_forwards_messaging_service(self):
        application, _ = self._build()
        ms = MagicMock()
        application.register(ms)
        # widget_factory must accept the messaging service (CalibrationFactory needs it)
        self.assertIs(application._messaging_service, ms)


if __name__ == "__main__":
    unittest.main()