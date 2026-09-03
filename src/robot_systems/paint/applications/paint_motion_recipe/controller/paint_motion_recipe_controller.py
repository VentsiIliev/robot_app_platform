from __future__ import annotations

from src.applications.base.i_application_controller import IApplicationController
from src.robot_systems.paint.applications.paint_motion_recipe.model.paint_motion_recipe_model import (
    PaintMotionRecipeModel,
)
from src.robot_systems.paint.applications.paint_motion_recipe.view.paint_motion_recipe_view import (
    PaintMotionRecipeView,
)


class PaintMotionRecipeController(IApplicationController):
    def __init__(self, model: PaintMotionRecipeModel, view: PaintMotionRecipeView) -> None:
        self._model = model
        self._view = view

        view.add_group_step_requested.connect(self._on_add_group_step)
        view.capture_pose_step_requested.connect(self._on_capture_pose_step)
        view.remove_step_requested.connect(self._on_remove_step)
        view.move_step_requested.connect(self._on_move_step)
        view.step_enabled_changed.connect(self._on_step_enabled_changed)
        view.save_requested.connect(self._on_save)
        view.reload_requested.connect(self._on_reload)
        view.test_step_requested.connect(self._on_test_step)

    def load(self) -> None:
        self._reload()

    def stop(self) -> None:
        try:
            self._view.add_group_step_requested.disconnect(self._on_add_group_step)
            self._view.capture_pose_step_requested.disconnect(self._on_capture_pose_step)
            self._view.remove_step_requested.disconnect(self._on_remove_step)
            self._view.move_step_requested.disconnect(self._on_move_step)
            self._view.step_enabled_changed.disconnect(self._on_step_enabled_changed)
            self._view.save_requested.disconnect(self._on_save)
            self._view.reload_requested.disconnect(self._on_reload)
            self._view.test_step_requested.disconnect(self._on_test_step)
        except (RuntimeError, TypeError):
            pass

    def _reload(self) -> None:
        try:
            recipe = self._model.load()
            self._view.set_groups(self._model.group_ids)
            self._view.set_recipe(recipe)
            self._view.set_status("Loaded")
        except Exception as exc:
            self._view.show_error("Recipe Load Failed", str(exc))

    def _on_reload(self) -> None:
        self._reload()

    def _on_save(self) -> None:
        try:
            self._model.save()
            self._view.set_status("Saved")
            self._view.show_info("Recipe Saved", "Paint development motion recipe saved.")
        except Exception as exc:
            self._view.show_error("Save Failed", str(exc))

    def _on_add_group_step(self, label: str, action: str, group_id: str) -> None:
        recipe = self._model.add_group_step(label=label, action=action, group_id=group_id)
        self._view.set_recipe(recipe)
        self._view.set_status("Step added")

    def _on_capture_pose_step(self, label: str) -> None:
        try:
            recipe = self._model.add_captured_pose_step(label=label)
            self._view.set_recipe(recipe)
            self._view.set_status("Mock pose captured")
        except Exception as exc:
            self._view.show_error("Capture Failed", str(exc))

    def _on_remove_step(self, index: int) -> None:
        self._view.set_recipe(self._model.remove_step(index))
        self._view.set_status("Step removed")

    def _on_move_step(self, index: int, delta: int) -> None:
        self._view.set_recipe(self._model.move_step(index, delta))

    def _on_step_enabled_changed(self, index: int, enabled: bool) -> None:
        self._view.set_recipe(self._model.toggle_step(index, enabled))

    def _on_test_step(self, index: int) -> None:
        ok, message = self._model.test_step(index)
        self._view.set_status(message)
        if ok:
            self._view.show_info("Mock Step Test", message)
        else:
            self._view.show_error("Mock Step Test", message)
