import unittest

from src.engine.robot.configuration.tool_changer_settings import (
    ToolChangerSettings,
    ToolChangerSettingsSerializer,
)
from src.engine.robot.interfaces.tool_definition import ToolDefinition
from src.engine.robot.tool_changer import SlotConfig, ToolChangeStep


class ToolChangerSettingsSerializerTests(unittest.TestCase):
    def test_round_trip_preserves_geometry_and_sequences(self):
        settings = ToolChangerSettings(
            reference_tool_id=1,
            tools=[ToolDefinition(2, "Vacuum", 1, [1, 2, 30, 0, 0, 0], "vacuum")],
            slots=[SlotConfig(
                id=4,
                tool_id=2,
                label="Left",
                pickup_sequence=[ToolChangeStep(kind="motion", pose=[1, 2, 3, 4, 5, 6])],
                dropoff_sequence=[ToolChangeStep(kind="detach", label="Release")],
            )],
        )
        serializer = ToolChangerSettingsSerializer()
        restored = serializer.from_dict(serializer.to_dict(settings))
        self.assertEqual(restored.reference_tool_id, 1)
        self.assertEqual(restored.tools[0].relative_transform, [1, 2, 30, 0, 0, 0])
        self.assertEqual(restored.slots[0].label, "Left")
        self.assertEqual(restored.slots[0].pickup_sequence[0].pose, [1, 2, 3, 4, 5, 6])
        self.assertEqual(restored.slots[0].dropoff_sequence[0].kind, "detach")

    def test_old_shape_remains_loadable(self):
        restored = ToolChangerSettingsSerializer().from_dict({
            "tools": [{"id": 1, "name": "Old"}],
            "slots": [{"slot_id": 2, "tool_id": 1}],
        })
        self.assertEqual(restored.tools[0].relative_transform, [0, 0, 0, 0, 0, 0])
        self.assertEqual(restored.slots[0].pickup_sequence, [])


if __name__ == "__main__":
    unittest.main()
