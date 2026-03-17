import sys
import unittest
from pathlib import Path


_ROS2_SCRIPTS_DIR = Path(
    "/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/fairino5_v6_moveit2_config/scripts"
)
if str(_ROS2_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_ROS2_SCRIPTS_DIR))

from motion.planning.planner_context import PlannerContext  # type: ignore
from motion.execution.motion_coordinator import MotionCoordinator  # type: ignore
from motion.execution.motion_queue import MotionQueue  # type: ignore
from status.robot_state_store import RobotStateStore  # type: ignore


class _FakeLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class _FakeClock:
    pass


class _FakeNode:
    def __init__(self):
        self._logger = _FakeLogger()
        self._clock = _FakeClock()

    def get_logger(self):
        return self._logger

    def get_clock(self):
        return self._clock

    def create_client(self, *args, **kwargs):
        return ("client", args, kwargs)


class TestRos2BridgePlannerContext(unittest.TestCase):

    def setUp(self):
        self.node = _FakeNode()
        self.state_store = RobotStateStore()
        self.motion = MotionCoordinator(node=self.node, motion_queue=MotionQueue(max_size=4))
        self.context = PlannerContext(
            node=self.node,
            state_store=self.state_store,
            motion_coordinator=self.motion,
            motion_queue=MotionQueue(max_size=4),
            safety_manager=object(),
            cart_path_client=object(),
            ipp_client=object(),
            trajectory_executor=object(),
        )

    def test_proxies_motion_state(self):
        self.context.is_executing = True
        self.context.plan_generation = 7
        self.context.last_move_result = -3

        self.assertTrue(self.motion.is_executing)
        self.assertEqual(self.motion.plan_generation, 7)
        self.assertEqual(self.motion.last_move_result, -3)

    def test_proxies_state_store(self):
        joint_state = object()
        self.context.current_joint_state = joint_state
        self.context.prev_cartesian = [1, 2, 3]
        self.context.get_latest_data()
        self.context._state_store.set_latest_data({"cartesian": [1, 2, 3]})

        self.assertIs(self.context.current_joint_state, joint_state)
        self.assertEqual(self.context.prev_cartesian, [1, 2, 3])
        self.assertEqual(self.context.get_latest_data()["cartesian"], [1, 2, 3])

    def test_exposes_node_logger_clock_and_client_factory(self):
        self.assertIs(self.context.get_logger(), self.node.get_logger())
        self.assertIs(self.context.get_clock(), self.node.get_clock())
        self.assertEqual(self.context.create_client("svc"), ("client", ("svc",), {}))
