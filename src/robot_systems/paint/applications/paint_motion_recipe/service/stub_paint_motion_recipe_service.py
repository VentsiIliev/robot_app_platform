from __future__ import annotations

from src.robot_systems.paint.applications.paint_motion_recipe.domain.recipe import (
    MotionRecipe,
    MotionRecipeStep,
    Pose6D,
)
from src.robot_systems.paint.applications.paint_motion_recipe.service.i_paint_motion_recipe_service import (
    IPaintMotionRecipeService,
)


class StubPaintMotionRecipeService(IPaintMotionRecipeService):
    def __init__(self) -> None:
        self._recipe = MotionRecipe.default()
        self._groups = ["Magazine", "CALIBRATION", "Dropoff", "HOME"]
        self._poses = {
            "Magazine": [100.0, 200.0, 300.0, 180.0, 0.0, 90.0],
            "CALIBRATION": [0.0, 0.0, 300.0, 180.0, 0.0, 0.0],
            "Dropoff": [300.0, 100.0, 260.0, 180.0, 0.0, 0.0],
            "HOME": [0.0, 0.0, 500.0, 180.0, 0.0, 0.0],
        }
        self._pose = list(self._poses["CALIBRATION"])

    def load_recipe(self) -> MotionRecipe:
        return self._recipe

    def save_recipe(self, recipe: MotionRecipe) -> None:
        self._recipe = recipe

    def get_group_ids(self) -> list[str]:
        return list(self._groups)

    def get_group_pose(self, group_id: str) -> Pose6D | None:
        pose = self._poses.get(str(group_id or "").strip())
        return list(pose) if pose is not None else None

    def capture_current_pose(self) -> Pose6D:
        return list(self._pose)

    def test_step(self, step: MotionRecipeStep) -> tuple[bool, str]:
        if step.action == "move_group":
            pose = self.get_group_pose(step.group_id)
            if pose is None:
                return False, f"Movement group '{step.group_id}' has no configured position."
            self._pose = pose
            return True, f"Stub moved to group '{step.group_id}'."
        if step.action == "move_pose" and step.pose is not None:
            self._pose = list(step.pose)
            return True, "Stub moved to captured pose."
        if step.action in {"vacuum_on", "vacuum_off"}:
            return True, f"Stub {step.action} completed."
        return True, f"Stub action '{step.action}' completed."
