import unittest
from unittest.mock import MagicMock

from src.applications.calibration_settings.service.calibration_settings_application_service import (
    CalibrationSettingsApplicationService,
)
from src.engine.common_settings_ids import CommonSettingsID


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
