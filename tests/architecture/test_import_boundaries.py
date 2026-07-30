import ast
import unittest
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, order=True)
class ImportViolation:
    source: str
    imported_module: str


_LEGACY_VIOLATIONS = {
    ImportViolation(
        "src/applications/calibration/controller/calibration_controller.py",
        "src.robot_systems.glue.component_ids",
    ),
    ImportViolation(
        "src/applications/calibration_v2/controller/calibration_controller.py",
        "src.robot_systems.glue.component_ids",
    ),
    ImportViolation(
        "src/applications/pick_and_place_visualizer/controller/pick_and_place_visualizer_controller.py",
        "src.robot_systems.glue.component_ids",
    ),
    ImportViolation(
        "src/applications/pick_and_place_visualizer/service/pick_and_place_visualizer_service.py",
        "src.robot_systems.glue.domain.matching.i_matching_service",
    ),
    ImportViolation(
        "src/applications/pick_and_place_visualizer/service/pick_and_place_visualizer_service.py",
        "src.robot_systems.glue.processes.pick_and_place.config",
    ),
    ImportViolation(
        "src/applications/pick_and_place_visualizer/service/pick_and_place_visualizer_service.py",
        "src.robot_systems.glue.processes.pick_and_place.plane",
    ),
    ImportViolation(
        "src/applications/pick_and_place_visualizer/service/pick_and_place_visualizer_service.py",
        "src.robot_systems.glue.processes.pick_and_place.planning",
    ),
    ImportViolation(
        "src/applications/pick_target/service/stub_pick_target_service.py",
        "src.robot_systems.glue.targeting.registry",
    ),
    ImportViolation(
        "src/applications/workpiece_editor/controller/workpiece_editor_controller.py",
        "src.robot_systems.paint.processes.paint.align",
    ),
    ImportViolation(
        "src/applications/workpiece_editor/controller/workpiece_editor_controller.py",
        "src.robot_systems.paint.processes.paint.config",
    ),
    ImportViolation(
        "src/applications/workpiece_editor/editor_core/adapters/workpiece_adapter.py",
        "src.robot_systems.paint.domain.paint_workpiece_editor_adapter",
    ),
    ImportViolation(
        "src/engine/hardware/weight/http/http_weight_cell_factory.py",
        "src.robot_systems.glue.settings.cells",
    ),
    ImportViolation(
        "src/engine/hardware/weight/interfaces/i_cell_calibrator.py",
        "src.robot_systems.glue.settings.cells",
    ),
    ImportViolation(
        "src/engine/hardware/weight/interfaces/i_weight_cell_service.py",
        "src.robot_systems.glue.settings.cells",
    ),
    ImportViolation(
        "src/engine/robot/path_interpolation/new_interpolation/simple_interpolation_pyqt6.py",
        "src.robot_systems.glue.glue_robot_system",
    ),
    ImportViolation(
        "src/robot_systems/paint/processes/robot_calibration_process.py",
        "src.robot_systems.glue.component_ids",
    ),
    ImportViolation(
        "src/robot_systems/welding/processes/robot_calibration_process.py",
        "src.robot_systems.glue.component_ids",
    ),
}


class TestImportBoundaries(unittest.TestCase):
    def test_cross_layer_and_cross_system_imports_match_known_debt(self):
        concrete_robot_systems = (
            "src.robot_systems.paint",
            "src.robot_systems.glue",
            "src.robot_systems.welding",
        )
        actual = set()
        actual.update(_find_imports("src/engine", concrete_robot_systems))
        actual.update(_find_imports("src/bootstrap", concrete_robot_systems))
        actual.update(_find_imports("src/applications", concrete_robot_systems))
        actual.update(_find_imports("src/shared_contracts", concrete_robot_systems))
        actual.update(_find_imports("pl_gui", concrete_robot_systems))
        actual.update(
            _find_imports(
                "src/robot_systems/paint",
                ("src.robot_systems.glue", "src.robot_systems.welding"),
            )
        )
        actual.update(
            _find_imports(
                "src/robot_systems/glue",
                ("src.robot_systems.paint", "src.robot_systems.welding"),
            )
        )
        actual.update(
            _find_imports(
                "src/robot_systems/welding",
                ("src.robot_systems.paint", "src.robot_systems.glue"),
            )
        )

        unexpected = sorted(actual - _LEGACY_VIOLATIONS)
        resolved = sorted(_LEGACY_VIOLATIONS - actual)
        self.assertFalse(
            unexpected or resolved,
            _format_failure(unexpected=unexpected, resolved=resolved),
        )


def _find_imports(
    relative_root: str,
    forbidden_prefixes: tuple[str, ...],
) -> set[ImportViolation]:
    violations = set()
    source_root = ROOT / relative_root
    for source_path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(
            source_path.read_text(encoding="utf-8"),
            filename=str(source_path),
        )
        for imported_module in _imported_modules(tree):
            if any(
                imported_module == prefix
                or imported_module.startswith(f"{prefix}.")
                for prefix in forbidden_prefixes
            ):
                violations.add(
                    ImportViolation(
                        source_path.relative_to(ROOT).as_posix(),
                        imported_module,
                    )
                )
    return violations


def _imported_modules(tree: ast.AST) -> tuple[str, ...]:
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return tuple(modules)


def _format_failure(
    *,
    unexpected: list[ImportViolation],
    resolved: list[ImportViolation],
) -> str:
    sections = [
        "Robot-system import boundaries changed.",
        "Reusable layers must not depend on concrete robot systems, and robot "
        "systems must not depend on each other.",
    ]
    if unexpected:
        sections.append("\nNew violations (remove the import or justify the boundary):")
        sections.extend(
            f"  + {item.source} -> {item.imported_module}"
            for item in unexpected
        )
    if resolved:
        sections.append("\nResolved violations (remove these from _LEGACY_VIOLATIONS):")
        sections.extend(
            f"  - {item.source} -> {item.imported_module}"
            for item in resolved
        )
    return "\n".join(sections)


if __name__ == "__main__":
    unittest.main()
