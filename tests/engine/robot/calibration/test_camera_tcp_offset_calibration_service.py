import unittest
from unittest.mock import MagicMock

from src.engine.robot.calibration.camera_tcp_offset_calibration_service import (
    CameraTcpOffsetCalibrationService,
)


class TestCameraTcpOffsetCalibrationMotion(unittest.TestCase):
    def test_linear_move_uses_unblended_linear_motion_and_waits(self):
        service = CameraTcpOffsetCalibrationService.__new__(CameraTcpOffsetCalibrationService)
        service._robot = MagicMock()
        service._robot.move_linear.return_value = True
        service._tool = 1
        service._user = 2
        pose = [10.0, 20.0, 30.0, 180.0, 0.0, 90.0]

        result = service._move_linear(pose, 20, 10, "recenter iter 1")

        self.assertTrue(result)
        service._robot.move_linear.assert_called_once_with(
            position=pose,
            tool=1,
            user=2,
            velocity=20,
            acceleration=10,
            blendR=0.0,
            wait_to_reach=True,
        )
        service._robot.move_ptp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
