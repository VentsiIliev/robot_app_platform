from src.applications.base.i_application_model import IApplicationModel
from src.applications.workpiece_editor.service import IWorkpieceEditorService


class WorkpieceEditorModel(IApplicationModel):

    def __init__(self, service: IWorkpieceEditorService):
        self._service = service

    def load(self) -> None:
        pass

    def save(self, *args, **kwargs) -> None:
        pass


    def get_contours(self) -> list:
        return self._service.get_contours()

    def save_workpiece(self, data: dict) -> tuple[bool, str]:
        return self._service.save_workpiece(data)

    def execute_workpiece(self, data: dict) -> tuple[bool, str]:
        return self._service.execute_workpiece(data)

    def get_last_interpolation_preview_contours(self) -> list:
        return self._service.get_last_interpolation_preview_contours()

    def get_last_interpolation_preview_paths(self) -> list:
        return self._service.get_last_interpolation_preview_paths()

    def get_last_original_preview_paths(self) -> list:
        return self._service.get_last_original_preview_paths()

    def get_last_pre_smoothed_preview_paths(self) -> list:
        return self._service.get_last_pre_smoothed_preview_paths()

    def get_last_linear_preview_paths(self) -> list:
        return self._service.get_last_linear_preview_paths()

    def get_last_execution_preview_paths(self) -> list:
        return self._service.get_last_execution_preview_paths()

    def execute_last_preview_paths(self) -> tuple[bool, str]:
        return self._service.execute_last_preview_paths()

    def set_editing(self, storage_id) -> None:
        self._service.set_editing(storage_id)
