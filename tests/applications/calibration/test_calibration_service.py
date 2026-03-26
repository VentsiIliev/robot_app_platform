import unittest
from unittest.mock import MagicMock

from src.applications.calibration_settings.calibration_settings_data import CalibrationSettingsData
from src.applications.calibration.service.i_calibration_service import ICalibrationService
from src.applications.calibration.service.stub_calibration_service import StubCalibrationService
from src.applications.calibration.service.calibration_application_service import CalibrationApplicationService
from src.engine.robot.configuration import RobotCalibrationSettings
from src.engine.robot.height_measuring.settings import HeightMeasuringModuleSettings
from src.engine.vision.calibration_vision_settings import CalibrationVisionSettings


def _make_calibration_settings():
    return CalibrationSettingsData(
        vision=CalibrationVisionSettings(chessboard_width=11),
        robot=RobotCalibrationSettings(),
        height=HeightMeasuringModuleSettings(),
    )


def _make_vision(capture=None, calibrate=None):
    vs = MagicMock()
    vs.capture_calibration_image.return_value = capture or (True, "ok")
    vs.calibrate_camera.return_value = calibrate or (True, "ok")
    vs.camera_to_robot_matrix_path = "/tmp/cameraToRobotMatrix_camera_center.npy"
    return vs


def _make_svc(capture=None, calibrate=None, calibrator=None, calibration_settings_service=None):
    vs = _make_vision(capture=capture, calibrate=calibrate)
    pc = MagicMock()
    return (
        CalibrationApplicationService(
            vs,
            pc,
            camera_tcp_offset_calibrator=calibrator,
            calibration_settings_service=calibration_settings_service,
        ),
        vs,
        pc,
    )


class TestStubCalibrationService(unittest.TestCase):

    def setUp(self):
        self._stub = StubCalibrationService()

    def test_implements_interface(self):
        self.assertIsInstance(self._stub, ICalibrationService)

    def test_capture_returns_success(self):
        ok, msg = self._stub.capture_calibration_image()
        self.assertTrue(ok)
        self.assertIsInstance(msg, str)

    def test_calibrate_camera_returns_success(self):
        ok, msg = self._stub.calibrate_camera()
        self.assertTrue(ok)
        self.assertIsInstance(msg, str)

    def test_calibrate_robot_returns_success(self):
        ok, msg = self._stub.calibrate_robot()
        self.assertTrue(ok)
        self.assertIsInstance(msg, str)

    def test_calibrate_camera_and_robot_returns_success(self):
        ok, msg = self._stub.calibrate_camera_and_robot()
        self.assertTrue(ok)
        self.assertIsInstance(msg, str)

    def test_calibrate_camera_tcp_offset_returns_success(self):
        ok, msg = self._stub.calibrate_camera_tcp_offset()
        self.assertTrue(ok)
        self.assertIsInstance(msg, str)

    def test_load_calibration_settings_returns_settings(self):
        settings = self._stub.load_calibration_settings()
        self.assertIsNotNone(settings)


class TestCalibrationApplicationServiceDelegation(unittest.TestCase):

    def test_capture_delegates_to_vision(self):
        svc, vs, _ = _make_svc(capture=(True, "captured"))
        ok, msg = svc.capture_calibration_image()
        vs.capture_calibration_image.assert_called_once()
        self.assertTrue(ok)
        self.assertEqual(msg, "captured")

    def test_calibrate_camera_delegates_to_vision(self):
        svc, vs, _ = _make_svc(calibrate=(True, "cam ok"))
        ok, msg = svc.calibrate_camera()
        vs.calibrate_camera.assert_called_once()
        self.assertTrue(ok)
        self.assertEqual(msg, "cam ok")

    def test_calibrate_robot_calls_process_controller_and_returns_success(self):
        svc, _, pc = _make_svc()
        ok, msg = svc.calibrate_robot()
        pc.calibrate.assert_called_once()
        self.assertTrue(ok)

    def test_calibrate_camera_and_robot_short_circuits_on_camera_failure(self):
        svc, vs, _ = _make_svc(calibrate=(False, "no cam"))
        ok, msg = svc.calibrate_camera_and_robot()
        self.assertFalse(ok)
        self.assertIn("Camera calibration failed", msg)
        self.assertIn("no cam", msg)

    def test_calibrate_camera_and_robot_starts_robot_on_camera_success(self):
        svc, vs, pc = _make_svc(calibrate=(True, "cam ok"))
        ok, msg = svc.calibrate_camera_and_robot()
        self.assertTrue(ok)
        pc.calibrate.assert_called_once()

    def test_calibrate_camera_and_robot_calls_camera_first(self):
        svc, vs, _ = _make_svc(calibrate=(False, "fail"))
        svc.calibrate_camera_and_robot()
        vs.calibrate_camera.assert_called_once()

    def test_calibrate_camera_and_robot_does_not_call_controller_on_camera_failure(self):
        svc, vs, pc = _make_svc(calibrate=(False, "fail"))
        svc.calibrate_camera_and_robot()
        pc.calibrate.assert_not_called()

    def test_calibrate_camera_tcp_offset_requires_existing_calibration(self):
        svc, vs, _ = _make_svc()
        ok, msg = svc.calibrate_camera_tcp_offset()
        self.assertFalse(ok)
        self.assertIn("System not calibrated", msg)

    def test_calibrate_camera_tcp_offset_delegates_to_calibrator_when_calibrated(self):
        calibrator = MagicMock()
        calibrator.calibrate.return_value = (True, "tcp ok")
        svc, vs, _ = _make_svc(calibrator=calibrator)
        svc.is_calibrated = MagicMock(return_value=True)

        ok, msg = svc.calibrate_camera_tcp_offset()

        self.assertTrue(ok)
        self.assertEqual(msg, "tcp ok")
        calibrator.calibrate.assert_called_once()

    def test_stop_calibration_stops_camera_tcp_calibrator(self):
        calibrator = MagicMock()
        svc, _, pc = _make_svc(calibrator=calibrator)

        svc.stop_calibration()

        pc.stop_calibration.assert_called_once()
        calibrator.stop.assert_called_once()

    def test_service_with_none_vision_raises_on_call(self):
        svc = CalibrationApplicationService(None, MagicMock())
        with self.assertRaises(Exception):
            svc.capture_calibration_image()

    def test_load_calibration_settings_delegates_to_bridge_service(self):
        settings_service = MagicMock()
        settings = _make_calibration_settings()
        settings_service.load_settings.return_value = settings
        svc, _, _ = _make_svc(calibration_settings_service=settings_service)

        loaded = svc.load_calibration_settings()

        settings_service.load_settings.assert_called_once()
        self.assertIs(loaded, settings)

    def test_save_calibration_settings_delegates_to_bridge_service(self):
        settings_service = MagicMock()
        settings = _make_calibration_settings()
        svc, _, _ = _make_svc(calibration_settings_service=settings_service)

        svc.save_calibration_settings(settings)

        settings_service.save_settings.assert_called_once_with(settings)


if __name__ == "__main__":
    unittest.main()
