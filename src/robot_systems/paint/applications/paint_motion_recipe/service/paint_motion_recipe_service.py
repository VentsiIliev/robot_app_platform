from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Iterable

from src.robot_systems.paint.applications.paint_motion_recipe.domain.recipe import (
    MotionRecipe,
    MotionRecipeStep,
    Pose6D,
)
from src.robot_systems.paint.applications.paint_motion_recipe.service.i_paint_motion_recipe_service import (
    IPaintMotionRecipeService,
)

_logger = logging.getLogger(__name__)


class PaintMotionRecipeService(IPaintMotionRecipeService):
    """Developer-only recipe storage and mock motion tester."""

    def __init__(
        self,
        *,
        recipe_path: str,
        group_ids: Iterable[str] = (),
        navigation_service=None,
        initial_mock_pose: Pose6D | None = None,
    ) -> None:
        self._recipe_path = Path(recipe_path)
        self._group_ids = tuple(str(group_id).strip() for group_id in group_ids if str(group_id).strip())
        self._navigation = navigation_service
        self._mock_pose = list(initial_mock_pose or [0.0, 0.0, 300.0, 180.0, 0.0, 0.0])

    def load_recipe(self) -> MotionRecipe:
        if not self._recipe_path.exists():
            recipe = MotionRecipe.default()
            self.save_recipe(recipe)
            return recipe
        try:
            with self._recipe_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            recipe = MotionRecipe.from_dict(data)
            return recipe if recipe.steps else MotionRecipe.default()
        except Exception:
            _logger.exception("Failed to load paint motion recipe from %s", self._recipe_path)
            return MotionRecipe.default()

    def save_recipe(self, recipe: MotionRecipe) -> None:
        os.makedirs(self._recipe_path.parent, exist_ok=True)
        with self._recipe_path.open("w", encoding="utf-8") as handle:
            json.dump(recipe.to_dict(), handle, indent=2, sort_keys=True)

    def get_group_ids(self) -> list[str]:
        return list(self._group_ids)

    def get_group_pose(self, group_id: str) -> Pose6D | None:
        group_id = str(group_id or "").strip()
        if not group_id or self._navigation is None:
            return None
        try:
            pose = self._navigation.get_group_position(group_id)
        except Exception:
            _logger.debug("Failed to read group pose for %s", group_id, exc_info=True)
            return None
        if pose is None or len(pose) < 6:
            return None
        return [float(value) for value in pose[:6]]

    def capture_current_pose(self) -> Pose6D:
        return list(self._mock_pose)

    def test_step(self, step: MotionRecipeStep) -> tuple[bool, str]:
        if not step.enabled:
            return False, f"Step '{step.label}' is disabled."
        if step.action == "move_group":
            return self._test_move_group(step)
        if step.action == "move_pose":
            return self._test_move_pose(step)
        if step.action == "capture":
            return True, f"Mock capture at {step.group_id or 'current pose'}."
        if step.action in {"vacuum_on", "vacuum_off", "release", "unwind", "cleanup", "wait"}:
            return True, f"Mock {step.action} completed."
        return False, f"Unsupported recipe action '{step.action}'."

    def _test_move_group(self, step: MotionRecipeStep) -> tuple[bool, str]:
        group_id = str(step.group_id or "").strip()
        if not group_id:
            return False, "Move group step has no movement group."
        if group_id not in self._group_ids:
            return False, f"Movement group '{group_id}' is not declared."
        pose = self.get_group_pose(group_id)
        if pose is None:
            return False, f"Movement group '{group_id}' has no configured position."
        self._mock_pose = list(pose)
        return True, f"Mock moved to group '{group_id}'."

    def _test_move_pose(self, step: MotionRecipeStep) -> tuple[bool, str]:
        if step.pose is None:
            return False, "Move pose step has no captured pose."
        self._mock_pose = list(step.pose)
        return True, "Mock moved to captured pose."
