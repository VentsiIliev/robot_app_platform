import unittest

from src.engine.robot.tool_changer import SlotConfig, ToolChanger


class TestToolChanger(unittest.TestCase):

    def _make(self):
        return ToolChanger(slots=[
            SlotConfig(id=10, tool_id=0),
            SlotConfig(id=11, tool_id=1),
            SlotConfig(id=12, tool_id=2),
        ])

    def test_get_slot_id_by_tool_id_found(self):
        tc = self._make()
        self.assertEqual(tc.get_slot_id_by_tool_id(1), 11)

    def test_get_slot_id_by_tool_id_not_found(self):
        tc = self._make()
        self.assertIsNone(tc.get_slot_id_by_tool_id(99))

    def test_slot_not_occupied_initially(self):
        tc = self._make()
        self.assertFalse(tc.is_slot_occupied(10))

    def test_set_slot_not_available_marks_occupied(self):
        tc = self._make()
        tc.set_slot_not_available(10)
        self.assertTrue(tc.is_slot_occupied(10))

    def test_set_slot_available_clears_occupied(self):
        tc = self._make()
        tc.set_slot_not_available(10)
        tc.set_slot_available(10)
        self.assertFalse(tc.is_slot_occupied(10))

    def test_get_occupied_slots_empty_initially(self):
        tc = self._make()
        self.assertEqual(tc.get_occupied_slots(), [])

    def test_get_occupied_slots_after_marking(self):
        tc = self._make()
        tc.set_slot_not_available(10)
        tc.set_slot_not_available(12)
        self.assertCountEqual(tc.get_occupied_slots(), [10, 12])

    def test_get_empty_slots_all_initially(self):
        tc = self._make()
        self.assertCountEqual(tc.get_empty_slots(), [10, 11, 12])

    def test_get_empty_slots_excludes_occupied(self):
        tc = self._make()
        tc.set_slot_not_available(11)
        self.assertCountEqual(tc.get_empty_slots(), [10, 12])

    def test_multiple_slots_independent(self):
        tc = self._make()
        tc.set_slot_not_available(10)
        self.assertFalse(tc.is_slot_occupied(11))
        self.assertFalse(tc.is_slot_occupied(12))