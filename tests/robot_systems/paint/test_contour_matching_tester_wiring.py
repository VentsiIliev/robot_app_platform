import unittest

from src.robot_systems.paint.paint_robot_system import PaintRobotSystem


class TestContourMatchingTesterWiring(unittest.TestCase):
    def test_paint_exposes_matching_tester_in_tests_folder(self):
        app = next(
            spec
            for spec in PaintRobotSystem.shell.applications
            if spec.name == "ContourMatchingTester"
        )

        self.assertEqual(4, app.folder_id)
        self.assertEqual(
            ["Admin", "Developer"],
            PaintRobotSystem.role_policy.protected_app_role_values[app.app_id],
        )


if __name__ == "__main__":
    unittest.main()
