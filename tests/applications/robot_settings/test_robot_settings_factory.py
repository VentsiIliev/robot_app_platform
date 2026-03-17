import sys
import unittest
from unittest.mock import MagicMock

from src.engine.robot.configuration import RobotSettings, RobotCalibrationSettings
from src.applications.robot_settings.service.i_robot_settings_service import IRobotSettingsService
from src.applications.robot_settings.robot_settings_factory import RobotSettingsFactory
from src.applications.robot_settings.view.robot_settings_view import RobotSettingsView
from src.applications.robot_settings.controller.robot_settings_controller import RobotSettingsController


def _make_service():
    svc = MagicMock(spec=IRobotSettingsService)
    svc.load_config.return_value      = RobotSettings()
    svc.load_calibration.return_value = RobotCalibrationSettings()
    svc.get_slot_info.return_value    = []
    return svc


class TestRobotSettingsFactory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def _make_factory(self):
        return RobotSettingsFactory(MagicMock(), MagicMock())

    def test_build_returns_robot_settings_view(self):
        result = self._make_factory().build(_make_service())
        self.assertIsInstance(result, RobotSettingsView)

    def test_build_attaches_controller_to_view(self):
        view = self._make_factory().build(_make_service())
        self.assertIsInstance(view._controller, RobotSettingsController)

    def test_build_calls_load_config_on_service(self):
        svc = _make_service()
        self._make_factory().build(svc)
        svc.load_config.assert_called_once()

    def test_build_calls_load_calibration_on_service(self):
        svc = _make_service()
        self._make_factory().build(svc)
        svc.load_calibration.assert_called_once()

    def test_two_builds_produce_independent_views(self):
        svc  = _make_service()
        v1   = self._make_factory().build(svc)
        v2   = self._make_factory().build(_make_service())
        self.assertIsNot(v1, v2)
        self.assertIsNot(v1._controller, v2._controller)


if __name__ == "__main__":
    unittest.main()