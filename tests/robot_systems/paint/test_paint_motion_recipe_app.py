import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.robot_systems.paint import application_wiring
from src.robot_systems.paint.applications.paint_motion_recipe.domain.recipe import (
    MotionRecipe,
    MotionRecipeStep,
)
from src.robot_systems.paint.applications.paint_motion_recipe.service.paint_motion_recipe_service import (
    PaintMotionRecipeService,
)
from src.robot_systems.paint.paint_robot_system import PaintRobotSystem


class TestPaintMotionRecipeService(unittest.TestCase):
    def test_missing_recipe_file_creates_default_recipe(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dev_motion_recipe.json"
            service = PaintMotionRecipeService(recipe_path=str(path), group_ids=["Magazine"])

            recipe = service.load_recipe()

            self.assertTrue(path.exists())
            self.assertTrue(recipe.mock_only)
            self.assertGreater(len(recipe.steps), 0)

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "recipe.json"
            service = PaintMotionRecipeService(recipe_path=str(path), group_ids=["Magazine"])
            recipe = MotionRecipe(
                name="Dev",
                steps=(MotionRecipeStep.new(label="Magazine", action="move_group", group_id="Magazine"),),
            )

            service.save_recipe(recipe)
            loaded = service.load_recipe()

            self.assertEqual("Dev", loaded.name)
            self.assertEqual("Magazine", loaded.steps[0].group_id)
            self.assertEqual(json.loads(path.read_text())["name"], "Dev")

    def test_mock_move_group_updates_pose_without_real_robot_motion(self):
        navigation = MagicMock()
        navigation.get_group_position.return_value = [1, 2, 3, 4, 5, 6]
        service = PaintMotionRecipeService(
            recipe_path="/tmp/not-used.json",
            group_ids=["Magazine"],
            navigation_service=navigation,
        )

        ok, message = service.test_step(
            MotionRecipeStep.new(label="Move", action="move_group", group_id="Magazine")
        )

        self.assertTrue(ok, message)
        self.assertEqual([1, 2, 3, 4, 5, 6], service.capture_current_pose())
        navigation.move_to_group.assert_not_called()

    def test_mock_vacuum_steps_do_not_call_hardware(self):
        navigation = MagicMock()
        service = PaintMotionRecipeService(
            recipe_path="/tmp/not-used.json",
            group_ids=["Magazine", "Dropoff"],
            navigation_service=navigation,
        )

        on_ok, on_message = service.test_step(
            MotionRecipeStep.new(label="Pick", action="vacuum_on", group_id="Magazine")
        )
        off_ok, off_message = service.test_step(
            MotionRecipeStep.new(label="Drop", action="vacuum_off", group_id="Dropoff")
        )

        self.assertTrue(on_ok, on_message)
        self.assertTrue(off_ok, off_message)
        self.assertEqual([], navigation.method_calls)

    def test_default_recipe_has_explicit_vacuum_pick_and_drop_steps(self):
        actions = [step.action for step in MotionRecipe.default().steps]

        self.assertIn("vacuum_on", actions)
        self.assertIn("vacuum_off", actions)
        self.assertLess(actions.index("vacuum_on"), actions.index("vacuum_off"))


class TestPaintMotionRecipeWiring(unittest.TestCase):
    def test_paint_system_declares_developer_motion_recipe_app(self):
        app = next(
            spec
            for spec in PaintRobotSystem.shell.applications
            if spec.name == "PaintMotionRecipe"
        )

        self.assertEqual(4, app.folder_id)
        self.assertEqual(["Admin", "Developer"], PaintRobotSystem.role_policy.protected_app_role_values[app.app_id])

    def test_build_paint_motion_recipe_application_wires_mock_safe_service(self):
        robot_system = SimpleNamespace(
            _navigation="navigation",
            get_movement_group_definitions=MagicMock(
                return_value=[
                    SimpleNamespace(id="Magazine"),
                    SimpleNamespace(id="CALIBRATION"),
                ]
            ),
        )
        factory = MagicMock()
        factory.build.return_value = "recipe-widget"

        with (
            patch(
                "src.robot_systems.paint.applications.paint_motion_recipe.service.PaintMotionRecipeService",
                return_value="recipe-service",
            ) as service_cls,
            patch(
                "src.robot_systems.paint.applications.paint_motion_recipe.PaintMotionRecipeFactory",
                return_value=factory,
            ),
        ):
            app = application_wiring._build_paint_motion_recipe_application(robot_system)
            app.register(MagicMock())
            self.assertEqual("recipe-widget", app.create_widget())

        self.assertEqual(service_cls.call_args.kwargs["group_ids"], ["Magazine", "CALIBRATION"])
        self.assertEqual(service_cls.call_args.kwargs["navigation_service"], "navigation")
        self.assertTrue(service_cls.call_args.kwargs["recipe_path"].endswith("dev_motion_recipe.json"))
        factory.build.assert_called_once_with("recipe-service")


if __name__ == "__main__":
    unittest.main()
