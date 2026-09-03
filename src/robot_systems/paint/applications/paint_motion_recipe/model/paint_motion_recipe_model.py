from __future__ import annotations

from dataclasses import replace

from src.applications.base.i_application_model import IApplicationModel
from src.robot_systems.paint.applications.paint_motion_recipe.domain.recipe import (
    MotionRecipe,
    MotionRecipeStep,
)
from src.robot_systems.paint.applications.paint_motion_recipe.service.i_paint_motion_recipe_service import (
    IPaintMotionRecipeService,
)


class PaintMotionRecipeModel(IApplicationModel):
    def __init__(self, service: IPaintMotionRecipeService) -> None:
        self._service = service
        self._recipe = MotionRecipe.default()
        self._group_ids: list[str] = []

    def load(self) -> MotionRecipe:
        self._recipe = self._service.load_recipe()
        self._group_ids = self._service.get_group_ids()
        return self._recipe

    def save(self, _data=None) -> None:
        self._service.save_recipe(self._recipe)

    @property
    def recipe(self) -> MotionRecipe:
        return self._recipe

    @property
    def group_ids(self) -> list[str]:
        return list(self._group_ids)

    def add_group_step(self, *, label: str, action: str, group_id: str) -> MotionRecipe:
        step = MotionRecipeStep.new(label=label, action=action, group_id=group_id)
        self._recipe = replace(self._recipe, steps=self._recipe.steps + (step,))
        return self._recipe

    def add_captured_pose_step(self, *, label: str) -> MotionRecipe:
        pose = self._service.capture_current_pose()
        step = MotionRecipeStep.new(label=label, action="move_pose", pose=pose)
        self._recipe = replace(self._recipe, steps=self._recipe.steps + (step,))
        return self._recipe

    def remove_step(self, index: int) -> MotionRecipe:
        steps = list(self._recipe.steps)
        if 0 <= index < len(steps):
            steps.pop(index)
        self._recipe = replace(self._recipe, steps=tuple(steps))
        return self._recipe

    def move_step(self, index: int, delta: int) -> MotionRecipe:
        steps = list(self._recipe.steps)
        new_index = index + delta
        if 0 <= index < len(steps) and 0 <= new_index < len(steps):
            steps[index], steps[new_index] = steps[new_index], steps[index]
        self._recipe = replace(self._recipe, steps=tuple(steps))
        return self._recipe

    def toggle_step(self, index: int, enabled: bool) -> MotionRecipe:
        steps = list(self._recipe.steps)
        if 0 <= index < len(steps):
            steps[index] = replace(steps[index], enabled=bool(enabled))
        self._recipe = replace(self._recipe, steps=tuple(steps))
        return self._recipe

    def test_step(self, index: int) -> tuple[bool, str]:
        if not 0 <= index < len(self._recipe.steps):
            return False, "Select a recipe step first."
        return self._service.test_step(self._recipe.steps[index])
