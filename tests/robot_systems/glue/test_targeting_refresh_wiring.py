import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.robot_systems.glue import application_wiring


class TestGlueTargetingRefreshWiring(unittest.TestCase):
    def test_glue_process_driver_uses_live_resolver_getter_for_job_builder(self):
        resolver = object()
        transformer = object()
        glue_process = MagicMock()
        glue_process.navigation_service = "navigation"
        robot_system = SimpleNamespace(
            _robot_config=SimpleNamespace(safety_limits=SimpleNamespace(z_min=12.0)),
            _messaging_service="messaging",
            coordinator=SimpleNamespace(glue_process=glue_process),
            workpieces_storage_path=MagicMock(return_value="/tmp/workpieces"),
            get_optional_service=MagicMock(side_effect=lambda key: {"vision": "vision"}.get(getattr(key, "value", key))),
            get_shared_vision_resolver=MagicMock(return_value=(transformer, resolver)),
            get_target_point_definition=MagicMock(return_value=SimpleNamespace(name="tool")),
        )

        with (
            patch("src.robot_systems.glue.domain.workpieces.repository.json_workpiece_repository.JsonWorkpieceRepository", return_value="repo"),
            patch("src.robot_systems.glue.domain.workpieces.service.workpiece_service.WorkpieceService", return_value="workpiece-service"),
            patch("src.robot_systems.glue.domain.matching.matching_service.MatchingService", return_value="matching-service"),
            patch("src.robot_systems.glue.domain.glue_job_builder_service.GlueJobBuilderService", return_value="job-builder") as builder_cls,
            patch("src.robot_systems.glue.domain.glue_job_execution_service.GlueJobExecutionService", return_value="execution-service"),
            patch("src.robot_systems.glue.applications.glue_process_driver.GlueProcessDriverService", return_value="driver-service"),
            patch("src.robot_systems.glue.applications.glue_process_driver.GlueProcessDriverFactory") as factory_cls,
            patch("src.robot_systems.glue.application_wiring._build_capture_snapshot_service", return_value="snapshot"),
        ):
            factory_cls.return_value.build.return_value = "widget"
            app = application_wiring._build_glue_process_driver_application(robot_system)
            app.register("broker")
            app.create_widget()

        self.assertEqual(builder_cls.call_count, 2)
        first_kwargs = builder_cls.call_args_list[0].kwargs
        self.assertIsNone(first_kwargs["resolver"])
        self.assertIs(first_kwargs["resolver_getter"](), resolver)

    def test_workpiece_editor_uses_live_resolver_getter_for_path_preparation(self):
        resolver = object()
        transformer = object()
        robot_config = SimpleNamespace(safety_limits=SimpleNamespace(z_min=9.0))
        catalog = MagicMock()
        catalog.get_all_names.return_value = ["Type A"]
        tool_config = MagicMock()
        tool_config.get_tool_options.return_value = []
        settings_service = MagicMock()
        settings_service.get.side_effect = lambda key: catalog if getattr(key, "value", key) == "glue_catalog" else tool_config
        robot_system = SimpleNamespace(
            _settings_service=settings_service,
            _messaging_service=MagicMock(),
            _robot_config=robot_config,
            workpieces_storage_path=MagicMock(return_value="/tmp/workpieces"),
            get_optional_service=MagicMock(side_effect=lambda key: {"vision": None, "robot": None}.get(getattr(key, "value", key))),
            get_shared_vision_resolver=MagicMock(return_value=(transformer, resolver)),
            get_target_point_definition=MagicMock(side_effect=lambda name: SimpleNamespace(name=name)),
        )

        with (
            patch("src.robot_systems.glue.domain.workpieces.repository.json_workpiece_repository.JsonWorkpieceRepository", return_value="repo"),
            patch("src.robot_systems.glue.domain.workpieces.service.workpiece_service.WorkpieceService", return_value=MagicMock(save=MagicMock(), update=MagicMock(), workpiece_id_exists=MagicMock())),
            patch("src.robot_systems.glue.application_wiring.build_glue_segment_settings_schema", return_value="segment-schema"),
            patch("src.applications.workpiece_editor.editor_core.config.SegmentEditorConfig", side_effect=lambda schema: SimpleNamespace(schema=schema)),
            patch("src.engine.robot.path_preparation.DefaultWorkpiecePathPreparationService", return_value="path-prep") as prep_cls,
            patch("src.applications.workpiece_editor.service.workpiece_editor_service.WorkpieceEditorStorage", side_effect=lambda **kwargs: SimpleNamespace(**kwargs)),
            patch("src.applications.workpiece_editor.service.workpiece_editor_service.WorkpieceEditorServices", side_effect=lambda **kwargs: SimpleNamespace(**kwargs)),
            patch(
                "src.applications.workpiece_editor.service.workpiece_editor_service.WorkpieceEditorService",
                side_effect=lambda **kwargs: SimpleNamespace(
                    set_editing=MagicMock(),
                    get_workpiece_data_adapter=MagicMock(),
                    **kwargs,
                ),
            ),
            patch("src.applications.workpiece_editor.workpiece_editor_factory.WorkpieceEditorFactory") as factory_cls,
            patch("src.robot_systems.glue.application_wiring._build_capture_snapshot_service", return_value="snapshot"),
            patch("src.applications.base.robot_jog_service_builder.build_robot_system_jog_service", return_value="jog"),
        ):
            factory_cls.return_value.build.return_value = "widget"
            app = application_wiring._build_workpiece_editor_application(robot_system)
            app.register("broker")
            app.create_widget()

        kwargs = prep_cls.call_args.kwargs
        self.assertIsNone(kwargs["resolver"])
        self.assertIs(kwargs["resolver_getter"](), resolver)


if __name__ == "__main__":
    unittest.main()
