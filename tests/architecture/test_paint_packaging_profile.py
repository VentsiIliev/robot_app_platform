import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGING_ROOT = ROOT / "packaging"


class TestPaintPackagingProfile(unittest.TestCase):
    def test_bundled_startup_config_selects_only_paint(self):
        config = json.loads(
            (PACKAGING_ROOT / "paint_config" / "platform.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(config["robot_system"], "paint")
        self.assertEqual(config["supported_robot_systems"], ["paint"])

    def test_spec_excludes_other_robot_systems(self):
        assignments = _literal_assignments(PACKAGING_ROOT / "paint.spec")

        self.assertEqual(
            set(assignments["excluded_robot_systems"]),
            {
                "src.robot_systems.glue",
                "src.robot_systems.welding",
                "src.robot_systems.ROBOT_SYSTEM_BLUEPRINT",
            },
        )

    def test_build_script_checks_collected_module_archive(self):
        script = (PACKAGING_ROOT / "build_paint.sh").read_text(encoding="utf-8")

        self.assertIn("PYZ-00.toc", script)
        self.assertIn("src\\\\.robot_systems\\\\.(glue|welding)", script)


def _literal_assignments(path: Path) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assignments = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            assignments[target.id] = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
    return assignments


if __name__ == "__main__":
    unittest.main()
