import unittest
import sys
import os
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication
from src.applications.base.widget_application import WidgetApplication
from src.robot_systems.glue.glue_robot_system import GlueRobotSystem
from src.engine.common_service_ids import CommonServiceID
from src.robot_systems.glue.component_ids import ServiceID


def _spec():
    return next(
        (s for s in GlueRobotSystem.shell.applications if s.name == "GlueProcessDriver"),
        None,
    )


def _make_robot_system():
    robot_system = MagicMock()
    robot_system._settings_service = MagicMock()
    robot_system.get_optional_service.return_value = None
    robot_system.coordinator = MagicMock()
    robot_system.coordinator.glue_process = MagicMock()
    robot_system.coordinator.glue_process.get_dispensing_snapshot.return_value = {
        "process_state": "idle",
        "dispensing": None,
    }
    return robot_system


class TestGlueProcessDriverApplicationSpec(unittest.TestCase):
    def test_spec_declared(self):
        self.assertIsNotNone(_spec(), "GlueProcessDriver ApplicationSpec missing")

    def test_spec_folder_id(self):
        self.assertEqual(_spec().folder_id, 4)

    def test_spec_has_factory(self):
        self.assertIsNotNone(_spec().factory)

    def test_spec_icon_set(self):
        self.assertIsNotNone(_spec().icon)


class TestGlueProcessDriverApplicationFactory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_factory_returns_widget_application(self):
        application = _spec().factory(_make_robot_system())
        self.assertIsInstance(application, WidgetApplication)

    def test_factory_fetches_vision_service_as_optional(self):
        robot_system = _make_robot_system()

        _spec().factory(robot_system)

        robot_system.get_optional_service.assert_any_call(CommonServiceID.VISION)

    def test_register_stores_messaging_service(self):
        application = _spec().factory(_make_robot_system())
        messaging_service = MagicMock()

        application.register(messaging_service)

        self.assertIs(application._messaging_service, messaging_service)

    def test_widget_factory_passes_registered_broker(self):
        application = _spec().factory(_make_robot_system())
        messaging_service = MagicMock()

        application.register(messaging_service)
        widget = application.create_widget()

        self.assertIs(widget._controller._broker, messaging_service)

    def test_widget_factory_configures_execution_service(self):
        application = _spec().factory(_make_robot_system())
        messaging_service = MagicMock()

        application.register(messaging_service)
        widget = application.create_widget()

        self.assertIsNotNone(widget._controller._model._service._execution_service)


if __name__ == "__main__":
    unittest.main()
