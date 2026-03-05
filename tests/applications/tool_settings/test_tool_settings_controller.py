import sys
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QDialog

from src.applications.tool_settings.controller.tool_settings_controller import ToolSettingsController
from src.applications.tool_settings.model.tool_settings_model import ToolSettingsModel
from src.applications.tool_settings.view.tool_settings_view import ToolSettingsView
from src.engine.robot.interfaces.tool_definition import ToolDefinition
from src.engine.robot.tool_changer import SlotConfig

_CTRL_MOD = "src.applications.tool_settings.controller.tool_settings_controller"


def _make_model(tools=None, slots=None):
    model = MagicMock(spec=ToolSettingsModel)
    model.get_tools.return_value = tools if tools is not None else []
    model.get_slots.return_value = slots if slots is not None else []
    return model


def _make_view():
    return MagicMock(spec=ToolSettingsView)


def _make_ctrl(tools=None, slots=None):
    model = _make_model(tools, slots)
    view  = _make_view()
    ctrl  = ToolSettingsController(model, view)
    return ctrl, model, view


class TestToolSettingsControllerLoad(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_load_connects_all_view_signals(self):
        ctrl, model, view = _make_ctrl()
        ctrl.load()
        view.add_tool_requested.connect.assert_called()
        view.edit_tool_requested.connect.assert_called()
        view.remove_tool_requested.connect.assert_called()
        view.add_slot_requested.connect.assert_called()
        view.remove_slot_requested.connect.assert_called()
        view.save_slots_requested.connect.assert_called()
        view.edit_slot_requested.connect.assert_called()

    def test_load_triggers_refresh(self):
        ctrl, model, view = _make_ctrl()
        ctrl.load()
        view.set_tools.assert_called_once()
        view.set_slots.assert_called_once()
        view.set_status.assert_called_once()


class TestToolSettingsControllerRefresh(unittest.TestCase):

    def test_refresh_passes_tools_to_view(self):
        tools = [ToolDefinition(1, "G")]
        ctrl, model, view = _make_ctrl(tools=tools)
        ctrl.load()
        view.set_tools.assert_called_once_with(tools)

    def test_refresh_passes_slots_and_tools_to_view(self):
        tools = [ToolDefinition(1, "G")]
        slots = [SlotConfig(id=10, tool_id=1)]
        ctrl, model, view = _make_ctrl(tools=tools, slots=slots)
        ctrl.load()
        view.set_slots.assert_called_once_with(slots, tools)

    def test_refresh_status_contains_tool_and_slot_counts(self):
        tools = [ToolDefinition(1, "G"), ToolDefinition(2, "D")]
        slots = [SlotConfig(id=10, tool_id=1)]
        ctrl, model, view = _make_ctrl(tools=tools, slots=slots)
        ctrl.load()
        msg = view.set_status.call_args[0][0]
        self.assertIn("2", msg)
        self.assertIn("1", msg)


class TestToolSettingsControllerOnAdd(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    @patch(f"{_CTRL_MOD}._ToolDialog")
    def test_rejected_dialog_does_not_call_model(self, MockDialog):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Rejected
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl()
        ctrl._on_add()
        model.add_tool.assert_not_called()

    @patch(f"{_CTRL_MOD}._ToolDialog")
    def test_accepted_dialog_calls_add_tool(self, MockDialog):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_values.return_value = (5, "NewTool")
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl()
        model.add_tool.return_value = (True, "Tool added")
        ctrl._on_add()
        model.add_tool.assert_called_once_with(5, "NewTool")

    @patch(f"{_CTRL_MOD}._ToolDialog")
    def test_success_triggers_refresh(self, MockDialog):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_values.return_value = (5, "NewTool")
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl()
        model.add_tool.return_value = (True, "Tool added")
        ctrl._on_add()
        self.assertGreater(view.set_tools.call_count, 0)

    @patch(f"{_CTRL_MOD}.show_warning")
    @patch(f"{_CTRL_MOD}._ToolDialog")
    def test_failure_shows_warning_no_refresh(self, MockDialog, mock_warn):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_values.return_value = (1, "Dup")
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl()
        model.add_tool.return_value = (False, "already exists")
        ctrl._on_add()
        mock_warn.assert_called_once()
        view.set_tools.assert_not_called()


class TestToolSettingsControllerOnEdit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    @patch(f"{_CTRL_MOD}._ToolDialog")
    def test_rejected_dialog_does_not_call_model(self, MockDialog):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Rejected
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl()
        ctrl._on_edit(1, "Old")
        model.update_tool.assert_not_called()

    @patch(f"{_CTRL_MOD}._ToolDialog")
    def test_accepted_calls_update_tool_with_new_name(self, MockDialog):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_values.return_value = (1, "Updated")
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl()
        model.update_tool.return_value = (True, "Tool updated")
        ctrl._on_edit(1, "Old")
        model.update_tool.assert_called_once_with(1, "Updated")

    @patch(f"{_CTRL_MOD}.show_warning")
    @patch(f"{_CTRL_MOD}._ToolDialog")
    def test_failure_shows_warning(self, MockDialog, mock_warn):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_values.return_value = (1, "X")
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl()
        model.update_tool.return_value = (False, "Not found")
        ctrl._on_edit(1, "X")
        mock_warn.assert_called_once()


class TestToolSettingsControllerOnRemove(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    @patch(f"{_CTRL_MOD}.ask_yes_no")
    def test_cancelled_does_not_call_model(self, mock_ask):
        mock_ask.return_value = False
        ctrl, model, view = _make_ctrl()
        ctrl._on_remove(1)
        model.remove_tool.assert_not_called()

    @patch(f"{_CTRL_MOD}.ask_yes_no")
    def test_confirmed_calls_remove_tool(self, mock_ask):
        mock_ask.return_value = True
        ctrl, model, view = _make_ctrl()
        model.remove_tool.return_value = (True, "Removed")
        ctrl._on_remove(1)
        model.remove_tool.assert_called_once_with(1)

    @patch(f"{_CTRL_MOD}.show_warning")
    @patch(f"{_CTRL_MOD}.ask_yes_no")
    def test_failure_shows_warning(self, mock_ask, mock_warn):
        mock_ask.return_value = True
        ctrl, model, view = _make_ctrl()
        model.remove_tool.return_value = (False, "In slot")
        ctrl._on_remove(1)
        mock_warn.assert_called_once()


class TestToolSettingsControllerOnAddSlot(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    @patch(f"{_CTRL_MOD}.show_warning")
    def test_no_tools_shows_warning_and_aborts(self, mock_warn):
        ctrl, model, view = _make_ctrl(tools=[])
        ctrl._on_add_slot()
        model.add_slot.assert_not_called()
        mock_warn.assert_called_once()

    @patch(f"{_CTRL_MOD}._SlotDialog")
    def test_rejected_dialog_does_not_call_model(self, MockDialog):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Rejected
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl(tools=[ToolDefinition(1, "G")])
        ctrl._on_add_slot()
        model.add_slot.assert_not_called()

    @patch(f"{_CTRL_MOD}._SlotDialog")
    def test_accepted_calls_add_slot(self, MockDialog):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_values.return_value = (20, 1)
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl(tools=[ToolDefinition(1, "G")])
        model.add_slot.return_value = (True, "Slot added")
        ctrl._on_add_slot()
        model.add_slot.assert_called_once_with(20, 1)

    @patch(f"{_CTRL_MOD}.show_warning")
    @patch(f"{_CTRL_MOD}._SlotDialog")
    def test_failure_shows_warning(self, MockDialog, mock_warn):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_values.return_value = (10, 1)
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl(tools=[ToolDefinition(1, "G")])
        model.add_slot.return_value = (False, "already exists")
        ctrl._on_add_slot()
        mock_warn.assert_called_once()


class TestToolSettingsControllerOnRemoveSlot(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    @patch(f"{_CTRL_MOD}.ask_yes_no")
    def test_cancelled_does_not_call_model(self, mock_ask):
        mock_ask.return_value = False
        ctrl, model, view = _make_ctrl()
        ctrl._on_remove_slot(10)
        model.remove_slot.assert_not_called()

    @patch(f"{_CTRL_MOD}.ask_yes_no")
    def test_confirmed_calls_remove_slot(self, mock_ask):
        mock_ask.return_value = True
        ctrl, model, view = _make_ctrl()
        model.remove_slot.return_value = (True, "Removed")
        ctrl._on_remove_slot(10)
        model.remove_slot.assert_called_once_with(10)

    @patch(f"{_CTRL_MOD}.show_warning")
    @patch(f"{_CTRL_MOD}.ask_yes_no")
    def test_failure_shows_warning(self, mock_ask, mock_warn):
        mock_ask.return_value = True
        ctrl, model, view = _make_ctrl()
        model.remove_slot.return_value = (False, "Not found")
        ctrl._on_remove_slot(10)
        mock_warn.assert_called_once()


class TestToolSettingsControllerOnSaveSlots(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_calls_update_slot_for_each_assignment(self):
        ctrl, model, view = _make_ctrl()
        model.update_slot.return_value = (True, "ok")
        ctrl._on_save_slots([(10, 1), (11, 4)])
        self.assertEqual(model.update_slot.call_count, 2)
        model.update_slot.assert_any_call(10, 1)
        model.update_slot.assert_any_call(11, 4)

    def test_all_success_sets_saved_status(self):
        ctrl, model, view = _make_ctrl()
        model.update_slot.return_value = (True, "ok")
        ctrl._on_save_slots([(10, 1)])
        view.set_status.assert_any_call("Slots saved")

    def test_empty_list_sets_saved_status(self):
        ctrl, model, view = _make_ctrl()
        ctrl._on_save_slots([])
        view.set_status.assert_any_call("Slots saved")

    @patch(f"{_CTRL_MOD}.show_warning")
    def test_partial_failure_shows_warning(self, mock_warn):
        ctrl, model, view = _make_ctrl()
        model.update_slot.side_effect = [(False, "Slot 10 not found"), (True, "ok")]
        ctrl._on_save_slots([(10, 1), (11, 4)])
        mock_warn.assert_called_once()

    @patch(f"{_CTRL_MOD}.show_warning")
    def test_all_failure_shows_warning_no_refresh(self, mock_warn):
        ctrl, model, view = _make_ctrl()
        model.update_slot.return_value = (False, "err")
        ctrl._on_save_slots([(10, 1)])
        mock_warn.assert_called_once()
        view.set_tools.assert_not_called()


class TestToolSettingsControllerOnEditSlot(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    @patch(f"{_CTRL_MOD}.show_warning")
    def test_no_tools_shows_warning_and_aborts(self, mock_warn):
        ctrl, model, view = _make_ctrl(tools=[])
        ctrl._on_edit_slot(10, 1)
        model.update_slot.assert_not_called()
        mock_warn.assert_called_once()

    @patch(f"{_CTRL_MOD}._SlotDialog")
    def test_rejected_dialog_does_not_call_model(self, MockDialog):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Rejected
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl(tools=[ToolDefinition(1, "G")])
        ctrl._on_edit_slot(10, 1)
        model.update_slot.assert_not_called()

    @patch(f"{_CTRL_MOD}._SlotDialog")
    def test_accepted_calls_update_slot(self, MockDialog):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_values.return_value = (10, 4)
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl(tools=[ToolDefinition(1, "G"), ToolDefinition(4, "D")])
        model.update_slot.return_value = (True, "Slot updated")
        ctrl._on_edit_slot(10, 1)
        model.update_slot.assert_called_once_with(10, 4)

    @patch(f"{_CTRL_MOD}.show_warning")
    @patch(f"{_CTRL_MOD}._SlotDialog")
    def test_failure_shows_warning(self, MockDialog, mock_warn):
        mock_dlg = MagicMock()
        mock_dlg.exec.return_value = QDialog.DialogCode.Accepted
        mock_dlg.get_values.return_value = (10, 99)
        MockDialog.return_value = mock_dlg
        ctrl, model, view = _make_ctrl(tools=[ToolDefinition(1, "G")])
        model.update_slot.return_value = (False, "Tool ID 99 does not exist")
        ctrl._on_edit_slot(10, 1)
        mock_warn.assert_called_once()


if __name__ == "__main__":
    unittest.main()