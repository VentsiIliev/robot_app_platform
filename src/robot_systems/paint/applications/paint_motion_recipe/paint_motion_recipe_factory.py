from __future__ import annotations

from src.applications.base.application_factory import ApplicationFactory
from src.robot_systems.paint.applications.paint_motion_recipe.controller.paint_motion_recipe_controller import (
    PaintMotionRecipeController,
)
from src.robot_systems.paint.applications.paint_motion_recipe.model.paint_motion_recipe_model import (
    PaintMotionRecipeModel,
)
from src.robot_systems.paint.applications.paint_motion_recipe.service.i_paint_motion_recipe_service import (
    IPaintMotionRecipeService,
)
from src.robot_systems.paint.applications.paint_motion_recipe.view.paint_motion_recipe_view import (
    PaintMotionRecipeView,
)


class PaintMotionRecipeFactory(ApplicationFactory):
    def _create_model(self, service: IPaintMotionRecipeService) -> PaintMotionRecipeModel:
        return PaintMotionRecipeModel(service)

    def _create_view(self) -> PaintMotionRecipeView:
        return PaintMotionRecipeView()

    def _create_controller(
        self,
        model: PaintMotionRecipeModel,
        view: PaintMotionRecipeView,
    ) -> PaintMotionRecipeController:
        return PaintMotionRecipeController(model, view)
