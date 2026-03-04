from src.applications.base.i_application_model import IApplicationModel
from ..service.i_tool_settings_service import IToolSettingsService


class ToolSettingsModel(IApplicationModel):

    def __init__(self, service: IToolSettingsService):
        self._service = service

    def load(self):
        return self._service.get_tools()

    def save(self, *_, **__): pass

    def get_tools(self):                        return self._service.get_tools()
    def get_slots(self):                        return self._service.get_slots()

    def add_tool(self, tool_id, name):          return self._service.add_tool(tool_id, name)
    def update_tool(self, tool_id, name):       return self._service.update_tool(tool_id, name)
    def remove_tool(self, tool_id):             return self._service.remove_tool(tool_id)
    def update_slot(self, slot_id, tool_id):    return self._service.update_slot(slot_id, tool_id)
    def add_slot(self, slot_id, tool_id):   return self._service.add_slot(slot_id, tool_id)
    def remove_slot(self, slot_id):         return self._service.remove_slot(slot_id)