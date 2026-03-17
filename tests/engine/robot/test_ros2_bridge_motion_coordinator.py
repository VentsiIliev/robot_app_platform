import sys
import unittest
from pathlib import Path


_ROS2_SCRIPTS_DIR = Path(
    "/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/fairino5_v6_moveit2_config/scripts"
)
if str(_ROS2_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_ROS2_SCRIPTS_DIR))

from motion.execution.motion_coordinator import MotionCoordinator  # type: ignore
from motion.execution.motion_queue import MotionQueue  # type: ignore


class _FakeLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class _FakeNode:
    def __init__(self):
        self._logger = _FakeLogger()

    def get_logger(self):
        return self._logger


class _QueueableStrategy:
    queueable = True

    def __init__(self):
        self.calls = []

    def execute(self, node):
        self.calls.append(node)
        return 0


class _NonQueueableStrategy:
    queueable = False

    def __init__(self):
        self.calls = []

    def execute(self, node):
        self.calls.append(node)
        return 0


class TestRos2BridgeMotionCoordinator(unittest.TestCase):

    def setUp(self):
        self.node = _FakeNode()
        self.queue = MotionQueue(max_size=4)
        self.coordinator = MotionCoordinator(node=self.node, motion_queue=self.queue)

    def test_execute_runs_immediately_when_idle(self):
        strategy = _QueueableStrategy()

        result = self.coordinator.execute(strategy)

        self.assertEqual(result, 0)
        self.assertEqual(strategy.calls, [self.node])
        self.assertEqual(self.queue.get_status()["current_task_id"], 1)

    def test_execute_queues_queueable_strategy_when_busy(self):
        self.coordinator.is_executing = True
        strategy = _QueueableStrategy()

        result = self.coordinator.execute(strategy)

        self.assertEqual(result, 1)
        self.assertEqual(strategy.calls, [])
        self.assertEqual(self.queue.get_status()["queue_size"], 1)

    def test_execute_rejects_non_queueable_strategy_when_busy(self):
        self.coordinator.is_executing = True
        strategy = _NonQueueableStrategy()

        result = self.coordinator.execute(strategy, queue_if_busy=False)

        self.assertEqual(result, -1)
        self.assertEqual(strategy.calls, [])
        self.assertEqual(self.queue.get_status()["queue_size"], 0)

    def test_stop_motion_returns_no_active_motion_when_idle(self):
        result = self.coordinator.stop_motion()

        self.assertEqual(result["state"], "NO_ACTIVE_MOTION")
        self.assertTrue(result["success"])
