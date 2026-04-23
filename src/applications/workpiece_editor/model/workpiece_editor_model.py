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

    def get_last_sampled_preview_paths(self) -> list:
        return self._service.get_last_sampled_preview_paths()

    def get_last_raw_preview_paths(self) -> list:
        return self._service.get_last_raw_preview_paths()

    def get_last_prepared_preview_paths(self) -> list:
        return self._service.get_last_prepared_preview_paths()

    def get_last_curve_preview_paths(self) -> list:
        return self._service.get_last_curve_preview_paths()

    def get_last_execution_preview_paths(self) -> list:
        return self._service.get_last_execution_preview_paths()

    def get_last_pivot_preview_paths(self) -> tuple[list[list[list[float]]], list[float] | None]:
        return self._service.get_last_pivot_preview_paths()

    def get_last_pivot_motion_preview(self):
        return self._service.get_last_pivot_motion_preview()

    def get_available_execution_modes(self) -> tuple[str, ...]:
        return self._service.get_available_execution_modes()

    def can_execute_pickup_to_pivot(self) -> bool:
        return self._service.can_execute_pickup_to_pivot()

    def execute_pickup_to_pivot(self) -> tuple[bool, str]:
        return self._service.execute_pickup_to_pivot()

    def execute_pickup_and_pivot_paint(self) -> tuple[bool, str]:
        return self._service.execute_pickup_and_pivot_paint()

    def execute_last_preview_paths(self, mode: str = "continuous") -> tuple[bool, str]:
        return self._service.execute_last_preview_paths(mode=mode)

    def can_import_dxf_test(self) -> bool:
        return self._service.can_import_dxf_test()

    def prepare_dxf_test_raw_for_image(
        self,
        raw: dict,
        image_width: float,
        image_height: float,
    ) -> dict:
        return self._service.prepare_dxf_test_raw_for_image(raw, image_width, image_height)

    def set_editing(self, storage_id) -> None:
        self._service.set_editing(storage_id)

    def can_match_saved_workpieces(self) -> bool:
        return self._service.can_match_saved_workpieces()

    def match_saved_workpieces(self, contour) -> tuple[bool, dict | None, str]:
        return self._service.match_saved_workpieces(contour)
