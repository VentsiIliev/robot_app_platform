import unittest
from unittest.mock import MagicMock
from types import SimpleNamespace

from src.applications.calibration_settings.service.calibration_settings_application_service import (
    CalibrationSettingsApplicationService,
)
from src.applications.calibration_settings.calibration_settings_data import CalibrationSettingsData
from src.engine.common_settings_ids import CommonSettingsID
from src.engine.vision.calibration_vision_settings import CalibrationVisionSettings
from src.engine.vision.camera_settings_serializer import CameraSettings


def _make_settings_service():
    service = MagicMock()
    service.get.side_effect = lambda key: {
        CommonSettingsID.CALIBRATION_VISION_SETTINGS: MagicMock(data={"Calibration": {"Chessboard width": 11}}),
        CommonSettingsID.ROBOT_CALIBRATION: MagicMock(),
        CommonSettingsID.HEIGHT_MEASURING_SETTINGS: MagicMock(),
    }[key]
    return service


class TestCalibrationSettingsApplicationService(unittest.TestCase):
    def test_load_requests_all_calibration_setting_groups(self):
        service = CalibrationSettingsApplicationService(_make_settings_service())
        service.load_settings()
        self.assertEqual(
            service._settings_service.get.call_args_list[0][0][0],
            CommonSettingsID.CALIBRATION_VISION_SETTINGS,
        )
        self.assertIn(
            ((CommonSettingsID.ROBOT_CALIBRATION,),),
            tuple((call.args,) for call in service._settings_service.get.call_args_list),
        )
        self.assertIn(
            ((CommonSettingsID.HEIGHT_MEASURING_SETTINGS,),),
            tuple((call.args,) for call in service._settings_service.get.call_args_list),
        )

    def test_save_persists_all_calibration_setting_groups(self):
        settings_service = _make_settings_service()
        service = CalibrationSettingsApplicationService(settings_service)
        data = service.load_settings()

        service.save_settings(data)

        saved_ids = [call.args[0] for call in settings_service.save.call_args_list]
        self.assertIn(CommonSettingsID.CALIBRATION_VISION_SETTINGS, saved_ids)
        self.assertIn(CommonSettingsID.ROBOT_CALIBRATION, saved_ids)
        self.assertIn(CommonSettingsID.HEIGHT_MEASURING_SETTINGS, saved_ids)

    def test_save_pushes_merged_calibration_settings_to_live_vision_runtime(self):
        settings_service = MagicMock()
        live_camera_settings = CameraSettings(
            data={
                "Index": 2,
                "Calibration": {
                    "Chessboard width": 11,
                    "Chessboard height": 7,
                    "Square size (mm)": 9.0,
                },
            }
        )
        settings_service.get.side_effect = lambda key: {
            CommonSettingsID.VISION_CAMERA_SETTINGS: live_camera_settings,
        }[key]
        vision_service = MagicMock()
        service = CalibrationSettingsApplicationService(settings_service, vision_service)

        data = CalibrationSettingsData(
            vision=CalibrationVisionSettings(
                chessboard_width=33,
                chessboard_height=21,
                square_size_mm=25.0,
                reference_board_mode="charuco",
                charuco_board_width=33,
                charuco_board_height=21,
                charuco_square_size_mm=25.0,
                charuco_marker_size_mm=18.0,
            ),
            robot=MagicMock(),
            height=MagicMock(),
        )

        service.save_settings(data)

        vision_service.update_settings.assert_called_once_with(
            {
                "Index": 2,
                "Calibration": {
                    "Chessboard width": 33,
                    "Chessboard height": 21,
                    "Square size (mm)": 25.0,
                    "Reference board mode": "charuco",
                    "ChArUco board width": 33,
                    "ChArUco board height": 21,
                    "ChArUco square size (mm)": 25.0,
                    "ChArUco marker size (mm)": 18.0,
                    "Skip frames": 30,
                },
            }
        )

    def test_workobject_solve_computes_rz_from_center_to_x_point(self):
        settings_service = MagicMock()
        settings_service.get.return_value = SimpleNamespace(robot_user=0)
        robot_service = MagicMock()
        robot_service.get_current_base_tcp_position.side_effect = [
            [100.0, 200.0, 300.0, 1.0, 2.0, 3.0],
            [100.0, 250.0, 300.0, 1.0, 2.0, 3.0],
            [50.0, 200.0, 300.0, 1.0, 2.0, 3.0],
        ]
        service = CalibrationSettingsApplicationService(settings_service, robot_service=robot_service)

        service.capture_workobject_point("center")
        service.capture_workobject_point("x")
        service.capture_workobject_point("y")
        ok, msg, payload = service.solve_workobject(2, "fixture")

        self.assertTrue(ok)
        self.assertIn("rz=90.000", msg)
        self.assertEqual(payload["name"], "fixture")
        self.assertEqual(payload["transform"], [100.0, 200.0, 300.0, 0.0, 0.0, 90.0])

    def test_workobject_solve_computes_full_orientation_for_tilted_surface(self):
        settings_service = MagicMock()
        settings_service.get.return_value = SimpleNamespace(robot_user=0)
        service = CalibrationSettingsApplicationService(settings_service)
        # Frame produced by XYZ Euler angles rx=-10, ry=20, rz=30 degrees.
        service._workobject_points = {
            "center": [10.0, 20.0, 30.0, 0.0, 0.0, 0.0],
            "x": [91.37976813493738, 66.98463103929542, -4.20201433256687, 0.0, 0.0, 0.0],
            "y": [-44.38381424823255, 102.31729446455009, 13.682408883346518, 0.0, 0.0, 0.0],
        }

        ok, msg, payload = service.solve_workobject(2, "tilted_fixture")

        self.assertTrue(ok, msg)
        self.assertIn("rx=-10.000", msg)
        for actual, expected in zip(payload["transform"], [10.0, 20.0, 30.0, -10.0, 20.0, 30.0]):
            self.assertAlmostEqual(actual, expected, places=5)
        self.assertEqual(len(payload["surface_normal"]), 3)

    def test_workobject_capture_refuses_nonzero_workobject_user(self):
        settings_service = MagicMock()
        settings_service.get.return_value = SimpleNamespace(robot_tool=0, robot_user=2)
        robot_service = MagicMock()
        service = CalibrationSettingsApplicationService(settings_service, robot_service=robot_service)

        ok, msg, payload = service.capture_workobject_point("center")

        self.assertFalse(ok)
        self.assertIn("WorkObject/User ID is 2", msg)
        self.assertEqual(payload, {})
        robot_service.get_current_position.assert_not_called()

    def test_workobject_solve_rejects_y_point_on_negative_y_side(self):
        settings_service = MagicMock()
        settings_service.get.return_value = SimpleNamespace(robot_user=0)
        service = CalibrationSettingsApplicationService(settings_service)
        service._workobject_points = {
            "center": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "x": [100.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "y": [0.0, -100.0, 0.0, 0.0, 0.0, 0.0],
        }

        ok, msg, payload = service.solve_workobject(1)

        self.assertFalse(ok)
        self.assertIn("-Y side", msg)
        self.assertEqual({}, payload)

    def test_workobject_solve_rejects_non_perpendicular_axes(self):
        settings_service = MagicMock()
        settings_service.get.return_value = SimpleNamespace(robot_user=0)
        service = CalibrationSettingsApplicationService(settings_service)
        service._workobject_points = {
            "center": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "x": [100.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "y": [100.0, 100.0, 0.0, 0.0, 0.0, 0.0],
        }

        ok, msg, payload = service.solve_workobject(1)

        self.assertFalse(ok)
        self.assertIn("45.0 deg", msg)
        self.assertEqual({}, payload)

    def test_workobject_capture_uses_base_tcp_pose(self):
        settings_service = MagicMock()
        settings_service.get.return_value = SimpleNamespace(robot_tool=0, robot_user=0)
        robot_service = MagicMock()
        robot_service.get_current_base_tcp_position.return_value = [
            10.0, 20.0, 30.0, 0.0, 0.0, 0.0
        ]
        robot_service.get_current_flange_position.return_value = [
            999.0, 999.0, 999.0, 0.0, 0.0, 0.0
        ]
        service = CalibrationSettingsApplicationService(settings_service, robot_service=robot_service)

        ok, msg, payload = service.capture_workobject_point("center")

        self.assertTrue(ok)
        self.assertEqual(payload["pose"], [10.0, 20.0, 30.0, 0.0, 0.0, 0.0])
        robot_service.get_current_flange_position.assert_not_called()

    def test_workobject_capture_allows_calibrated_nonzero_tool_with_user_zero(self):
        settings_service = MagicMock()
        settings_service.get.return_value = SimpleNamespace(robot_tool=1, robot_user=0)
        robot_service = MagicMock()
        robot_service.get_current_base_tcp_position.return_value = [
            10.0, 20.0, 30.0, 0.0, 0.0, 0.0
        ]
        service = CalibrationSettingsApplicationService(settings_service, robot_service=robot_service)

        ok, msg, payload = service.capture_workobject_point("center")

        self.assertTrue(ok)
        self.assertEqual(payload["pose"], [10.0, 20.0, 30.0, 0.0, 0.0, 0.0])
        robot_service.set_active_tool.assert_called_once_with(1)

    def test_workobject_capture_rejects_tool_change_after_center(self):
        robot_config = SimpleNamespace(robot_tool=1, robot_user=0)
        settings_service = MagicMock()
        settings_service.get.return_value = robot_config
        robot_service = MagicMock()
        robot_service.set_active_tool.return_value = True
        robot_service.get_current_base_tcp_position.return_value = [10.0, 20.0, 30.0, 0.0, 0.0, 0.0]
        service = CalibrationSettingsApplicationService(settings_service, robot_service=robot_service)

        center_ok, _, _ = service.capture_workobject_point("center")
        robot_config.robot_tool = 0
        x_ok, msg, payload = service.capture_workobject_point("x")

        self.assertTrue(center_ok)
        self.assertFalse(x_ok)
        self.assertIn("started with Tool ID 1", msg)
        self.assertEqual({}, payload)
        self.assertEqual(1, robot_service.get_current_base_tcp_position.call_count)

    def test_workobject_save_updates_runtime_robot_settings_and_active_workobject(self):
        robot_config = SimpleNamespace(robot_user=0)
        settings_service = MagicMock()
        settings_service.get.return_value = robot_config
        robot_service = MagicMock()
        robot_service.get_current_base_tcp_position.side_effect = [
            [10.0, 20.0, 30.0, 0.0, 0.0, 0.0],
            [20.0, 20.0, 30.0, 0.0, 0.0, 0.0],
            [10.0, 30.0, 30.0, 0.0, 0.0, 0.0],
        ]
        robot_service.update_workobject_registry.return_value = 0
        robot_service.set_active_workobject.return_value = True
        messaging = MagicMock()
        service = CalibrationSettingsApplicationService(
            settings_service,
            robot_service=robot_service,
            messaging=messaging,
        )

        service.capture_workobject_point("center")
        service.capture_workobject_point("x")
        service.capture_workobject_point("y")
        ok, msg, payload = service.save_workobject(4, "WOBJ_FIXTURE")

        self.assertTrue(ok)
        self.assertIn("Saved WorkObject", msg)
        robot_service.update_workobject_registry.assert_called_once_with(
            4,
            name="WOBJ_FIXTURE",
            transform=[10.0, 20.0, 30.0, 0.0, 0.0, 0.0],
            persist=True,
        )
        self.assertEqual(robot_config.robot_user, 4)
        settings_service.save.assert_called_once_with(CommonSettingsID.ROBOT_CONFIG, robot_config)
        messaging.publish.assert_called_once_with(
            "robot/config_changed",
            {"robot_user": 4},
        )
        robot_service.set_active_workobject.assert_called_once_with(4)
        self.assertEqual(payload["user_id"], 4)
