from __future__ import annotations

from src.applications.base.i_application_model import IApplicationModel
from src.robot_systems.paint.applications.paint_motion_plane_setup.domain.plane_inference import (
    PlaneInference,
    Pose6D,
    infer_plane,
)
from src.robot_systems.paint.applications.paint_motion_plane_setup.service.i_paint_motion_plane_setup_service import (
    IPaintMotionPlaneSetupService,
)


class PaintMotionPlaneSetupModel(IApplicationModel):
    def __init__(self, service: IPaintMotionPlaneSetupService) -> None:
        self._service = service
        self.paint_pose: Pose6D | None = None
        self.reference_pose: Pose6D | None = None
        self.translation_pose: Pose6D | None = None
        self.rotation_pose: Pose6D | None = None
        self.fixed_axis: str | None = None
        self.inference: PlaneInference | None = None

    def load(self) -> None:
        self.paint_pose = self._service.get_paint_pose()

    def save(self, *args, **kwargs) -> None:
        return None

    def get_current_pose(self) -> Pose6D:
        return self._service.get_current_pose()

    def move_to_paint_pose(self) -> bool:
        return self._service.move_to_paint_pose()

    def update_inference(self) -> PlaneInference | None:
        if self.reference_pose is None or self.translation_pose is None or self.rotation_pose is None:
            self.inference = None
            return None
        self.inference = infer_plane(
            self.reference_pose,
            self.translation_pose,
            self.rotation_pose,
            fixed_axis_override=self.fixed_axis,
        )
        return self.inference
