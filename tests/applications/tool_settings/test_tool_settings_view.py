import sys
import unittest

from src.applications.tool_settings.view.tool_settings_view import ToolSettingsView
from src.engine.robot.interfaces.tool_definition import ToolDefinition
from src.engine.robot.tool_changer import SlotConfig


class TestToolSettingsViewSetTools(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)
        cls._view = ToolSettingsView()

    def test_set_tools_populates_rows(self):
        self._view.set_tools([ToolDefinition(1, "A"), ToolDefinition(4, "B")])
        self.assertEqual(self._view._tools_table.rowCount(), 2)

    def test_set_tools_replaces_previous_rows(self):
        self._view.set_tools([ToolDefinition(1, "A"), ToolDefinition(2, "B")])
        self._view.set_tools([ToolDefinition(3, "C")])
        self.assertEqual(self._view._tools_table.rowCount(), 1)

    def test_set_tools_empty_clears_table(self):
        self._view.set_tools([ToolDefinition(1, "A")])
        self._view.set_tools([])
        self.assertEqual(self._view._tools_table.rowCount(), 0)

    def test_set_tools_displays_id_in_column_0(self):
        self._view.set_tools([ToolDefinition(42, "Test")])
        self.assertEqual(self._view._tools_table.item(0, 0).text(), "42")

    def test_set_tools_displays_name_in_column_1(self):
        self._view.set_tools([ToolDefinition(1, "MyTool")])
        self.assertEqual(self._view._tools_table.item(0, 1).text(), "MyTool")


class TestToolSettingsViewSetSlots(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)
        cls._view = ToolSettingsView()

    def test_set_slots_populates_rows(self):
        self._view.set_slots(
            [SlotConfig(id=10, tool_id=None), SlotConfig(id=11, tool_id=None)], []
        )
        self.assertEqual(self._view._slots_table.rowCount(), 2)

    def test_set_slots_replaces_previous_rows(self):
        self._view.set_slots([SlotConfig(id=10, tool_id=None)], [])
        self._view.set_slots([], [])
        self.assertEqual(self._view._slots_table.rowCount(), 0)

    def test_set_slots_displays_slot_id_in_column_0(self):
        self._view.set_slots([SlotConfig(id=99, tool_id=None)], [])
        self.assertEqual(self._view._slots_table.item(0, 0).text(), "99")


class TestToolSettingsViewSetStatus(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)
        cls._view = ToolSettingsView()

    def test_set_status_updates_label(self):
        self._view.set_status("3 tool(s), 2 slot(s)")
        self.assertEqual(self._view._status.text(), "3 tool(s), 2 slot(s)")

    def test_set_status_empty_string(self):
        self._view.set_status("")
        self.assertEqual(self._view._status.text(), "")


class TestToolSettingsViewSelectedTool(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self._view = ToolSettingsView()

    def test_no_selection_returns_none_none(self):
        self._view.set_tools([ToolDefinition(1, "G")])
        tid, name = self._view.selected_tool()
        self.assertIsNone(tid)
        self.assertIsNone(name)

    def test_selected_row_returns_id_and_name(self):
        self._view.set_tools([ToolDefinition(7, "PickTool")])
        self._view._tools_table.selectRow(0)
        tid, name = self._view.selected_tool()
        self.assertEqual(tid, 7)
        self.assertEqual(name, "PickTool")


class TestToolSettingsViewButtonStates(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self._view = ToolSettingsView()

    def test_edit_and_remove_tool_buttons_disabled_initially(self):
        self.assertFalse(self._view._btn_edit_tool.isEnabled())
        self.assertFalse(self._view._btn_remove_tool.isEnabled())

    def test_edit_and_remove_tool_buttons_enabled_after_selection(self):
        self._view.set_tools([ToolDefinition(1, "G")])
        self._view._tools_table.selectRow(0)
        self.assertTrue(self._view._btn_edit_tool.isEnabled())
        self.assertTrue(self._view._btn_remove_tool.isEnabled())

    def test_edit_and_remove_slot_buttons_disabled_initially(self):
        self.assertFalse(self._view._btn_edit_slot.isEnabled())
        self.assertFalse(self._view._btn_remove_slot.isEnabled())

    def test_edit_and_remove_slot_buttons_enabled_after_selection(self):
        self._view.set_slots([SlotConfig(id=10, tool_id=None)], [])
        self._view._slots_table.selectRow(0)
        self.assertTrue(self._view._btn_edit_slot.isEnabled())
        self.assertTrue(self._view._btn_remove_slot.isEnabled())


class TestToolSettingsViewSignals(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def setUp(self):
        self._view = ToolSettingsView()

    def test_add_tool_button_emits_add_tool_requested(self):
        received = []
        self._view.add_tool_requested.connect(lambda: received.append(True))
        self._view._btn_add_tool.click()
        self.assertTrue(received)

    def test_add_slot_button_emits_add_slot_requested(self):
        received = []
        self._view.add_slot_requested.connect(lambda: received.append(True))
        self._view._btn_add_slot.click()
        self.assertTrue(received)

    def test_remove_tool_button_emits_with_selected_id(self):
        received = []
        self._view.remove_tool_requested.connect(lambda tid: received.append(tid))
        self._view.set_tools([ToolDefinition(3, "T")])
        self._view._tools_table.selectRow(0)
        self._view._btn_remove_tool.click()
        self.assertEqual(received, [3])

    def test_edit_tool_button_emits_with_id_and_name(self):
        received = []
        self._view.edit_tool_requested.connect(lambda tid, name: received.append((tid, name)))
        self._view.set_tools([ToolDefinition(5, "MyTool")])
        self._view._tools_table.selectRow(0)
        self._view._btn_edit_tool.click()
        self.assertEqual(received, [(5, "MyTool")])

    def test_remove_slot_button_emits_with_selected_slot_id(self):
        received = []
        self._view.remove_slot_requested.connect(lambda sid: received.append(sid))
        self._view.set_slots([SlotConfig(id=10, tool_id=None)], [])
        self._view._slots_table.selectRow(0)
        self._view._btn_remove_slot.click()
        self.assertEqual(received, [10])

    def test_edit_slot_button_emits_with_slot_and_tool_id(self):
        received = []
        self._view.edit_slot_requested.connect(lambda sid, tid: received.append((sid, tid)))
        tools = [ToolDefinition(1, "G")]
        self._view.set_slots([SlotConfig(id=10, tool_id=1)], tools)
        self._view._slots_table.selectRow(0)
        self._view._btn_edit_slot.click()
        self.assertEqual(received, [(10, 1)])

    def test_save_button_emits_save_slots_requested_with_assignments(self):
        received = []
        self._view.save_slots_requested.connect(lambda lst: received.append(lst))
        tools = [ToolDefinition(1, "G")]
        self._view.set_slots([SlotConfig(id=10, tool_id=1)], tools)
        self._view._btn_save_slots.click()
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], [(10, 1)])

    def test_clean_up_does_not_raise(self):
        self._view.clean_up()


if __name__ == "__main__":
    unittest.main()