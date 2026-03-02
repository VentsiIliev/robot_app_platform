from typing import List
from src.applications.base.i_application_model import IApplicationModel
from src.robot_systems.glue.applications.workpiece_editor.service import IWorkpieceEditorService


class WorkpieceEditorModel(IApplicationModel):

    def __init__(self, service: IWorkpieceEditorService):
        self._service = service

    def load(self) -> List[str]:
        return self._service.get_glue_types()

    def save(self, *args, **kwargs) -> None:
        pass

    def get_glue_types(self) -> List[str]:
        return self._service.get_glue_types()

    def get_contours(self) -> list:
        return self._service.get_contours()

    def save_workpiece(self, data: dict) -> tuple[bool, str]:
        return self._service.save_workpiece(data)

    def execute_workpiece(self, data: dict) -> tuple[bool, str]:
        return self._service.execute_workpiece(data)