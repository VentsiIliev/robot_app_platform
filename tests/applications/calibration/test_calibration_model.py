import unittest
from unittest.mock import MagicMock

from src.applications.calibration.model.calibration_model import CalibrationModel
from src.applications.calibration_settings.calibration_settings_data import CalibrationSettingsData
from src.applications.calibration.service.i_calibration_service import ICalibrationService
from src.applications.base.i_application_model import IApplicationModel
from src.engine.robot.configuration import RobotCalibrationSettings
from src.engine.robot.height_measuring.settings import HeightMeasuringModuleSettings
from src.engine.vision.calibration_vision_settings import CalibrationVisionSettings


def _make_calibration_settings():
    return CalibrationSettingsData(
        vision=CalibrationVisionSettings(chessboard_width=11),
        robot=RobotCalibrationSettings(),
        height=HeightMeasuringModuleSettings(),
    )


def _make_service(**overrides):
    svc = MagicMock(spec=ICalibrationService)
    svc.load_calibration_settings.return_value       = overrides.get("settings", _make_calibration_settings())
    svc.capture_calibration_image.return_value  = overrides.get("capture",  (True,  "captured"))
    svc.calibrate_camera.return_value            = overrides.get("camera",   (True,  "cam ok"))
    svc.calibrate_robot.return_value             = overrides.get("robot",    (False, "not impl"))
    svc.calibrate_camera_and_robot.return_value  = overrides.get("sequence", (True,  "all ok"))
    svc.start_tool_tcp_calibration.return_value  = overrides.get("tool_start", (True, "tool start"))
    svc.capture_tool_tcp_sample.return_value     = overrides.get("tool_capture", (True, "tool capture"))
    svc.solve_tool_tcp_calibration.return_value  = overrides.get("tool_solve", (True, "tool solve", {}))
    svc.save_tool_tcp_calibration.return_value   = overrides.get("tool_save", (True, "tool save"))
    svc.clear_tool_tcp_calibration.return_value  = overrides.get("tool_clear", (True, "tool clear"))
    return svc


class TestCalibrationModelInterface(unittest.TestCase):

    def test_implements_i_application_model(self):
        model = CalibrationModel(_make_service())
        self.assertIsInstance(model, IApplicationModel)


class TestCalibrationModelLoad(unittest.TestCase):

    def test_load_is_no_op(self):
        model = CalibrationModel(_make_service())
        model.load()   # must not raise


class TestCalibrationModelDelegation(unittest.TestCase):

    def test_capture_delegates_to_service(self):
        svc = _make_service(capture=(True, "snap"))
        ok, msg = CalibrationModel(svc).capture_calibration_image()
        svc.capture_calibration_image.assert_called_once()
        self.assertTrue(ok)
        self.assertEqual(msg, "snap")

    def test_calibrate_camera_delegates_to_service(self):
        svc = _make_service(camera=(True, "cam"))
        ok, msg = CalibrationModel(svc).calibrate_camera()
        svc.calibrate_camera.assert_called_once()
        self.assertTrue(ok)
        self.assertEqual(msg, "cam")

    def test_calibrate_robot_delegates_to_service(self):
        svc = _make_service(robot=(False, "no robot"))
        ok, msg = CalibrationModel(svc).calibrate_robot()
        svc.calibrate_robot.assert_called_once()
        self.assertFalse(ok)
        self.assertEqual(msg, "no robot")

    def test_calibrate_camera_and_robot_delegates_to_service(self):
        svc = _make_service(sequence=(True, "done"))
        ok, msg = CalibrationModel(svc).calibrate_camera_and_robot()
        svc.calibrate_camera_and_robot.assert_called_once()
        self.assertTrue(ok)
        self.assertEqual(msg, "done")

    def test_capture_passes_through_failure(self):
        svc = _make_service(capture=(False, "no image"))
        ok, msg = CalibrationModel(svc).capture_calibration_image()
        self.assertFalse(ok)
        self.assertEqual(msg, "no image")

    def test_save_is_no_op(self):
        model = CalibrationModel(_make_service())
        model.save()  # must not raise

    def test_load_calibration_settings_delegates_to_service(self):
        settings = _make_calibration_settings()
        svc = _make_service(settings=settings)
        loaded = CalibrationModel(svc).load_calibration_settings()
        svc.load_calibration_settings.assert_called_once()
        self.assertIs(loaded, settings)

    def test_save_calibration_settings_delegates_to_service(self):
        settings = _make_calibration_settings()
        svc = _make_service()
        CalibrationModel(svc).save_calibration_settings(settings)
        svc.save_calibration_settings.assert_called_once_with(settings)

    def test_tool_tcp_methods_delegate_to_service(self):
        svc = _make_service(
            tool_start=(True, "started"),
            tool_capture=(True, "captured"),
            tool_solve=(True, "solved", {"sample_count": 6}),
            tool_save=(True, "saved"),
            tool_clear=(True, "cleared"),
        )
        model = CalibrationModel(svc)

        self.assertEqual(model.start_tool_tcp_calibration(2), (True, "started"))
        self.assertEqual(model.capture_tool_tcp_sample(), (True, "captured"))
        self.assertEqual(model.solve_tool_tcp_calibration(), (True, "solved", {"sample_count": 6}))
        self.assertEqual(model.save_tool_tcp_calibration(), (True, "saved"))
        self.assertEqual(model.clear_tool_tcp_calibration(), (True, "cleared"))

        svc.start_tool_tcp_calibration.assert_called_once_with(2)
        svc.capture_tool_tcp_sample.assert_called_once()
        svc.solve_tool_tcp_calibration.assert_called_once()
        svc.save_tool_tcp_calibration.assert_called_once()
        svc.clear_tool_tcp_calibration.assert_called_once()


if __name__ == "__main__":
    unittest.main()
