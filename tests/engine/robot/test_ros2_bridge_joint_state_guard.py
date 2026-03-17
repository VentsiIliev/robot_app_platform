import sys
import unittest
from pathlib import Path


_ROS2_SCRIPTS_DIR = Path(
    "/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/fairino5_v6_moveit2_config/scripts"
)
if str(_ROS2_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_ROS2_SCRIPTS_DIR))

from motion.planning.single_target import send_cartesian_goal  # type: ignore
from motion.planning.trajectory import send_path_cartesian  # type: ignore


class _FakeLogger:
    def __init__(self):
        self.errors = []

    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, message, *args, **kwargs):
        self.errors.append(message)


class _FakeRobotController:
    def __init__(self):
        self.current_joint_state = None
        self.prev_cartesian = [0.0, 0.0, 0.0, 180.0, 0.0, 0.0]
        self.T_tool = None
        self.force_safety_update_calls = 0
        self._logger = _FakeLogger()

    def force_safety_update(self):
        self.force_safety_update_calls += 1

    def get_logger(self):
        return self._logger


class TestRos2BridgeJointStateGuard(unittest.TestCase):
    def test_single_target_rejects_when_joint_state_missing(self):
        rc = _FakeRobotController()

        result = send_cartesian_goal(rc, 10.0, 20.0, 30.0, 180.0, 0.0, 0.0, 0.6, 0.4)

        self.assertEqual(result, -11)
        self.assertEqual(rc.force_safety_update_calls, 1)
        self.assertIn("[MOVE] No current joint state available", rc.get_logger().errors)

    def test_path_rejects_when_joint_state_missing(self):
        rc = _FakeRobotController()

        result = send_path_cartesian(
            rc,
            [[10.0, 20.0, 30.0], [40.0, 50.0, 60.0]],
            180.0,
            0.0,
            0.0,
            0.6,
            0.4,
        )

        self.assertEqual(result, -11)
        self.assertEqual(rc.force_safety_update_calls, 1)
        self.assertIn("[EXECUTE_PATH] No current joint state available", rc.get_logger().errors)
