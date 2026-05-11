import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.robot_systems.welding import application_wiring


class TestWeldingTargetingRefreshWiring(unittest.TestCase):
    def test_welding_contour_editor_uses_live_resolver_getter_for_path_preparation(self):
        resolver = object()
        transformer = object()
        robot_system = SimpleNamespace(
            _robot_config=SimpleNamespace(safety_limits=SimpleNamespace(z_min=100.0)),
            get_optional_service=MagicMock(side_effect=lambda key: {"vision": None, "robot": None}.get(getattr(key, "value", key))),
            get_shared_vision_resolver=MagicMock(return_value=(transformer, resolver)),
            get_target_point_definition=MagicMock(return_value=SimpleNamespace(name="camera")),
            storage_path=MagicMock(return_value="/tmp/contours"),
        )

        with (
            patch("src.robot_systems.welding.application_wiring.os.makedirs"),
            patch("src.robot_systems.welding.domain.contour_editor_schema.build_welding_segment_settings_schema", return_value="segment-schema"),
            patch("src.applications.workpiece_editor.editor_core.config.SegmentEditorConfig", side_effect=lambda schema: SimpleNamespace(schema=schema)),
            patch("src.engine.robot.path_preparation.DefaultWorkpiecePathPreparationService", return_value="path-prep") as prep_cls,
            patch("src.applications.workpiece_editor.service.workpiece_editor_service.WorkpieceEditorStorage", side_effect=lambda **kwargs: SimpleNamespace(**kwargs)),
            patch("src.applications.workpiece_editor.service.workpiece_editor_service.WorkpieceEditorServices", side_effect=lambda **kwargs: SimpleNamespace(**kwargs)),
            patch("src.applications.workpiece_editor.service.workpiece_editor_service.WorkpieceEditorService", side_effect=lambda **kwargs: SimpleNamespace(**kwargs)),
            patch("src.robot_systems.welding.domain.contour_editor_schema.build_welding_contour_form_schema", return_value="form-schema"),
            patch("src.robot_systems.welding.workpiece_path_executor.WeldingWorkpiecePathExecutor", return_value="executor"),
            patch("src.applications.workpiece_editor.workpiece_editor_factory.WorkpieceEditorFactory") as factory_cls,
            patch("src.applications.base.robot_jog_service_builder.build_robot_system_jog_service", return_value="jog"),
            patch("src.robot_systems.welding.application_wiring._build_capture_snapshot_service", return_value="snapshot"),
        ):
            factory_cls.return_value.build.return_value = "widget"
            app = application_wiring._build_welding_contour_editor_application(robot_system)
            app.register("broker")
            app.create_widget()

        kwargs = prep_cls.call_args.kwargs
        self.assertIsNone(kwargs["resolver"])
        self.assertIs(kwargs["resolver_getter"](), resolver)


if __name__ == "__main__":
    unittest.main()
