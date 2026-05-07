import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.engine.common_service_ids import CommonServiceID
from src.engine.common_settings_ids import CommonSettingsID
from src.robot_systems.paint import application_wiring
from src.robot_systems.paint.component_ids import ServiceID
from src.robot_systems.paint.paint_robot_system import PaintRobotSystem


class TestPaintApplicationWiring(unittest.TestCase):

    def test_build_dashboard_application_passes_dashboard_service_and_messaging(self):
        robot_system = SimpleNamespace(_dashboard_service=object())
        messaging = object()
        built_widget = object()
        factory = MagicMock()
        factory.build.return_value = built_widget

        with patch("src.robot_systems.paint.applications.dashboard.PaintDashboardFactory", return_value=factory):
            app = application_wiring._build_dashboard_application(robot_system)
            app.register(messaging)
            widget = app.create_widget()

        self.assertIs(widget, built_widget)
        factory.build.assert_called_once_with(robot_system._dashboard_service, messaging=messaging)

    def test_build_paint_path_preparation_service_wires_vision_robot_and_navigation_context(self):
        transformer = object()
        resolver = object()
        robot_config = SimpleNamespace(
            safety_limits=SimpleNamespace(z_min=123.0),
            camera_z_shift_x_per_mm_px=1.5,
            camera_z_shift_y_per_mm_px=-2.0,
        )
        navigation = MagicMock()
        navigation.get_group_position.return_value = [1, 2, 3, 4, 5, 6]
        robot_system = SimpleNamespace(
            _robot_config=robot_config,
            _navigation=navigation,
            get_shared_vision_resolver=MagicMock(return_value=(transformer, resolver)),
            get_target_frame_for_work_area=MagicMock(return_value=SimpleNamespace(name="paint_frame")),
            get_target_point_definition=MagicMock(return_value=SimpleNamespace(name="tool_point")),
        )
        built_service = object()

        with (
            patch("src.engine.robot.path_preparation.DefaultWorkpiecePathPreparationService", return_value=built_service) as cls,
            patch("src.robot_systems.paint.domain.contour_editor_schema.build_paint_segment_settings_schema", return_value="schema"),
            patch("src.applications.workpiece_editor.editor_core.config.SegmentEditorConfig", side_effect=lambda schema: SimpleNamespace(schema=schema)),
        ):
            result = application_wiring._build_paint_path_preparation_service(robot_system)

        self.assertIs(result, built_service)
        kwargs = cls.call_args.kwargs
        self.assertIs(kwargs["transformer"], transformer)
        self.assertIs(kwargs["resolver"], resolver)
        self.assertEqual(123.0, kwargs["z_min"])
        self.assertEqual("path_tangent", kwargs["rz_mode"])
        self.assertTrue(kwargs["execute_from_workpiece_layer"])
        self.assertEqual("paint_frame", kwargs["calibration_frame_name"])
        self.assertEqual(application_wiring._get_paint_execution_target_point_name(robot_system), kwargs["target_point_name"])
        self.assertEqual(application_wiring._get_paint_execution_target_point_name(robot_system), kwargs["pickup_target_point_name"])
        expected_compensation = (
            (15.0, -20.0)
            if application_wiring._PAINT_PROCESS.enable_z_shift_pixel_compensation
            else (0.0, 0.0)
        )
        self.assertEqual(expected_compensation, kwargs["pixel_height_compensation_fn"](10.0))
        self.assertEqual([1, 2, 3, 4, 5, 6], kwargs["base_position_provider"]())
        navigation.get_group_position.assert_called_once()

    def test_build_paint_path_preparation_service_falls_back_when_robot_config_values_are_unusable(self):
        robot_system = SimpleNamespace(
            _robot_config=SimpleNamespace(safety_limits=SimpleNamespace(z_min="bad")),
            _navigation=None,
            get_shared_vision_resolver=MagicMock(return_value=("transformer", "resolver")),
            get_target_frame_for_work_area=MagicMock(return_value=SimpleNamespace(name="")),
            get_target_point_definition=MagicMock(return_value=SimpleNamespace(name="tool_point")),
        )

        with (
            patch("src.engine.robot.path_preparation.DefaultWorkpiecePathPreparationService", return_value="service") as cls,
            patch("src.robot_systems.paint.domain.contour_editor_schema.build_paint_segment_settings_schema", return_value="schema"),
            patch("src.applications.workpiece_editor.editor_core.config.SegmentEditorConfig", side_effect=lambda schema: SimpleNamespace(schema=schema)),
        ):
            service = application_wiring._build_paint_path_preparation_service(robot_system)

        self.assertEqual(service, "service")
        kwargs = cls.call_args.kwargs
        self.assertEqual(kwargs["z_min"], 0.0)
        self.assertEqual(kwargs["calibration_frame_name"], "calibration")
        self.assertIsNone(kwargs["base_position_provider"]())
        if application_wiring._PAINT_PROCESS.enable_z_shift_pixel_compensation:
            self.assertEqual(kwargs["pixel_height_compensation_fn"](2.0), (0.0, 0.0))

    def test_build_paint_path_executor_wires_runtime_callbacks_and_robot_config(self):
        path_preparation_service = object()
        robot_service = object()
        navigation = MagicMock()
        navigation.get_group_position.side_effect = (
            lambda group: [group, "pose"]
        )
        navigation.move_to_calibration_position.return_value = True
        settings_service = MagicMock()
        settings_service.get.return_value = "live_robot_config"
        robot_config = SimpleNamespace(
            robot_tool=7,
            robot_user=9,
            camera_to_tcp_x_offset=1.25,
            camera_to_tcp_y_offset=-3.5,
        )
        robot_system = SimpleNamespace(
            _robot_config=robot_config,
            _navigation=navigation,
            _settings_service=settings_service,
            _vacuum_pump="pump",
            get_optional_service=MagicMock(return_value=robot_service),
        )
        built_executor = object()

        with (
            patch("src.robot_systems.paint.processes.paint.execute.PaintWorkpiecePathExecutor", return_value=built_executor) as cls,
            patch("src.robot_systems.paint.application_wiring._build_paint_path_preparation_service", return_value=path_preparation_service),
            patch("src.robot_systems.paint.application_wiring._build_paint_path_debug_dump_dir", return_value="/tmp/paint_debug"),
        ):
            result = application_wiring._build_paint_path_executor(robot_system)

        self.assertIs(result, built_executor)
        kwargs = cls.call_args.kwargs
        self.assertIs(kwargs["robot_service"], robot_service)
        self.assertIs(kwargs["path_preparation_service"], path_preparation_service)
        self.assertEqual(7, kwargs["pickup_tool"])
        self.assertEqual(9, kwargs["pickup_user"])
        self.assertEqual("/tmp/paint_debug", kwargs["debug_dump_dir"])
        self.assertEqual(1.25, kwargs["camera_to_tcp_x_offset"])
        self.assertEqual(-3.5, kwargs["camera_to_tcp_y_offset"])
        self.assertEqual("pump", kwargs["vacuum_pump"])
        self.assertEqual("live_robot_config", kwargs["robot_config_provider"]())
        self.assertTrue(kwargs["post_execute_callback"]())
        self.assertEqual([application_wiring._get_pickup_base_group_id(), "pose"], kwargs["pickup_base_position_provider"]())
        self.assertEqual([application_wiring._get_paint_base_group_id(), "pose"], kwargs["base_position_provider"]())

    def test_build_paint_contour_editor_application_registers_form_behavior_and_factory(self):
        robot_system = SimpleNamespace()
        service = MagicMock(prepare_dxf_test_raw_for_image=MagicMock())
        messaging = object()
        built_widget = object()
        behavior_provider = MagicMock()
        factory = MagicMock()
        factory.build.return_value = built_widget

        with (
            patch("src.robot_systems.paint.application_wiring._build_paint_workpiece_editor_service", return_value=service),
            patch("contour_editor.AdditionalFormBehaviorProvider.get", return_value=behavior_provider),
            patch("src.robot_systems.paint.domain.dxf_path_form_behavior.PaintDxfPathFormBehavior", return_value="behavior") as behavior_cls,
            patch("src.applications.base.robot_jog_service_builder.build_robot_system_jog_service", return_value="jog"),
            patch("src.applications.workpiece_editor.workpiece_editor_factory.WorkpieceEditorFactory", return_value=factory),
        ):
            app = application_wiring._build_paint_contour_editor_application(robot_system)
            app.register(messaging)
            widget = app.create_widget()

        self.assertIs(widget, built_widget)
        behavior_provider.set_behaviors.assert_called_once_with(["behavior"])
        behavior_cls.assert_called_once()
        factory.build.assert_called_once_with(service, messaging=messaging, jog_service="jog")

    def test_build_workpiece_library_application_wires_repository_service_and_factory(self):
        robot_system = SimpleNamespace(workpieces_storage_path=MagicMock(return_value="/tmp/workpieces"))
        messaging = object()
        built_widget = object()
        repository = object()
        workpiece_service = object()
        library_service = object()
        factory = MagicMock()
        factory.build.return_value = built_widget

        with (
            patch("src.robot_systems.paint.domain.workpieces.JsonPaintWorkpieceRepository", return_value=repository) as repo_cls,
            patch("src.robot_systems.paint.domain.workpieces.PaintWorkpieceService", return_value=workpiece_service) as svc_cls,
            patch("src.robot_systems.paint.domain.workpieces.PaintWorkpieceLibraryService", return_value=library_service) as lib_cls,
            patch("src.applications.base.robot_jog_service_builder.build_robot_system_jog_service", return_value="jog"),
            patch("src.applications.workpiece_library.workpiece_library_factory.WorkpieceLibraryFactory", return_value=factory),
        ):
            app = application_wiring._build_workpiece_library_application(robot_system)
            app.register(messaging)
            widget = app.create_widget()

        self.assertIs(widget, built_widget)
        repo_cls.assert_called_once_with("/tmp/workpieces")
        svc_cls.assert_called_once_with(repository)
        lib_cls.assert_called_once_with(workpiece_service)
        factory.build.assert_called_once_with(library_service, messaging, jog_service="jog")

    def test_build_user_management_application_wires_roles_permissions_and_factory(self):
        role_policy = SimpleNamespace(
            role_values=["admin", "operator"],
            default_permission_role_values=["admin"],
            protected_app_role_values=["operator"],
        )
        robot_system = type("RobotSystem", (), {"role_policy": role_policy})()
        robot_system.users_storage_path = MagicMock(return_value="/tmp/users.csv")
        robot_system.permissions_storage_path = MagicMock(return_value="/tmp/permissions.json")
        robot_system.shell = SimpleNamespace(applications=[SimpleNamespace(app_id="a"), SimpleNamespace(app_id="b")])
        messaging = object()
        built_widget = object()
        user_repo = object()
        service = object()
        perm_repo = object()
        perm_svc = object()
        factory = MagicMock()
        factory.build.return_value = built_widget

        with (
            patch("src.robot_systems.paint.domain.users.build_paint_user_schema", return_value="schema") as schema_builder,
            patch("src.applications.user_management.domain.csv_user_repository.CsvUserRepository", return_value=user_repo) as repo_cls,
            patch("src.applications.user_management.service.user_management_application_service.UserManagementApplicationService", return_value=service) as service_cls,
            patch("src.engine.auth.json_permissions_repository.JsonPermissionsRepository", return_value=perm_repo) as perm_repo_cls,
            patch("src.engine.auth.authorization_service.AuthorizationService", return_value=perm_svc) as authz_cls,
            patch("src.applications.base.robot_jog_service_builder.build_robot_system_jog_service", return_value="jog"),
            patch("src.applications.user_management.user_management_factory.UserManagementFactory", return_value=factory),
        ):
            app = application_wiring._build_user_management_application(robot_system)
            app.register(messaging)
            widget = app.create_widget()

        self.assertIs(widget, built_widget)
        schema_builder.assert_called_once_with(["admin", "operator"])
        repo_cls.assert_called_once_with("/tmp/users.csv", "schema")
        service_cls.assert_called_once_with(user_repo)
        perm_repo_cls.assert_called_once_with("/tmp/permissions.json", default_role_values=["admin"])
        authz_cls.assert_called_once_with(perm_repo, protected_app_role_values=["operator"])
        factory.build.assert_called_once_with(
            service,
            perm_svc,
            ["a", "b"],
            role_values=["admin", "operator"],
            default_role_values=["admin"],
            messaging=messaging,
            jog_service="jog",
        )

    def test_build_camera_and_calibration_settings_applications_wire_expected_services(self):
        robot_system = SimpleNamespace(
            _settings_service="settings",
            get_optional_service=MagicMock(return_value="vision"),
            get_service=MagicMock(return_value="work_areas"),
            get_work_area_definitions=MagicMock(return_value=["area"]),
        )
        messaging = object()
        camera_factory = MagicMock()
        camera_factory.build.return_value = "camera-widget"
        calibration_factory = MagicMock()
        calibration_factory.build.return_value = "calibration-widget"
        work_area_factory = MagicMock()
        work_area_factory.build.return_value = "work-area-widget"

        with (
            patch("src.applications.camera_settings.service.camera_settings_application_service.CameraSettingsApplicationService", return_value="camera-service") as camera_service_cls,
            patch("src.applications.camera_settings.camera_settings_factory.CameraSettingsFactory", return_value=camera_factory),
            patch("src.applications.calibration_settings.CalibrationSettingsApplicationService", return_value="calibration-service") as calibration_service_cls,
            patch("src.applications.calibration_settings.CalibrationSettingsFactory", return_value=calibration_factory),
            patch("src.applications.work_area_settings.service.work_area_settings_application_service.WorkAreaSettingsApplicationService", return_value="work-area-service") as work_area_service_cls,
            patch("src.applications.work_area_settings.work_area_settings_factory.WorkAreaSettingsFactory", return_value=work_area_factory) as work_area_factory_cls,
            patch("src.applications.base.robot_jog_service_builder.build_robot_system_jog_service", return_value="jog"),
        ):
            camera_app = application_wiring._build_camera_settings_application(robot_system)
            camera_app.register(messaging)
            self.assertEqual(camera_app.create_widget(), "camera-widget")

            calibration_app = application_wiring._build_calibration_settings_application(robot_system)
            calibration_app.register(messaging)
            self.assertEqual(calibration_app.create_widget(), "calibration-widget")

            work_area_app = application_wiring._build_work_area_settings_application(robot_system)
            work_area_app.register(messaging)
            self.assertEqual(work_area_app.create_widget(), "work-area-widget")

        camera_service_cls.assert_called_once_with(settings_service="settings", vision_service="vision")
        camera_factory.build.assert_called_once_with("camera-service", messaging, jog_service="jog")
        calibration_service_cls.assert_called_once_with("settings")
        calibration_factory.build.assert_called_once_with("calibration-service", messaging=messaging, jog_service="jog")
        work_area_service_cls.assert_called_once_with(work_area_service="work_areas", vision_service="vision")
        work_area_factory_cls.assert_called_once_with(work_area_definitions=["area"])
        work_area_factory.build.assert_called_once_with("work-area-service", messaging=messaging, jog_service="jog")

    def test_build_broker_debug_and_intrinsic_capture_applications_wire_factories(self):
        robot_system = SimpleNamespace(
            get_optional_service=MagicMock(side_effect=lambda key: {"robot": "robot", "vision": "vision"}.get(getattr(key, "value", key), None)),
            _robot_config="robot-config",
            _settings_service="settings",
            _messaging_service="robot-messaging",
            storage_path=MagicMock(return_value="/tmp/intrinsic"),
        )
        messaging = object()
        broker_factory = MagicMock()
        broker_factory.build.return_value = "broker-widget"
        intrinsic_factory = MagicMock()
        intrinsic_factory.build.return_value = "intrinsic-widget"

        with (
            patch("src.applications.base.robot_jog_service_builder.build_robot_system_jog_service", return_value="jog"),
            patch("src.applications.broker_debug.service.broker_debug_application_service.BrokerDebugApplicationService", return_value="broker-service") as broker_service_cls,
            patch("src.applications.broker_debug.broker_debug_factory.BrokerDebugFactory", return_value=broker_factory),
            patch("src.applications.intrinsic_calibration_capture.service.intrinsic_capture_service.IntrinsicCaptureService", return_value="intrinsic-service") as intrinsic_service_cls,
            patch("src.applications.intrinsic_calibration_capture.intrinsic_capture_factory.IntrinsicCaptureFactory", return_value=intrinsic_factory),
        ):
            broker_app = application_wiring._build_broker_debug_application(robot_system)
            broker_app.register(messaging)
            self.assertEqual(broker_app.create_widget(), "broker-widget")

            intrinsic_app = application_wiring._build_intrinsic_capture_application(robot_system)
            intrinsic_app.register(messaging)
            self.assertEqual(intrinsic_app.create_widget(), "intrinsic-widget")

        broker_service_cls.assert_called_once_with(messaging)
        broker_factory.build.assert_called_once_with("broker-service", messaging=messaging, jog_service="jog")
        intrinsic_service_cls.assert_called_once_with(
            robot_service="robot",
            vision_service="vision",
            robot_config="robot-config",
            messaging="robot-messaging",
            default_output_dir="/tmp/intrinsic",
            settings_service="settings",
        )
        intrinsic_factory.build.assert_called_once_with("intrinsic-service", messaging=messaging)

    def test_build_hand_eye_and_pick_target_applications_wire_runtime_services(self):
        robot_system = SimpleNamespace(
            _robot_config="robot-config",
            _navigation="navigation",
            _height_measuring_service="height",
            get_optional_service=MagicMock(side_effect=lambda key: {"robot": "robot", "vision": "vision"}.get(getattr(key, "value", key), None)),
            get_shared_vision_resolver=MagicMock(return_value=("transformer", "resolver")),
            get_targeting_provider=MagicMock(return_value=SimpleNamespace(get_default_target_name=MagicMock(return_value="tool"))),
            get_target_frame_for_work_area=MagicMock(side_effect=lambda area: SimpleNamespace(name=f"{area}-frame")),
        )
        messaging = object()
        hand_eye_factory = MagicMock()
        hand_eye_factory.build.return_value = "hand-eye-widget"
        pick_target_factory = MagicMock()
        pick_target_factory.build.return_value = "pick-target-widget"
        pick_service = MagicMock(get_jog_reference_rz=MagicMock(return_value=12.0))

        with (
            patch("src.engine.vision.capture_snapshot_service.CaptureSnapshotService", return_value="snapshot-service") as snapshot_cls,
            patch("src.applications.hand_eye_calibration.service.hand_eye_service.HandEyeCalibrationService", return_value="hand-eye-service") as hand_eye_service_cls,
            patch("src.applications.hand_eye_calibration.hand_eye_calibration_factory.HandEyeCalibrationFactory", return_value=hand_eye_factory),
            patch("src.applications.pick_target.service.pick_target_application_service.PickTargetApplicationService", return_value=pick_service) as pick_service_cls,
            patch("src.applications.pick_target.pick_target_factory.PickTargetFactory", return_value=pick_target_factory),
            patch("src.applications.base.robot_jog_service_builder.build_robot_system_jog_service", return_value="jog"),
            patch("src.robot_systems.paint.application_wiring._build_capture_snapshot_service", return_value="capture-snapshot"),
        ):
            hand_eye_app = application_wiring._build_hand_eye_calibration_application(robot_system)
            hand_eye_app.register(messaging)
            self.assertEqual(hand_eye_app.create_widget(), "hand-eye-widget")

            pick_target_app = application_wiring._build_pick_target_application(robot_system)
            pick_target_app.register(messaging)
            self.assertEqual(pick_target_app.create_widget(), "pick-target-widget")

        snapshot_cls.assert_called_once_with(vision_service="vision", robot_service="robot")
        hand_eye_service_cls.assert_called_once_with(
            snapshot_service="snapshot-service",
            robot_service="robot",
            vision_service="vision",
            robot_config="robot-config",
            messaging=messaging,
        )
        hand_eye_factory.build.assert_called_once_with("hand-eye-service", messaging=messaging)
        pick_service_cls.assert_called_once_with(
            vision_service="vision",
            capture_snapshot_service="capture-snapshot",
            robot_service="robot",
            resolver="resolver",
            robot_config="robot-config",
            navigation="navigation",
            height_measuring="height",
            default_target_name="tool",
            calibration_frame_name="spray-frame",
            pickup_frame_name="pickup-frame",
        )
        pick_target_factory.build.assert_called_once_with(pick_service, messaging=messaging, jog_service="jog")

    def test_build_capture_snapshot_and_workpiece_services_wire_dependencies(self):
        robot_system = SimpleNamespace(
            get_optional_service=MagicMock(side_effect=lambda key: {"vision": "vision", "robot": "robot"}.get(getattr(key, "value", key))),
            workpieces_storage_path=MagicMock(return_value="/tmp/workpieces"),
        )

        with (
            patch("src.engine.vision.capture_snapshot_service.CaptureSnapshotService", return_value="snapshot-service") as snapshot_cls,
            patch("src.robot_systems.paint.domain.workpieces.JsonPaintWorkpieceRepository", return_value="repo") as repo_cls,
            patch("src.robot_systems.paint.domain.workpieces.PaintWorkpieceService", return_value="workpiece-service") as service_cls,
        ):
            snapshot_service = application_wiring._build_capture_snapshot_service(robot_system)
            workpiece_service = application_wiring._build_paint_workpiece_service(robot_system)

        self.assertEqual(snapshot_service, "snapshot-service")
        self.assertEqual(workpiece_service, "workpiece-service")
        snapshot_cls.assert_called_once_with(vision_service="vision", robot_service="robot")
        repo_cls.assert_called_once_with("/tmp/workpieces")
        service_cls.assert_called_once_with("repo")

    def test_small_application_wiring_helpers_cover_debug_dir_and_target_validation(self):
        robot_system = SimpleNamespace(get_target_point_definition=MagicMock(return_value=SimpleNamespace(name="")))

        with patch(
            "src.robot_systems.paint.application_wiring._PAINT_PROCESS",
            replace(application_wiring._PAINT_PROCESS, execution_target_point="camera"),
        ):
            self.assertEqual(application_wiring._get_paint_execution_target_point_name(robot_system), "camera")

        with patch(
            "src.robot_systems.paint.application_wiring._PAINT_PROCESS",
            replace(application_wiring._PAINT_PROCESS, execution_target_point="invalid"),
        ):
            with self.assertRaises(ValueError):
                application_wiring._get_paint_execution_target_point_name(robot_system)

        debug_dir = application_wiring._build_paint_path_debug_dump_dir()
        self.assertTrue(debug_dir.endswith("src/bootstrap/debug_plots"))

    def test_build_matching_and_preparation_services_wire_runtime_functions(self):
        workpiece_service = MagicMock()
        workpiece_service.list_all = MagicMock(name="list_all")
        workpiece_service.load_raw = MagicMock(name="load_raw")
        matching_service = MagicMock(
            can_match_saved_workpieces=MagicMock(name="can_match"),
            match_saved_workpieces=MagicMock(name="match"),
        )
        robot_system = SimpleNamespace(
            get_optional_service=MagicMock(side_effect=lambda key: {"vision": SimpleNamespace(run_matching=MagicMock(name="run_matching"))}.get(getattr(key, "value", key))),
            get_shared_vision_resolver=MagicMock(return_value=("transformer", "resolver")),
        )

        with (
            patch("src.robot_systems.paint.processes.paint.plan.PaintWorkpieceMatchingService", return_value="built-matching") as matching_cls,
            patch("src.robot_systems.paint.application_wiring._build_capture_snapshot_service", return_value="snapshot"),
        ):
            built_matching = application_wiring._build_paint_matching_service(
                robot_system,
                workpiece_service=workpiece_service,
            )

        with (
            patch("src.robot_systems.paint.processes.paint.plan.PaintWorkpiecePreparationService", return_value="built-preparation") as prep_cls,
            patch("src.robot_systems.paint.application_wiring._build_paint_matching_service", return_value=matching_service),
        ):
            built_preparation = application_wiring._build_paint_workpiece_preparation_service(robot_system)

        self.assertEqual(built_matching, "built-matching")
        self.assertEqual(built_preparation, "built-preparation")
        matching_cls.assert_called_once()
        matching_kwargs = matching_cls.call_args.kwargs
        self.assertIs(matching_kwargs["list_saved_workpieces_fn"], workpiece_service.list_all)
        self.assertIs(matching_kwargs["load_saved_workpiece_fn"], workpiece_service.load_raw)
        self.assertEqual(matching_kwargs["capture_snapshot_service"], "snapshot")
        self.assertIsNotNone(matching_kwargs["run_matching_fn"])
        prep_cls.assert_called_once_with(
            can_match_fn=matching_service.can_match_saved_workpieces,
            match_workpiece_fn=matching_service.match_saved_workpieces,
            transformer="transformer",
            dxf_alignment_strategy=application_wiring._PAINT_PROCESS.dxf_alignment_strategy,
            dxf_max_scale_deviation=application_wiring._PAINT_PROCESS.dxf_max_scale_deviation,
        )

    def test_build_workpiece_editor_service_wires_storage_services_and_options(self):
        workpiece_service = MagicMock()
        workpiece_service.save.return_value = (True, "saved")
        workpiece_service.update.return_value = (True, "updated")
        workpiece_service.workpiece_id_exists.return_value = True
        robot_system = SimpleNamespace(
            _settings_service="settings",
            get_optional_service=MagicMock(side_effect=lambda key: {"vision": "vision", "robot": "robot"}.get(getattr(key, "value", key))),
            get_shared_vision_resolver=MagicMock(return_value=("transformer", "resolver")),
        )

        with (
            patch("src.robot_systems.paint.application_wiring._build_capture_snapshot_service", return_value="snapshot"),
            patch("src.robot_systems.paint.application_wiring._build_paint_workpiece_service", return_value=workpiece_service),
            patch("src.robot_systems.paint.application_wiring._build_paint_matching_service", return_value="matching"),
            patch("src.robot_systems.paint.application_wiring._build_paint_path_preparation_service", return_value="path-prep"),
            patch("src.robot_systems.paint.application_wiring._build_paint_path_executor", return_value="path-executor"),
            patch("src.robot_systems.paint.application_wiring._build_paint_path_debug_dump_dir", return_value="/tmp/debug"),
            patch("src.robot_systems.paint.domain.contour_editor_schema.build_paint_segment_settings_schema", return_value="segment-schema"),
            patch("src.robot_systems.paint.domain.contour_editor_schema.build_paint_contour_form_schema", return_value="form-schema"),
            patch("src.applications.workpiece_editor.editor_core.config.SegmentEditorConfig", side_effect=lambda schema: SimpleNamespace(schema=schema)),
            patch("src.applications.workpiece_editor.service.workpiece_editor_service.WorkpieceEditorStorage", side_effect=lambda **kwargs: SimpleNamespace(**kwargs)) as storage_cls,
            patch("src.applications.workpiece_editor.service.workpiece_editor_service.WorkpieceEditorServices", side_effect=lambda **kwargs: SimpleNamespace(**kwargs)) as services_cls,
            patch("src.applications.workpiece_editor.service.workpiece_editor_service.WorkpieceEditorOptions", side_effect=lambda **kwargs: SimpleNamespace(**kwargs)) as options_cls,
            patch("src.applications.workpiece_editor.service.workpiece_editor_service.WorkpieceEditorService", side_effect=lambda **kwargs: SimpleNamespace(**kwargs)) as service_cls,
        ):
            service = application_wiring._build_paint_workpiece_editor_service(robot_system)

        self.assertEqual(service.form_schema, "form-schema")
        self.assertEqual(service.segment_config.schema, "segment-schema")
        self.assertEqual(service.options.debug_dump_dir, "/tmp/debug")
        self.assertTrue(service.options.enable_dxf_import_test)
        self.assertEqual(service.services.vision_service, "vision")
        self.assertEqual(service.services.capture_snapshot_service, "snapshot")
        self.assertEqual(service.services.robot_service, "robot")
        self.assertEqual(service.services.transformer, "transformer")
        self.assertEqual(service.services.path_executor, "path-executor")
        self.assertEqual(service.services.path_preparation_service, "path-prep")
        self.assertEqual(service.services.matching_service, "matching")
        self.assertEqual(service.storage.save_fn({"id": "a"}), (True, "saved"))
        workpiece_service.save.assert_called_once_with({"id": "a"})
        self.assertEqual(service.storage.update_fn("a", {"id": "a"}), (True, "updated"))
        workpiece_service.update.assert_called_once_with("a", {"id": "a"})
        self.assertTrue(service.storage.id_exists_fn("a"))
        workpiece_service.workpiece_id_exists.assert_called_once_with("a")
        storage_cls.assert_called_once()
        services_cls.assert_called_once()
        options_cls.assert_called_once()
        service_cls.assert_called_once()

    def test_build_calibration_application_wires_optional_calibrators_and_observer_position(self):
        robot_config = SimpleNamespace(
            camera_to_tcp_x_offset=1.5,
            camera_to_tcp_y_offset=-2.5,
            robot_tool=7,
            robot_user=9,
        )
        work_area_service = MagicMock()
        robot_system = SimpleNamespace(
            _settings_service="settings",
            _robot_config=robot_config,
            _robot_calibration="robot-calibration",
            _calibration_coordinator="coordinator",
            _height_measuring_service="height",
            _height_measuring_calibration_service="height-calibration",
            _laser_detection_service="laser-ops",
            _messaging_service="system-messaging",
            _navigation=SimpleNamespace(get_group_position=MagicMock(return_value=["observer-pose"])),
            get_optional_service=MagicMock(side_effect=lambda key: {"vision": SimpleNamespace(camera_to_robot_matrix_path="/tmp/matrix"), "robot": "robot"}.get(getattr(key, "value", key))),
            get_service=MagicMock(side_effect=lambda key: {"work_areas": work_area_service, "navigation": "nav-service"}[getattr(key, "value", key)]),
            get_observer_group_for_area=MagicMock(return_value="observer-group"),
            get_work_area_definitions=MagicMock(return_value=["paint-area"]),
            storage_path=MagicMock(return_value="/tmp/intrinsic"),
        )
        messaging = object()
        built_widget = object()
        calibration_factory = MagicMock()
        calibration_factory.build.return_value = built_widget

        with (
            patch("src.engine.robot.calibration.calibration_navigation_service.CalibrationNavigationService", return_value="navigation-service") as nav_cls,
            patch("src.engine.vision.homography_residual_transformer.HomographyResidualTransformer", return_value="transformer") as transformer_cls,
            patch("src.engine.robot.calibration.camera_tcp_offset_calibration_service.CameraTcpOffsetCalibrationService", return_value="tcp-calibrator") as tcp_cls,
            patch("src.engine.robot.calibration.camera_z_shift_calibration_service.CameraZShiftCalibrationService", return_value="z-calibrator") as z_cls,
            patch("src.engine.robot.calibration.aruco_marker_height_mapping_service.ArucoMarkerHeightMappingService", return_value="marker-height") as marker_cls,
            patch("src.applications.intrinsic_calibration_capture.service.intrinsic_capture_service.IntrinsicCaptureService", return_value="intrinsic-service") as intrinsic_cls,
            patch("src.applications.calibration_settings.CalibrationSettingsApplicationService", return_value="calibration-settings") as calibration_settings_cls,
            patch("src.applications.calibration.service.calibration_application_service.CalibrationApplicationService", side_effect=lambda **kwargs: SimpleNamespace(**kwargs)) as calibration_service_cls,
            patch("src.applications.calibration.calibration_factory.CalibrationFactory", return_value=calibration_factory) as calibration_factory_cls,
            patch("src.applications.base.robot_jog_service_builder.build_robot_system_jog_service", return_value="jog"),
        ):
            app = application_wiring._build_calibration_application(robot_system)
            app.register(messaging)
            widget = app.create_widget()

        self.assertIs(widget, built_widget)
        nav_cls.assert_called_once()
        nav_cls.call_args.kwargs["before_move"]()
        work_area_service.set_active_area_id.assert_called_once_with("paint")
        transformer_cls.assert_called_once_with(
            "/tmp/matrix",
            camera_to_tcp_x_offset=1.5,
            camera_to_tcp_y_offset=-2.5,
        )
        tcp_cls.assert_called_once()
        z_cls.assert_called_once()
        marker_cls.assert_called_once()
        intrinsic_cls.assert_called_once_with(
            robot_service="robot",
            vision_service=robot_system.get_optional_service(CommonServiceID.VISION),
            robot_config=robot_config,
            messaging="system-messaging",
            default_output_dir="/tmp/intrinsic",
            settings_service="settings",
        )
        calibration_settings_cls.assert_called_once_with("settings")
        service = calibration_service_cls.call_args.args[0] if calibration_service_cls.call_args.args else calibration_service_cls.call_args.kwargs
        if isinstance(service, dict):
            observer_position_provider = service["observer_position_provider"]
            self.assertEqual(["observer-pose"], observer_position_provider("observer-group"))
        calibration_factory_cls.assert_called_once_with(work_area_definitions=["paint-area"])
        calibration_factory.build.assert_called_once()

    def test_build_robot_settings_application_wires_targeting_load_and_save(self):
        settings_service = MagicMock()
        settings_service.get.return_value = "existing-targeting"
        robot_app = SimpleNamespace(
            _settings_service=settings_service,
            _navigation="navigation",
            get_optional_service=MagicMock(return_value="robot"),
            get_service=MagicMock(return_value="nav-service"),
            get_target_point_definitions=MagicMock(return_value=["point"]),
            get_target_frame_definitions=MagicMock(return_value=["frame"]),
            get_movement_group_definitions=MagicMock(return_value=["group"]),
            invalidate_shared_vision_resolver=MagicMock(),
        )
        messaging = object()
        factory = MagicMock()
        factory.build.return_value = "robot-settings-widget"

        with (
            patch("src.robot_systems.paint.targeting.settings_adapter.to_editor_dict", return_value="editor-targeting") as to_editor_dict,
            patch("src.robot_systems.paint.targeting.settings_adapter.from_editor_dict", return_value="saved-targeting") as from_editor_dict,
            patch("src.applications.robot_settings.service.robot_settings_application_service.RobotSettingsApplicationService", side_effect=lambda *args, **kwargs: SimpleNamespace(args=args, kwargs=kwargs)) as service_cls,
            patch("src.applications.robot_settings.robot_settings_factory.RobotSettingsFactory", return_value=factory) as factory_cls,
            patch("src.applications.base.robot_jog_service_builder.build_robot_system_jog_service", return_value="jog"),
        ):
            app = application_wiring._build_robot_settings_application(robot_app)
            app.register(messaging)
            widget = app.create_widget()

        self.assertEqual(widget, "robot-settings-widget")
        service = service_cls.call_args.args[0] if service_cls.call_args.args else None
        kwargs = service_cls.call_args.kwargs
        self.assertIsNotNone(service)
        self.assertEqual(kwargs["navigation_service"], "navigation")
        self.assertEqual(kwargs["movement_group_definitions"], ["group"])
        self.assertEqual(kwargs["load_targeting_definitions_fn"](), "editor-targeting")
        to_editor_dict.assert_called_once_with("existing-targeting", ["point"], ["frame"])
        kwargs["save_targeting_definitions_fn"]("new-editor-data")
        from_editor_dict.assert_called_once_with("new-editor-data", "existing-targeting", ["point"], ["frame"])
        settings_service.save.assert_called_once_with(CommonSettingsID.TARGETING, "saved-targeting")
        robot_app.invalidate_shared_vision_resolver.assert_called_once_with()
        factory_cls.assert_called_once_with(movement_group_definitions=["group"])
        factory.build.assert_called_once()


