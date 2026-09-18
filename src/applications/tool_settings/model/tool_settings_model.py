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
    def update_tool_geometry(self, tool_id, transform, collision_profile=""):
        return self._service.update_tool_geometry(tool_id, transform, collision_profile)
    def update_slot_sequences(self, slot_id, pickup, dropoff):
        return self._service.update_slot_sequences(slot_id, pickup, dropoff)
    def capture_reference_contact(self): return self._service.capture_reference_contact()
    def capture_tool_contact(self): return self._service.capture_tool_contact()
    def solve_tool_calibration(self, tool_id): return self._service.solve_tool_calibration(tool_id)
    def activate_tool(self, tool_id): return self._service.activate_tool(tool_id)
    def get_current_motion_pose(self): return self._service.get_current_motion_pose()
