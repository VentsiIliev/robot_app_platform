import sys
import unittest
from pathlib import Path


_ROS2_SCRIPTS_DIR = Path(
    "/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/fairino5_v6_moveit2_config/scripts"
)
if str(_ROS2_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_ROS2_SCRIPTS_DIR))

from motion.execution.trajectory_optimizer import (  # type: ignore
    RuckigTrajectoryOptimizer,
    TotgTrajectoryOptimizer,
    build_trajectory_optimizer,
)


class _FakeNode:
    pass


class _FakeLogger:
    def __init__(self):
        self.errors = []

    def error(self, message):
        self.errors.append(message)


class TestRos2BridgeTrajectoryOptimizer(unittest.TestCase):
    def test_build_returns_totg_optimizer(self):
        optimizer = build_trajectory_optimizer("TOTG", node=_FakeNode())

        self.assertIsInstance(optimizer, TotgTrajectoryOptimizer)

    def test_build_returns_ruckig_optimizer(self):
        optimizer = build_trajectory_optimizer("RUCKIG", node=_FakeNode())

        self.assertIsInstance(optimizer, RuckigTrajectoryOptimizer)

    def test_build_rejects_unknown_optimizer(self):
        with self.assertRaises(ValueError):
            build_trajectory_optimizer("UNKNOWN", node=_FakeNode())

    def test_totg_optimizer_delegates_to_totg_function(self):
        calls = []
        optimizer = TotgTrajectoryOptimizer(
            apply_fn=lambda node, trajectory, vel, acc, callback: calls.append(
                (node, trajectory, vel, acc, callback)
            )
        )
        callback = object()

        optimizer.optimize(_FakeNode(), "traj", 0.6, 0.4, callback)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1:4], ("traj", 0.6, 0.4))
        self.assertIs(calls[0][4], callback)

    def test_ruckig_optimizer_delegates_to_ruckig_function(self):
        calls = []
        optimizer = RuckigTrajectoryOptimizer(
            apply_fn=lambda node, trajectory, vel, acc, callback: calls.append(
                (node, trajectory, vel, acc, callback)
            )
        )
        callback = object()

        optimizer.optimize(_FakeNode(), "traj", 0.5, 0.3, callback)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1:4], ("traj", 0.5, 0.3))
        self.assertIs(calls[0][4], callback)

    def test_build_logs_and_falls_back_when_requested(self):
        logger = _FakeLogger()
        node = type("_Node", (), {"get_logger": lambda self: logger})()

        optimizer = build_trajectory_optimizer(
            "UNKNOWN",
            node=node,
            fallback_name="TOTG",
        )

        self.assertIsInstance(optimizer, TotgTrajectoryOptimizer)
        self.assertEqual(len(logger.errors), 1)
