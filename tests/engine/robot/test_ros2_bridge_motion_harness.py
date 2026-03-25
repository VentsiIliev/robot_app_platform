import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


_ROS2_SCRIPTS_DIR = Path(
    "/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/fairino5_v6_moveit2_config/scripts"
)
if str(_ROS2_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_ROS2_SCRIPTS_DIR))

try:
    from fairino_ros2_robot import FairinoRos2Robot  # type: ignore
    from motion.execution.motion_queue import MotionQueue  # type: ignore
    from enums import RobotAxis, Direction  # type: ignore
except ImportError as _e:
    raise unittest.SkipTest(f"ROS2 bridge packages not available: {_e}")


class _FakeLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class _FakeQueue:
    def __init__(self, wait_result=0):
        self.wait_result = wait_result
        self.wait_calls = []
        self.queue_size = 0

    def wait_for_task(self, task_id, timeout_s, poll_interval_s=0.05):
        self.wait_calls.append((task_id, timeout_s, poll_interval_s))
        return self.wait_result

    def get_status(self):
        return {"queue_size": self.queue_size}


class _FakeNode:
    def __init__(self):
        self.motion_queue = _FakeQueue()
        self.last_submitted_task_id = 41
        self.is_executing = False
        self.last_move_result = 0
        self.prev_cartesian = [100.0, 200.0, 300.0, 180.0, 0.0, 0.0]
        self.execute_result = 0
        self.execute_calls = []
        self.send_cartesian_goal_calls = []
        self._logger = _FakeLogger()
        self._motion_active = False

    def get_tool_transform(self, tool_id):
        return [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]

    def execute(self, strategy):
        self.execute_calls.append(strategy)
        return self.execute_result

    def get_logger(self):
        return self._logger

    def get_latest_data(self):
        return {"cartesian": MagicMock(tolist=lambda: list(self.prev_cartesian))}

    def is_motion_active(self):
        return self._motion_active

    def has_pending_motion(self):
        return self.motion_queue.get_status()["queue_size"] > 0

    def send_cartesian_goal(self, *args, **kwargs):
        self.send_cartesian_goal_calls.append((args, kwargs))
        return 0


class TestRos2BridgeMotionHarness(unittest.TestCase):

    def test_motion_queue_wait_for_task_returns_completed_result(self):
        queue = MotionQueue(max_size=2)
        task_id = queue.allocate_task_id()
        queue.start_immediate_task(task_id)
        queue.mark_current_complete(-1)

        result = queue.wait_for_task(task_id, timeout_s=0.01, poll_interval_s=0.001)

        self.assertEqual(result, -1)

    def test_move_liner_blocking_waits_for_queued_task_completion(self):
        node = _FakeNode()
        node.execute_result = 2
        node.motion_queue = _FakeQueue(wait_result=0)
        robot = FairinoRos2Robot(ip="0.0.0.0", node=node, workobject=None)

        result = robot.move_liner([10, 20, 30, 180, 0, 0], blocking=True)

        self.assertEqual(result, 0)
        self.assertEqual(len(node.execute_calls), 1)
        self.assertEqual(node.motion_queue.wait_calls[0][0], 41)

    def test_execute_path_blocking_waits_for_queued_task_completion(self):
        node = _FakeNode()
        node.execute_result = 3
        node.motion_queue = _FakeQueue(wait_result=0)
        robot = FairinoRos2Robot(ip="0.0.0.0", node=node, workobject=None)

        result = robot.execute_path([[10, 20, 30], [40, 50, 60]], rx=180, ry=0, rz=0, blocking=True)

        self.assertEqual(result, 0)
        self.assertEqual(len(node.execute_calls), 1)
        self.assertEqual(node.motion_queue.wait_calls[0][0], 41)

    def test_start_jog_rejects_when_motion_is_active(self):
        node = _FakeNode()
        node._motion_active = True
        robot = FairinoRos2Robot(ip="0.0.0.0", node=node, workobject=None)

        result = robot.start_jog(RobotAxis.X, Direction.PLUS, 1.0, 10.0, 10.0)

        self.assertEqual(result, -1)
        self.assertEqual(node.send_cartesian_goal_calls, [])

    def test_start_jog_rejects_when_motion_is_queued(self):
        node = _FakeNode()
        node.motion_queue.queue_size = 1
        robot = FairinoRos2Robot(ip="0.0.0.0", node=node, workobject=None)

        result = robot.start_jog(RobotAxis.X, Direction.PLUS, 1.0, 10.0, 10.0)

        self.assertEqual(result, -1)
        self.assertEqual(node.send_cartesian_goal_calls, [])

    def test_start_jog_sends_non_queueable_goal_when_idle(self):
        node = _FakeNode()
        robot = FairinoRos2Robot(ip="0.0.0.0", node=node, workobject=None)

        result = robot.start_jog(RobotAxis.X, Direction.PLUS, 1.0, 10.0, 10.0)

        self.assertEqual(result, 0)
        self.assertEqual(len(node.send_cartesian_goal_calls), 1)
        _, kwargs = node.send_cartesian_goal_calls[0]
        self.assertEqual(kwargs.get("queue_if_busy"), False)

