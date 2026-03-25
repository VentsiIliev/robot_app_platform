import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
import types


_ROS2_SCRIPTS_DIR = Path(
    "/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/fairino5_v6_moveit2_config/scripts"
)
if str(_ROS2_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_ROS2_SCRIPTS_DIR))

if "control_msgs.action" not in sys.modules:
    control_msgs = types.ModuleType("control_msgs")
    control_msgs_action = types.ModuleType("control_msgs.action")
    control_msgs_msg = types.ModuleType("control_msgs.msg")

    class _FakeGoal:
        def __init__(self):
            self.trajectory = None
            self.path_tolerance = []
            self.goal_tolerance = []
            self.goal_time_tolerance = SimpleNamespace(sec=0, nanosec=0)

    class _FakeFollowJointTrajectory:
        Goal = _FakeGoal

    class _FakeJointTolerance:
        def __init__(self):
            self.name = ""
            self.position = 0.0
            self.velocity = 0.0
            self.acceleration = 0.0

    control_msgs_action.FollowJointTrajectory = _FakeFollowJointTrajectory
    control_msgs_msg.JointTolerance = _FakeJointTolerance

    sys.modules["control_msgs"] = control_msgs
    sys.modules["control_msgs.action"] = control_msgs_action
    sys.modules["control_msgs.msg"] = control_msgs_msg

try:
    from motion.execution.motion_coordinator import MotionCoordinator  # type: ignore
    from motion.execution.motion_queue import MotionQueue  # type: ignore
    from motion.execution.trajectory_executor import TrajectoryExecutor  # type: ignore
except ImportError as _e:
    raise unittest.SkipTest(f"ROS2 bridge packages not available: {_e}")


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


class _FakeFuture:
    def __init__(self, result):
        self._result = result
        self.callbacks = []

    def result(self):
        return self._result

    def add_done_callback(self, cb):
        self.callbacks.append(cb)


class _FakeControllerClient:
    def __init__(self, send_future):
        self._send_future = send_future

    def wait_for_server(self, timeout_sec=1.0):
        return True

    def send_goal_async(self, goal):
        return self._send_future


class _QueueTask:
    def __init__(self):
        self.called = 0

    def __call__(self):
        self.called += 1
        return 0


class TestRos2BridgeTrajectoryExecutor(unittest.TestCase):

    def setUp(self):
        self.node = _FakeNode()
        self.queue = MotionQueue(max_size=4)
        self.motion = MotionCoordinator(node=self.node, motion_queue=self.queue)

    def test_process_next_queued_task_executes_task(self):
        task = _QueueTask()
        self.queue.submit(task)
        executor = TrajectoryExecutor(
            node=self.node,
            coordinator=self.motion,
            motion_queue=self.queue,
            controller_client=_FakeControllerClient(_FakeFuture(None)),
        )

        executor.process_next_queued_task()

        self.assertEqual(task.called, 1)
        self.assertEqual(self.queue.get_status()["queue_size"], 0)

    def test_controller_goal_result_marks_completion_and_drains_queue(self):
        result_future = _FakeFuture(SimpleNamespace(result=SimpleNamespace(error_code=0)))
        goal_handle = SimpleNamespace(accepted=True, get_result_async=lambda: result_future)
        send_future = _FakeFuture(goal_handle)
        executor = TrajectoryExecutor(
            node=self.node,
            coordinator=self.motion,
            motion_queue=self.queue,
            controller_client=_FakeControllerClient(send_future),
        )

        self.motion.execution_lock.acquire()
        self.motion.active_controller_goal = goal_handle
        self.motion.is_executing = True
        self.queue.start_immediate_task(self.queue.allocate_task_id())
        next_task = _QueueTask()
        self.queue.submit(next_task)

        executor._on_controller_goal_result(result_future)

        self.assertEqual(self.motion.last_move_result, 0)
        self.assertFalse(self.motion.is_executing)
        self.assertEqual(next_task.called, 1)
