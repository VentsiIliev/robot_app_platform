from __future__ import annotations

from abc import ABC, abstractmethod

from src.robot_systems.paint.applications.paint_motion_recipe.domain.recipe import (
    MotionRecipe,
    MotionRecipeStep,
    Pose6D,
)


class IPaintMotionRecipeService(ABC):
    @abstractmethod
    def load_recipe(self) -> MotionRecipe: ...

    @abstractmethod
    def save_recipe(self, recipe: MotionRecipe) -> None: ...

    @abstractmethod
    def get_group_ids(self) -> list[str]: ...

    @abstractmethod
    def get_group_pose(self, group_id: str) -> Pose6D | None: ...

    @abstractmethod
    def capture_current_pose(self) -> Pose6D: ...

    @abstractmethod
    def test_step(self, step: MotionRecipeStep) -> tuple[bool, str]: ...
