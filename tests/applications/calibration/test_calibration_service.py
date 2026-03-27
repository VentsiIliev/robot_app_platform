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

    def test_measure_area_grid_prefers_area_observer_pose(self):
        marker_service = MagicMock()
        marker_service.measure_area_grid.return_value = (True, "ok")
        work_area_service = MagicMock()
        work_area_service.get_active_area_id.return_value = "pickup"
        height_service = MagicMock()
        height_service.get_calibration_data.return_value = MagicMock(
            robot_initial_position=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        )

        svc = CalibrationApplicationService(
            _make_vision(),
            MagicMock(),
            height_service=height_service,
            work_area_service=work_area_service,
            marker_height_mapping_service=marker_service,
            observer_group_provider=lambda area_id: "HOME" if area_id == "pickup" else None,
            observer_position_provider=lambda group: [10.0, 20.0, 30.0, 40.0, 50.0, 60.0] if group == "HOME" else None,
        )
        svc.is_calibrated = MagicMock(return_value=True)

        ok, msg = svc.measure_area_grid("pickup", [(0.0, 0.0)] * 4, 2, 2)

        self.assertTrue(ok)
        self.assertEqual(msg, "ok")
        marker_service.measure_area_grid.assert_called_once()
        self.assertEqual(
            marker_service.measure_area_grid.call_args.kwargs["measurement_pose"],
            [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
        )

    def test_verify_height_model_prefers_area_observer_pose(self):
        marker_service = MagicMock()
        marker_service.verify_height_model.return_value = (True, "ok")
        height_service = MagicMock()
        height_service.get_calibration_data.return_value = MagicMock(
            robot_initial_position=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        )

        svc = CalibrationApplicationService(
            _make_vision(),
            MagicMock(),
            height_service=height_service,
            marker_height_mapping_service=marker_service,
            observer_group_provider=lambda area_id: "HOME" if area_id == "pickup" else None,
            observer_position_provider=lambda group: [10.0, 20.0, 30.0, 40.0, 50.0, 60.0] if group == "HOME" else None,
        )

        ok, msg = svc.verify_height_model("pickup")

        self.assertTrue(ok)
        self.assertEqual(msg, "ok")
        marker_service.verify_height_model.assert_called_once_with(
            "pickup",
            measurement_pose=[10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
        )

    def test_verify_area_grid_uses_height_measurement_pose_instead_of_observer_pose(self):
        robot_service = MagicMock()
        robot_service.get_current_position.return_value = [100.0, 200.0, 300.0, 10.0, 20.0, 30.0]
        robot_service.are_safety_walls_enabled.return_value = False
        robot_service.validate_pose.return_value = {"reachable": True, "success": True}

        transformer = MagicMock()
        transformer.is_available.return_value = True
        transformer.transform.side_effect = [
            (10.0, 20.0),
            (30.0, 40.0),
            (50.0, 60.0),
            (70.0, 80.0),
            (0.0, 0.0),
            (1.0, 0.0),
            (1.0, 1.0),
            (0.0, 1.0),
        ]

        height_service = MagicMock()
        height_service.is_calibrated.return_value = True
        height_service.get_calibration_data.return_value = MagicMock(
            robot_initial_position=[1.0, 2.0, 333.0, 44.0, 55.0, 66.0]
        )

        vision = _make_vision()
        vision.get_camera_width.return_value = 1000.0
        vision.get_camera_height.return_value = 1000.0

        svc = CalibrationApplicationService(
            vision,
            MagicMock(),
            robot_service=robot_service,
            height_service=height_service,
            transformer=transformer,
            observer_group_provider=lambda area_id: "SPRAY_OBSERVER",
            observer_position_provider=lambda group: [10.0, 20.0, 819.378, 179.915, 0.011, 0.001],
        )
        svc.is_calibrated = MagicMock(return_value=True)
        svc.generate_area_grid = MagicMock(
            return_value=[(0.1, 0.2), (0.3, 0.4), (0.5, 0.6), (0.7, 0.8)]
        )

        ok, _, _ = svc.verify_area_grid(
            corners_norm=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
            rows=2,
            cols=2,
        )

        self.assertTrue(ok)
        first_validate_call = robot_service.validate_pose.call_args_list[0]
        self.assertEqual(
            first_validate_call.args[1],
            [10.0, 20.0, 333.0, 44.0, 55.0, 66.0],
        )


if __name__ == "__main__":
    unittest.main()
