import unittest
from src.applications.tool_settings.service.stub_tool_settings_service import StubToolSettingsService


class TestStubToolSettingsServiceTools(unittest.TestCase):

    def setUp(self):
        self._svc = StubToolSettingsService()

    def test_get_tools_returns_initial_tools(self):
        tools = self._svc.get_tools()
        self.assertEqual(len(tools), 2)
        ids = {t.id for t in tools}
        self.assertIn(1, ids)
        self.assertIn(4, ids)

    def test_add_tool_returns_true_and_message(self):
        ok, msg = self._svc.add_tool(99, "Test")
        self.assertTrue(ok)
        self.assertEqual(msg, "Tool added")

    def test_add_tool_appends_to_list(self):
        self._svc.add_tool(99, "Test")
        self.assertIn(99, {t.id for t in self._svc.get_tools()})

    def test_update_tool_existing_returns_true(self):
        ok, msg = self._svc.update_tool(1, "Updated")
        self.assertTrue(ok)
        self.assertEqual(msg, "Tool updated")

    def test_update_tool_updates_name(self):
        self._svc.update_tool(1, "Updated")
        self.assertIn("Updated", {t.name for t in self._svc.get_tools()})

    def test_update_tool_not_found_returns_false(self):
        ok, msg = self._svc.update_tool(999, "X")
        self.assertFalse(ok)

    def test_remove_tool_existing_returns_true(self):
        ok, msg = self._svc.remove_tool(1)
        self.assertTrue(ok)
        self.assertEqual(msg, "Removed")

    def test_remove_tool_removes_from_list(self):
        self._svc.remove_tool(1)
        self.assertNotIn(1, {t.id for t in self._svc.get_tools()})

    def test_remove_tool_not_found_returns_false(self):
        ok, msg = self._svc.remove_tool(999)
        self.assertFalse(ok)
        self.assertEqual(msg, "Not found")


class TestStubToolSettingsServiceSlots(unittest.TestCase):

    def setUp(self):
        self._svc = StubToolSettingsService()

    def test_get_slots_returns_initial_slots(self):
        slots = self._svc.get_slots()
        self.assertEqual(len(slots), 2)
        ids = {s.id for s in slots}
        self.assertIn(10, ids)
        self.assertIn(11, ids)

    def test_update_slot_existing_returns_true(self):
        ok, msg = self._svc.update_slot(10, 4)
        self.assertTrue(ok)
        self.assertEqual(msg, "Slot updated")

    def test_update_slot_updates_tool_id(self):
        self._svc.update_slot(10, 4)
        slot = next(s for s in self._svc.get_slots() if s.id == 10)
        self.assertEqual(slot.tool_id, 4)

    def test_update_slot_not_found_returns_false(self):
        ok, _ = self._svc.update_slot(999, 1)
        self.assertFalse(ok)

    def test_add_slot_returns_true(self):
        ok, msg = self._svc.add_slot(99, 1)
        self.assertTrue(ok)
        self.assertEqual(msg, "Slot added")

    def test_add_slot_appends_to_list(self):
        self._svc.add_slot(99, 1)
        self.assertIn(99, {s.id for s in self._svc.get_slots()})

    def test_remove_slot_existing_returns_true(self):
        ok, msg = self._svc.remove_slot(10)
        self.assertTrue(ok)
        self.assertEqual(msg, "Removed")

    def test_remove_slot_removes_from_list(self):
        self._svc.remove_slot(10)
        self.assertNotIn(10, {s.id for s in self._svc.get_slots()})

    def test_remove_slot_not_found_returns_false(self):
        ok, msg = self._svc.remove_slot(999)
        self.assertFalse(ok)
        self.assertEqual(msg, "Not found")


if __name__ == "__main__":
    unittest.main()