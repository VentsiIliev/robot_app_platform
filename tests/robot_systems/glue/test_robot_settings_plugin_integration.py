import unittest
from unittest.mock import MagicMock, patch

from src.engine.robot.configuration import RobotSettings, RobotCalibrationSettings
from src.applications.base.widget_application import WidgetApplication
from src.applications.robot_settings.service.robot_settings_application_service import RobotSettingsApplicationService
from src.robot_systems.glue.glue_robot_system import GlueRobotSystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_robot_system(config=None, calibration=None):
    ss = MagicMock()
    ss.get.side_effect = lambda key: (
        config      or RobotSettings()      if key == "robot_config"      else
        calibration or RobotCalibrationSettings() if key == "robot_calibration" else None
    )
    app                   = MagicMock()
    app._settings_service = ss
    return app


# ---------------------------------------------------------------------------
# ApplicationSpec declaration
# ---------------------------------------------------------------------------

class TestRobotSettingsApplicationSpec(unittest.TestCase):

    def _spec(self):
        return next(
            (s for s in GlueRobotSystem.shell.applications if s.name == "RobotSettings"),
            None,
        )

    def test_spec_declared(self):
        self.assertIsNotNone(self._spec(), "RobotSettings ApplicationSpec missing from GlueRobotSystem.shell.applications")

    def test_spec_folder_id(self):
        self.assertEqual(self._spec().folder_id, 2)

    def test_spec_has_factory(self):
        self.assertIsNotNone(self._spec().factory)

    def test_spec_icon_set(self):
        self.assertIsNotNone(self._spec().icon)


# ---------------------------------------------------------------------------
# Factory builds a WidgetApplication
# ---------------------------------------------------------------------------

class TestRobotSettingsApplicationFactory(unittest.TestCase):

    def test_factory_returns_widget_application(self):
        robot_app = _make_robot_system()
        spec      = next(s for s in GlueRobotSystem.shell.applications if s.name == "RobotSettings")
        application    = spec.factory(robot_app)
        self.assertIsInstance(application, WidgetApplication)

    def test_factory_does_not_require_messaging_service(self):
        robot_app = _make_robot_system()
        spec      = next(s for s in GlueRobotSystem.shell.applications if s.name == "RobotSettings")
        # Should not raise before register() is called
        application = spec.factory(robot_app)
        self.assertIsNotNone(application)

    def test_register_stores_messaging_service(self):
        robot_app        = _make_robot_system()
        spec             = next(s for s in GlueRobotSystem.shell.applications if s.name == "RobotSettings")
        application           = spec.factory(robot_app)
        messaging_service = MagicMock()
        application.register(messaging_service)
        self.assertIs(application._messaging_service, messaging_service)

    def test_widget_factory_callable_ignores_messaging_service(self):
        """RobotSettings does not use the broker — lambda must accept and ignore it."""
        robot_app = _make_robot_system()
        spec = next(s for s in GlueRobotSystem.shell.applications if s.name == "RobotSettings")
        application = spec.factory(robot_app)

        with patch(
                "src.applications.robot_settings.robot_settings_factory.RobotSettingsFactory.build"
        ) as mock_build:
            mock_build.return_value = MagicMock()
            application.register(MagicMock())
            application.create_widget()
            mock_build.assert_called_once()


# ---------------------------------------------------------------------------
# RobotSettingsApplicationService — integration with ISettingsService
# ---------------------------------------------------------------------------

class TestRobotSettingsApplicationServiceIntegration(unittest.TestCase):

    def _make_service(self, config=None, calibration=None):
        cfg   = config      or RobotSettings(robot_ip="1.1.1.1", robot_tool=3)
        calib = calibration or RobotCalibrationSettings(z_target=400)
        ss = MagicMock()
        ss.get.side_effect = lambda key: (
            cfg   if key == "robot_config"      else
            calib if key == "robot_calibration" else None
        )
        return RobotSettingsApplicationService(ss), ss, cfg, calib

    def test_load_config_returns_correct_instance(self):
        svc, _, cfg, _ = self._make_service()
        self.assertIs(svc.load_config(), cfg)

    def test_load_config_reads_robot_config_key(self):
        svc, ss, _, _ = self._make_service()
        svc.load_config()
        ss.get.assert_called_with("robot_config")

    def test_load_calibration_returns_correct_instance(self):
        svc, _, _, calib = self._make_service()
        self.assertIs(svc.load_calibration(), calib)

    def test_load_calibration_reads_robot_calibration_key(self):
        svc, ss, _, _ = self._make_service()
        svc.load_calibration()
        ss.get.assert_called_with("robot_calibration")

    def test_save_config_delegates_to_settings_service(self):
        svc, ss, _, _ = self._make_service()
        new_cfg = RobotSettings(robot_ip="9.9.9.9")
        svc.save_config(new_cfg)
        ss.save.assert_called_once_with("robot_config", new_cfg)

    def test_save_calibration_delegates_to_settings_service(self):
        svc, ss, _, _ = self._make_service()
        new_calib = RobotCalibrationSettings(z_target=999)
        svc.save_calibration(new_calib)
        ss.save.assert_called_once_with("robot_calibration", new_calib)

    def test_load_config_robot_ip(self):
        svc, _, cfg, _ = self._make_service(RobotSettings(robot_ip="5.5.5.5"))
        self.assertEqual(svc.load_config().robot_ip, "5.5.5.5")

    def test_load_config_robot_tool(self):
        svc, _, _, _ = self._make_service(RobotSettings(robot_tool=7))
        self.assertEqual(svc.load_config().robot_tool, 7)

    def test_load_calibration_z_target(self):
        svc, _, _, _ = self._make_service(calibration=RobotCalibrationSettings(z_target=750))
        self.assertEqual(svc.load_calibration().z_target, 750)


if __name__ == "__main__":
    unittest.main()