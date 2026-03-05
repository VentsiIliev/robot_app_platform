import unittest
from unittest.mock import MagicMock

from src.applications.calibration.service.i_calibration_service import ICalibrationService
from src.applications.calibration.service.stub_calibration_service import StubCalibrationService
from src.applications.calibration.service.calibration_application_service import CalibrationApplicationService


def _make_vision(capture=None, calibrate=None):
    vs = MagicMock()
    vs.capture_calibration_image.return_value = capture or (True, "ok")
    vs.calibrate_camera.return_value = calibrate or (True, "ok")
    return vs


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


class TestCalibrationApplicationServiceDelegation(unittest.TestCase):

    def test_capture_delegates_to_vision(self):
        vs = _make_vision(capture=(True, "captured"))
        svc = CalibrationApplicationService(vs)
        ok, msg = svc.capture_calibration_image()
        vs.capture_calibration_image.assert_called_once()
        self.assertTrue(ok)
        self.assertEqual(msg, "captured")

    def test_calibrate_camera_delegates_to_vision(self):
        vs = _make_vision(calibrate=(True, "cam ok"))
        svc = CalibrationApplicationService(vs)
        ok, msg = svc.calibrate_camera()
        vs.calibrate_camera.assert_called_once()
        self.assertTrue(ok)
        self.assertEqual(msg, "cam ok")

    def test_calibrate_robot_returns_not_implemented(self):
        svc = CalibrationApplicationService(MagicMock())
        ok, msg = svc.calibrate_robot()
        self.assertFalse(ok)
        self.assertIn("not yet implemented", msg.lower())

    def test_calibrate_camera_and_robot_short_circuits_on_camera_failure(self):
        vs = _make_vision(calibrate=(False, "no cam"))
        svc = CalibrationApplicationService(vs)
        ok, msg = svc.calibrate_camera_and_robot()
        self.assertFalse(ok)
        self.assertIn("Camera calibration failed", msg)
        self.assertIn("no cam", msg)

    def test_calibrate_camera_and_robot_fails_on_robot_failure(self):
        vs = _make_vision(calibrate=(True, "cam ok"))
        svc = CalibrationApplicationService(vs)
        ok, msg = svc.calibrate_camera_and_robot()
        # robot calibration is not implemented → always fails
        self.assertFalse(ok)
        self.assertIn("Robot calibration failed", msg)

    def test_calibrate_camera_and_robot_calls_camera_first(self):
        vs = _make_vision(calibrate=(False, "fail"))
        svc = CalibrationApplicationService(vs)
        svc.calibrate_camera_and_robot()
        vs.calibrate_camera.assert_called_once()

    def test_calibrate_camera_and_robot_does_not_call_robot_on_camera_failure(self):
        vs = _make_vision(calibrate=(False, "fail"))
        svc = CalibrationApplicationService(vs)
        svc.calibrate_camera_and_robot()
        # robot method has no backing vision call — just ensure camera stopped it
        vs.capture_calibration_image.assert_not_called()

    def test_service_with_none_vision_raises_on_call(self):
        svc = CalibrationApplicationService(None)
        with self.assertRaises(Exception):
            svc.capture_calibration_image()


if __name__ == "__main__":
    unittest.main()