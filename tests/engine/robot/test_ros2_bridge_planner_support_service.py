import sys
import types
import unittest
from pathlib import Path


_ROS2_SCRIPTS_DIR = Path(
    "/home/ilv/ros2_ws/eRob_moveit/src/eRob_ROS2_MoveIt/fairino5_v6_moveit2_config/scripts"
)
if str(_ROS2_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_ROS2_SCRIPTS_DIR))


if "moveit_msgs" not in sys.modules:
    moveit_msgs = types.ModuleType("moveit_msgs")
    moveit_msgs.srv = types.ModuleType("moveit_msgs.srv")

    class _GetPositionFK:
        pass

    class _GetStateValidity:
        pass

    moveit_msgs.srv.GetPositionFK = _GetPositionFK
    moveit_msgs.srv.GetStateValidity = _GetStateValidity
    sys.modules["moveit_msgs"] = moveit_msgs
    sys.modules["moveit_msgs.srv"] = moveit_msgs.srv

from motion.planning.planner_support_service import PlannerSupportService  # type: ignore


class _FakeNode:
    def __init__(self):
        self.calls = []

    def create_client(self, service_type, service_name):
        client = object()
        self.calls.append((service_type, service_name, client))
        return client


class TestRos2BridgePlannerSupportService(unittest.TestCase):
    def test_caches_fk_and_state_validity_clients(self):
        node = _FakeNode()
        service = PlannerSupportService(node=node)

        fk_client_1 = service.get_fk_client()
        fk_client_2 = service.get_fk_client()
        validity_client_1 = service.get_state_validity_client()
        validity_client_2 = service.get_state_validity_client()

        self.assertIs(fk_client_1, fk_client_2)
        self.assertIs(validity_client_1, validity_client_2)
        self.assertEqual(len(node.calls), 2)
        self.assertEqual(node.calls[0][1], "/compute_fk")
        self.assertEqual(node.calls[1][1], "/check_state_validity")
