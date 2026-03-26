import sys
import unittest
from pathlib import Path


_ROS2_SCRIPTS_DIR = Path(
    "/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/fairino5_v6_moveit2_config/scripts"
)
if str(_ROS2_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_ROS2_SCRIPTS_DIR))

try:
    from motion.planning.planner_context import PlannerContext  # type: ignore
    from motion.execution.motion_coordinator import MotionCoordinator  # type: ignore
    from motion.execution.motion_queue import MotionQueue  # type: ignore
    from status.robot_state_store import RobotStateStore  # type: ignore
except ImportError as _e:
    raise unittest.SkipTest(f"ROS2 bridge packages not available: {_e}")


class _FakeLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class _FakeClock:
    pass


class _FakeFuture:
    def __init__(self, payload=None):
        self.payload = payload


class _FakeClient:
    def __init__(self):
        self.requests = []
        self.timeout_values = []

    def call_async(self, request):
        self.requests.append(request)
        return _FakeFuture(request)

    def wait_for_service(self, timeout_sec=1.0):
        self.timeout_values.append(timeout_sec)
        return True


class _FakeSafetyManager:
    def __init__(self):
        self.force_update_calls = 0
        self.check_calls = []

    def force_update(self):
        self.force_update_calls += 1

    def check_position_safety(self, x, y, z):
        self.check_calls.append((x, y, z))
        return True, "ok"


class _FakePlannerSupport:
    def __init__(self):
        self._fk = object()
        self._ik = object()
        self._validity = object()

    def get_fk_client(self):
        return self._fk

    def get_ik_client(self):
        return self._ik

    def get_state_validity_client(self):
        return self._validity


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
        self.queue = MotionQueue(max_size=4)
        self.safety_manager = _FakeSafetyManager()
        self.cart_path_client = _FakeClient()
        self.planner_support = _FakePlannerSupport()
        self.context = PlannerContext(
            node=self.node,
            state_store=self.state_store,
            motion_coordinator=self.motion,
            motion_queue=self.queue,
            safety_manager=self.safety_manager,
            cart_path_client=self.cart_path_client,
            ipp_client=object(),
            trajectory_executor=object(),
            planner_support=self.planner_support,
            trajectory_optimizer=object(),
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

    def test_tracks_last_requested_delta_and_waypoints(self):
        self.context.set_last_requested_delta_mm(12.5)
        self.context.set_last_full_waypoints(["a", "b"])

        self.assertEqual(self.context.get_last_requested_delta_mm(), 12.5)
        self.assertEqual(self.context.get_last_full_waypoints(), ["a", "b"])

    def test_stages_and_consumes_pending_path(self):
        self.context.stage_pending_path("traj", 0.6, 0.4)

        self.assertEqual(self.context.consume_pending_path(), ("traj", 0.6, 0.4))
        self.assertEqual(self.context.consume_pending_path(), (None, None, None))

    def test_exposes_queue_and_safety_helpers(self):
        self.context.force_safety_update()
        self.assertEqual(self.safety_manager.force_update_calls, 1)

        self.assertEqual(self.context.check_position_safety(1.0, 2.0, 3.0), (True, "ok"))
        self.assertEqual(self.safety_manager.check_calls, [(1.0, 2.0, 3.0)])

        self.assertTrue(self.context.wait_for_cartesian_path_service(timeout_sec=0.25))
        future = self.context.request_cartesian_path({"path": 1})
        self.assertEqual(self.cart_path_client.timeout_values, [0.25])
        self.assertEqual(self.cart_path_client.requests, [{"path": 1}])
        self.assertEqual(future.payload, {"path": 1})

        self.context.submit_motion_task(lambda: 0)
        self.assertEqual(self.queue.get_status()["queue_size"], 1)
        task = self.queue.get_next_task()
        self.assertIsNotNone(task)
        self.context.mark_current_motion_complete(0)
        self.assertEqual(self.queue.wait_for_task(1, timeout_s=0.01), 0)

    def test_delegates_cached_clients_to_planner_support(self):
        fk_1 = self.context.get_fk_client()
        fk_2 = self.context.get_fk_client()
        validity_1 = self.context.get_state_validity_client()
        validity_2 = self.context.get_state_validity_client()

        self.assertIs(fk_1, fk_2)
        self.assertIs(validity_1, validity_2)
