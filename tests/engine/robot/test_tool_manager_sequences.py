import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.engine.robot.interfaces.tool_definition import ToolDefinition
from src.engine.robot.tool_changer import SlotConfig, ToolChangeStep, ToolChanger
from src.engine.robot.tool_manager import ToolManager


class ToolManagerSequenceTests(unittest.TestCase):
    def _manager(self, pickup, dropoff=None):
        motion = MagicMock()
        motion.move_linear.return_value = True
        activator = MagicMock()
        activator.set_active_tool.return_value = True
        slot = SlotConfig(
            id=2,
            tool_id=7,
            pickup_sequence=pickup,
            dropoff_sequence=dropoff or [],
        )
        changer = ToolChanger([slot], [ToolDefinition(7, "Vacuum")])
        config = SimpleNamespace(robot_tool=1, robot_user=0)
        manager = ToolManager(
            motion_service=motion,
            tool_changer=changer,
            robot_config=config,
            movement_groups=SimpleNamespace(movement_groups={}),
            tool_activator=activator,
        )
        return manager, motion, activator, config

    def test_pickup_executes_taught_motion_and_activation_boundary(self):
        manager, motion, activator, config = self._manager([
            ToolChangeStep(kind="motion", pose=[1, 2, 3, 4, 5, 6]),
            ToolChangeStep(kind="attach", label="Attach"),
        ])
        ok, error = manager.pickup_gripper(7)
        self.assertTrue(ok, error)
        motion.move_linear.assert_called_once()
        activator.set_active_tool.assert_called_once_with(7)
        self.assertEqual(config.robot_tool, 7)
        self.assertEqual(manager.current_gripper, 7)

    def test_operator_confirmation_fails_closed_without_callback(self):
        manager, _, _, _ = self._manager([
            ToolChangeStep(kind="operator_confirm", label="Lock the tool"),
        ])
        ok, error = manager.pickup_gripper(7)
        self.assertFalse(ok)
        self.assertIn("Operator confirmation required", error)


if __name__ == "__main__":
    unittest.main()
