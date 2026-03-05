import sys
import unittest
from unittest.mock import MagicMock

from src.applications.tool_settings.service.i_tool_settings_service import IToolSettingsService
from src.applications.tool_settings.tool_settings_factory import ToolSettingsFactory
from src.applications.tool_settings.view.tool_settings_view import ToolSettingsView
from src.applications.tool_settings.controller.tool_settings_controller import ToolSettingsController
from src.engine.robot.interfaces.tool_definition import ToolDefinition
from src.engine.robot.tool_changer import SlotConfig


def _make_service():
    svc = MagicMock(spec=IToolSettingsService)
    svc.get_tools.return_value = [ToolDefinition(1, "Gripper")]
    svc.get_slots.return_value = [SlotConfig(id=10, tool_id=1)]
    return svc


class TestToolSettingsFactory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls._app = QApplication.instance() or QApplication(sys.argv)

    def test_build_returns_tool_settings_view(self):
        self.assertIsInstance(ToolSettingsFactory().build(_make_service()), ToolSettingsView)

    def test_build_attaches_controller_to_view(self):
        view = ToolSettingsFactory().build(_make_service())
        self.assertIsInstance(view._controller, ToolSettingsController)

    def test_build_calls_get_tools_via_load(self):
        svc = _make_service()
        ToolSettingsFactory().build(svc)
        svc.get_tools.assert_called()

    def test_build_calls_get_slots_via_load(self):
        svc = _make_service()
        ToolSettingsFactory().build(svc)
        svc.get_slots.assert_called()

    def test_two_builds_produce_independent_views(self):
        v1 = ToolSettingsFactory().build(_make_service())
        v2 = ToolSettingsFactory().build(_make_service())
        self.assertIsNot(v1, v2)
        self.assertIsNot(v1._controller, v2._controller)


if __name__ == "__main__":
    unittest.main()