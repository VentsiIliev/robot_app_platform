import unittest
from unittest.mock import MagicMock

from src.applications.calibration.model.calibration_model import CalibrationModel
from src.applications.calibration.service.i_calibration_service import ICalibrationService
from src.applications.base.i_application_model import IApplicationModel


def _make_service(**overrides):
    svc = MagicMock(spec=ICalibrationService)
    svc.capture_calibration_image.return_value  = overrides.get("capture",  (True,  "captured"))
    svc.calibrate_camera.return_value            = overrides.get("camera",   (True,  "cam ok"))
    svc.calibrate_robot.return_value             = overrides.get("robot",    (False, "not impl"))
    svc.calibrate_camera_and_robot.return_value  = overrides.get("sequence", (True,  "all ok"))
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


if __name__ == "__main__":
    unittest.main()