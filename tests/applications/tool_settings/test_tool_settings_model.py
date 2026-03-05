import unittest
from unittest.mock import MagicMock

from src.applications.tool_settings.model.tool_settings_model import ToolSettingsModel
from src.applications.tool_settings.service.i_tool_settings_service import IToolSettingsService
from src.engine.robot.interfaces.tool_definition import ToolDefinition
from src.engine.robot.tool_changer import SlotConfig


def _make_service():
    svc = MagicMock(spec=IToolSettingsService)
    svc.get_tools.return_value   = [ToolDefinition(1, "Gripper")]
    svc.get_slots.return_value   = [SlotConfig(id=10, tool_id=1)]
    svc.add_tool.return_value    = (True, "Tool added")
    svc.update_tool.return_value = (True, "Tool updated")
    svc.remove_tool.return_value = (True, "Removed")
    svc.update_slot.return_value = (True, "Slot updated")
    svc.add_slot.return_value    = (True, "Slot added")
    svc.remove_slot.return_value = (True, "Removed")
    return svc


class TestToolSettingsModelLoad(unittest.TestCase):

    def test_load_returns_tools_list(self):
        svc = _make_service()
        result = ToolSettingsModel(svc).load()
        self.assertEqual(result, svc.get_tools.return_value)

    def test_load_calls_get_tools(self):
        svc = _make_service()
        ToolSettingsModel(svc).load()
        svc.get_tools.assert_called_once()


class TestToolSettingsModelSave(unittest.TestCase):

    def test_save_with_no_args_does_not_raise(self):
        ToolSettingsModel(_make_service()).save()

    def test_save_with_arbitrary_args_does_not_raise(self):
        ToolSettingsModel(_make_service()).save(1, 2, x=3)


class TestToolSettingsModelDelegation(unittest.TestCase):

    def setUp(self):
        self._svc   = _make_service()
        self._model = ToolSettingsModel(self._svc)

    def test_get_tools_delegates_and_returns(self):
        result = self._model.get_tools()
        self._svc.get_tools.assert_called_once()
        self.assertEqual(result, self._svc.get_tools.return_value)

    def test_get_slots_delegates_and_returns(self):
        result = self._model.get_slots()
        self._svc.get_slots.assert_called_once()
        self.assertEqual(result, self._svc.get_slots.return_value)

    def test_add_tool_delegates_with_args(self):
        result = self._model.add_tool(5, "New")
        self._svc.add_tool.assert_called_once_with(5, "New")
        self.assertEqual(result, (True, "Tool added"))

    def test_update_tool_delegates_with_args(self):
        result = self._model.update_tool(1, "Updated")
        self._svc.update_tool.assert_called_once_with(1, "Updated")
        self.assertEqual(result, (True, "Tool updated"))

    def test_remove_tool_delegates_with_args(self):
        result = self._model.remove_tool(1)
        self._svc.remove_tool.assert_called_once_with(1)
        self.assertEqual(result, (True, "Removed"))

    def test_update_slot_delegates_with_args(self):
        result = self._model.update_slot(10, 1)
        self._svc.update_slot.assert_called_once_with(10, 1)
        self.assertEqual(result, (True, "Slot updated"))

    def test_add_slot_delegates_with_args(self):
        result = self._model.add_slot(20, 1)
        self._svc.add_slot.assert_called_once_with(20, 1)
        self.assertEqual(result, (True, "Slot added"))

    def test_remove_slot_delegates_with_args(self):
        result = self._model.remove_slot(10)
        self._svc.remove_slot.assert_called_once_with(10)
        self.assertEqual(result, (True, "Removed"))


if __name__ == "__main__":
    unittest.main()