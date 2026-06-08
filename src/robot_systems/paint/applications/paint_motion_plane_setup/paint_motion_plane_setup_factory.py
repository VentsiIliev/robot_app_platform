from __future__ import annotations

from src.applications.base.application_factory import ApplicationFactory
from src.robot_systems.paint.applications.paint_motion_plane_setup.controller.paint_motion_plane_setup_controller import (
    PaintMotionPlaneSetupController,
)
from src.robot_systems.paint.applications.paint_motion_plane_setup.model.paint_motion_plane_setup_model import (
    PaintMotionPlaneSetupModel,
)
from src.robot_systems.paint.applications.paint_motion_plane_setup.service.i_paint_motion_plane_setup_service import (
    IPaintMotionPlaneSetupService,
)
from src.robot_systems.paint.applications.paint_motion_plane_setup.view.paint_motion_plane_setup_view import (
    PaintMotionPlaneSetupView,
)


class PaintMotionPlaneSetupFactory(ApplicationFactory):
    def _create_model(self, service: IPaintMotionPlaneSetupService) -> PaintMotionPlaneSetupModel:
        return PaintMotionPlaneSetupModel(service)

    def _create_view(self) -> PaintMotionPlaneSetupView:
        return PaintMotionPlaneSetupView()

    def _create_controller(
        self,
        model: PaintMotionPlaneSetupModel,
        view: PaintMotionPlaneSetupView,
    ) -> PaintMotionPlaneSetupController:
        return PaintMotionPlaneSetupController(model, view)
