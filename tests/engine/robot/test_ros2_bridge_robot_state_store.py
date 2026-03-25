import sys
import unittest
from pathlib import Path


_ROS2_SCRIPTS_DIR = Path(
    "/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/fairino5_v6_moveit2_config/scripts"
)
if str(_ROS2_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_ROS2_SCRIPTS_DIR))

try:
    from status.robot_state_store import RobotStateStore  # type: ignore
except ImportError as _e:
    raise unittest.SkipTest(f"ROS2 bridge packages not available: {_e}")


class TestRos2BridgeRobotStateStore(unittest.TestCase):

    def test_round_trips_prev_cartesian(self):
        store = RobotStateStore()
        pose = [1.0, 2.0, 3.0, 180.0, 0.0, 0.0]

        store.set_prev_cartesian(pose)

        self.assertEqual(store.get_prev_cartesian(), pose)

    def test_round_trips_current_joint_state(self):
        store = RobotStateStore()
        joint_state = object()

        store.set_current_joint_state(joint_state)

        self.assertIs(store.get_current_joint_state(), joint_state)

    def test_latest_data_returns_copy(self):
        store = RobotStateStore()
        payload = {"cartesian": [1, 2, 3]}
        store.set_latest_data(payload)

        resolved = store.get_latest_data()
        resolved["cartesian"] = [9, 9, 9]

        self.assertEqual(store.get_latest_data()["cartesian"], [1, 2, 3])
