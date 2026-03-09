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


def _make_svc(capture=None, calibrate=None):
    vs = _make_vision(capture=capture, calibrate=calibrate)
    pc = MagicMock()
    return CalibrationApplicationService(vs, pc), vs, pc


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

    def test_service_with_none_vision_raises_on_call(self):
        svc = CalibrationApplicationService(None, MagicMock())
        with self.assertRaises(Exception):
            svc.capture_calibration_image()


if __name__ == "__main__":
    unittest.main()