class TestPaintRobotSystemStart(unittest.TestCase):

    def _make_system(self):
        system = PaintRobotSystem()
        system._messaging_service = MagicMock()
        system._system_manager = MagicMock()
        system._health_registry = SimpleNamespace(check=MagicMock(return_value=True))
        system.register_managed_resource = MagicMock(side_effect=lambda resource: resource)
        return system

    def _configure_service_access(self, system, *, vision):
        robot = MagicMock()
        navigation_engine = MagicMock()
        work_area_service = MagicMock()
        vacuum_pump = MagicMock()
        robot_config = SimpleNamespace()
        robot_calibration = SimpleNamespace()
        targeting = SimpleNamespace()

        services = {
            CommonServiceID.ROBOT: robot,
            CommonServiceID.NAVIGATION: navigation_engine,
            CommonServiceID.WORK_AREAS: work_area_service,
        }
        optional_services = {
            CommonServiceID.VISION: vision,
            ServiceID.VACUUM_PUMP: vacuum_pump,
        }
        settings = {
            CommonSettingsID.ROBOT_CONFIG: robot_config,
            CommonSettingsID.ROBOT_CALIBRATION: robot_calibration,
            CommonSettingsID.TARGETING: targeting,
        }

        system.get_service = MagicMock(side_effect=lambda name: services[name])
        system.get_optional_service = MagicMock(side_effect=lambda name: optional_services.get(name))
        system.get_settings = MagicMock(side_effect=lambda name: settings[name])
        return robot, navigation_engine, work_area_service, vacuum_pump

    def test_on_start_starts_and_registers_vision_when_present(self):
        system = self._make_system()
        vision = MagicMock()
        robot, navigation_engine, work_area_service, _vacuum_pump = self._configure_service_access(
            system,
            vision=vision,
        )
        navigation = MagicMock()
        calibration_process = MagicMock()
        main_process = MagicMock()
        dashboard_service = MagicMock()
        production_service = MagicMock()

        with (
            patch("src.robot_systems.paint.navigation.PaintNavigationService", return_value=navigation) as nav_cls,
            patch("src.robot_systems.paint.paint_robot_system.PaintRobotSystemTargetingProvider", return_value=MagicMock()),
            patch("src.robot_systems.paint.paint_robot_system.PaintRobotSystemHeightMeasuringProvider", return_value=MagicMock()),
            patch("src.robot_systems.paint.paint_robot_system.PaintRobotSystemCalibrationProvider", return_value=MagicMock()),
            patch("src.robot_systems.paint.paint_robot_system.build_robot_system_height_measuring_services", return_value=(MagicMock(), MagicMock(), MagicMock())),
            patch("src.robot_systems.paint.paint_robot_system.build_robot_system_calibration_service", return_value=MagicMock()),
            patch("src.engine.robot.calibration.robot_calibration_process.RobotCalibrationProcess", return_value=calibration_process),
            patch("src.robot_systems.paint.calibration.coordinator.PaintCalibrationCoordinator", return_value=MagicMock()),
            patch("src.robot_systems.paint.processes.paint.paint_production_service.PaintProductionService", return_value=production_service),
            patch("src.robot_systems.paint.processes.PaintProcess", return_value=main_process),
            patch("src.robot_systems.paint.applications.dashboard.service.paint_dashboard_service.PaintDashboardService", return_value=dashboard_service),
            patch("src.robot_systems.paint.application_wiring._build_paint_workpiece_editor_service", return_value=MagicMock()),
            patch("src.robot_systems.paint.application_wiring._build_capture_snapshot_service", return_value=MagicMock()),
            patch("src.robot_systems.paint.application_wiring._build_paint_path_preparation_service", return_value=MagicMock()),
            patch("src.robot_systems.paint.application_wiring._build_paint_path_executor", return_value=MagicMock()),
            patch("src.robot_systems.paint.application_wiring._build_paint_matching_service", return_value=MagicMock()),
            patch("src.robot_systems.paint.application_wiring._build_paint_workpiece_preparation_service", return_value=MagicMock()),
            patch("src.robot_systems.paint.application_wiring._build_paint_workpiece_service", return_value=MagicMock()),
        ):
            system.on_start()

        vision.start.assert_called_once_with()
        robot.enable_robot.assert_called_once_with()
        nav_cls.assert_called_once()
        self.assertEqual(nav_cls.call_args.kwargs["vision"], vision)
        self.assertEqual(nav_cls.call_args.kwargs["work_area_service"], work_area_service)
        self.assertEqual(nav_cls.call_args.kwargs["robot_service"], robot)
        self.assertEqual(
            nav_cls.call_args.kwargs["observed_area_by_group"],
            {"CALIBRATION": "paint"},
        )
        self.assertIs(system._navigation, navigation)
        self.assertIs(system._dashboard_service, dashboard_service)
        system.register_managed_resource.assert_any_call(vision)
        system.register_managed_resource.assert_any_call(calibration_process)
        system.register_managed_resource.assert_any_call(main_process)

    def test_on_start_skips_vision_start_when_optional_service_missing(self):
        system = self._make_system()
        robot, work_area_navigation, work_area_service, _vacuum_pump = self._configure_service_access(
            system,
            vision=None,
        )
        navigation = MagicMock()

        with (
            patch("src.robot_systems.paint.navigation.PaintNavigationService", return_value=navigation),
            patch("src.robot_systems.paint.paint_robot_system.PaintRobotSystemTargetingProvider", return_value=MagicMock()),
            patch("src.robot_systems.paint.paint_robot_system.PaintRobotSystemHeightMeasuringProvider", return_value=MagicMock()),
            patch("src.robot_systems.paint.paint_robot_system.PaintRobotSystemCalibrationProvider", return_value=MagicMock()),
            patch("src.robot_systems.paint.paint_robot_system.build_robot_system_height_measuring_services", return_value=(MagicMock(), MagicMock(), MagicMock())),
            patch("src.robot_systems.paint.paint_robot_system.build_robot_system_calibration_service", return_value=MagicMock()),
            patch("src.engine.robot.calibration.robot_calibration_process.RobotCalibrationProcess", return_value=MagicMock()),
            patch("src.robot_systems.paint.calibration.coordinator.PaintCalibrationCoordinator", return_value=MagicMock()),
            patch("src.robot_systems.paint.processes.paint.paint_production_service.PaintProductionService", return_value=MagicMock()),
            patch("src.robot_systems.paint.processes.PaintProcess", return_value=MagicMock()),
            patch("src.robot_systems.paint.applications.dashboard.service.paint_dashboard_service.PaintDashboardService", return_value=MagicMock()),
            patch("src.robot_systems.paint.application_wiring._build_paint_workpiece_editor_service", return_value=MagicMock()),
            patch("src.robot_systems.paint.application_wiring._build_capture_snapshot_service", return_value=MagicMock()),
            patch("src.robot_systems.paint.application_wiring._build_paint_path_preparation_service", return_value=MagicMock()),
            patch("src.robot_systems.paint.application_wiring._build_paint_path_executor", return_value=MagicMock()),
            patch("src.robot_systems.paint.application_wiring._build_paint_matching_service", return_value=MagicMock()),
            patch("src.robot_systems.paint.application_wiring._build_paint_workpiece_preparation_service", return_value=MagicMock()),
            patch("src.robot_systems.paint.application_wiring._build_paint_workpiece_service", return_value=MagicMock()),
        ):
            system.on_start()

        robot.enable_robot.assert_called_once_with()
        self.assertIsNone(system._vision)
        registered_resources = [call.args[0] for call in system.register_managed_resource.call_args_list]
        self.assertNotIn(None, registered_resources)
