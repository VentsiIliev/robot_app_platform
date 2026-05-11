from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.engine.common_service_ids import CommonServiceID
from src.engine.robot.targeting import (
    RemoteTcpDefinition,
    RemoteTcpSettings,
    TargetFrameDefinition,
    TargetFrameSettings,
    TargetingSettings,
)
from src.robot_systems.paint import PaintRobotSystem
from src.robot_systems.paint.applications import PaintDashboardFactory as ApplicationsDashboardFactory
from src.robot_systems.paint.applications.dashboard import (
    PaintDashboardFactory as DashboardPackageFactory,
)
from src.robot_systems.paint.applications.dashboard.config import (
    PAINT_DASHBOARD_ACTIONS,
    PAINT_DASHBOARD_CARDS,
    PaintDashboardConfig,
)
from src.robot_systems.paint.applications.dashboard.dashboard_state import DashboardState
from src.robot_systems.paint.applications.dashboard.paint_dashboard_factory import (
    PaintDashboardFactory,
)
from src.robot_systems.paint.bootstrap_provider import PaintBootstrapProvider
from src.robot_systems.paint.calibration import PaintRobotSystemCalibrationProvider
from src.robot_systems.paint.component_ids import ProcessID, ServiceID, SettingsID
from src.robot_systems.paint.domain.contour_editor_schema import (
    build_paint_contour_form_schema,
    build_paint_layer_config,
    build_paint_segment_settings_schema,
)
from src.robot_systems.paint.domain.users import build_paint_user_schema
from src.robot_systems.paint.domain.workpieces.paint_workpiece_library_service import (
    PaintWorkpieceLibraryService,
    build_paint_workpiece_library_schema,
)
from src.robot_systems.paint.height_measuring import (
    PaintRobotSystemHeightMeasuringProvider,
)
from src.robot_systems.paint.height_measuring.mock_laser_control import MockLaserControl
from src.robot_systems.paint.service_builders import build_vacuum_pump_service
from src.robot_systems.paint.targeting import (
    PaintRobotSystemTargetingProvider,
    build_paint_point_registry,
    build_paint_target_frames,
)
from src.robot_systems.paint.targeting.settings_adapter import (
    from_editor_dict,
    to_editor_dict,
)


class TestPaintBootstrapProvider(unittest.TestCase):
    def test_system_class_and_robot_builder(self) -> None:
        provider = PaintBootstrapProvider()

        self.assertIs(provider.system_class, PaintRobotSystem)

        with patch(
            "src.robot_systems.paint.bootstrap_provider.FairinoRos2Robot",
            return_value="robot",
        ) as robot_cls:
            self.assertEqual(provider.build_robot(), "robot")

        robot_cls.assert_called_once_with(server_url="fake://local")

    def test_build_login_view_wires_auth_and_login_service(self) -> None:
        provider = PaintBootstrapProvider()
        robot_system = MagicMock()
        robot_system.__class__.role_policy = MagicMock(
            role_values=["admin", "operator"],
            admin_role_value="admin",
        )
        robot_system.users_storage_path.return_value = "/tmp/users.csv"
        robot_service = object()
        robot_system.get_optional_service.return_value = robot_service
        messaging = object()
        repo = object()
        auth_service = object()
        login_service = object()

        with patch(
            "src.robot_systems.paint.bootstrap_provider.build_paint_user_schema",
            return_value="schema",
        ) as build_schema, patch(
            "src.robot_systems.paint.bootstrap_provider.CsvUserRepository",
            return_value=repo,
        ) as repo_cls, patch(
            "src.robot_systems.paint.bootstrap_provider.AuthUserRepositoryAdapter",
            return_value="adapter",
        ) as adapter_cls, patch(
            "src.robot_systems.paint.bootstrap_provider.AuthenticationService",
            return_value=auth_service,
        ) as auth_cls, patch(
            "src.robot_systems.paint.bootstrap_provider.LoginApplicationService",
            return_value=login_service,
        ) as login_service_cls, patch(
            "src.robot_systems.paint.bootstrap_provider.LoginFactory.build",
            return_value="login-view",
        ) as build_view:
            result = provider.build_login_view(robot_system, messaging)

        self.assertEqual(result, "login-view")
        build_schema.assert_called_once_with(["admin", "operator"])
        repo_cls.assert_called_once_with("/tmp/users.csv", "schema")
        adapter_cls.assert_called_once_with(repo)
        auth_cls.assert_called_once_with("adapter")
        robot_system.get_optional_service.assert_called_once_with(CommonServiceID.ROBOT)
        login_service_cls.assert_called_once_with(
            auth_service=auth_service,
            user_repository=repo,
            robot_service=robot_service,
            admin_role_value="admin",
        )
        build_view.assert_called_once_with(login_service, messaging=messaging)

    def test_build_authorization_service_wires_permissions_repository(self) -> None:
        provider = PaintBootstrapProvider()
        robot_system = MagicMock()
        robot_system.__class__.role_policy = MagicMock(
            default_permission_role_values=["admin"],
            protected_app_role_values=["operator"],
        )
        robot_system.permissions_storage_path.return_value = "/tmp/permissions.json"
        permissions_repo = object()
        authorization_service = object()

        with patch(
            "src.robot_systems.paint.bootstrap_provider.JsonPermissionsRepository",
            return_value=permissions_repo,
        ) as repo_cls, patch(
            "src.robot_systems.paint.bootstrap_provider.AuthorizationService",
            return_value=authorization_service,
        ) as authz_cls:
            result = provider.build_authorization_service(robot_system)

        self.assertIs(result, authorization_service)
        repo_cls.assert_called_once_with(
            "/tmp/permissions.json",
            default_role_values=["admin"],
        )
        authz_cls.assert_called_once_with(
            permissions_repo,
            protected_app_role_values=["operator"],
        )


class TestPaintIdentifiersAndExports(unittest.TestCase):
    def test_component_ids_expose_expected_values(self) -> None:
        self.assertEqual(ServiceID.CUSTOM_DEVICE.value, "custom_device")
        self.assertEqual(ServiceID.VACUUM_PUMP.value, "vacuum_pump")
        self.assertEqual(ProcessID.MAIN_PROCESS.value, "main_process")
        self.assertEqual(ProcessID.ROBOT_CALIBRATION.value, "robot_calibration")
        self.assertEqual(list(SettingsID), [])

    def test_package_exports_are_stable(self) -> None:
        self.assertIs(ApplicationsDashboardFactory, PaintDashboardFactory)
        self.assertIs(DashboardPackageFactory, PaintDashboardFactory)
        self.assertIs(PaintRobotSystemCalibrationProvider, PaintRobotSystemCalibrationProvider)
        self.assertIs(PaintRobotSystemHeightMeasuringProvider, PaintRobotSystemHeightMeasuringProvider)
        self.assertIs(PaintRobotSystemTargetingProvider, PaintRobotSystemTargetingProvider)
        self.assertIs(build_paint_target_frames, build_paint_target_frames)
        self.assertIs(build_paint_point_registry, build_paint_point_registry)


class TestPaintServiceBuildersAndProviders(unittest.TestCase):
    def test_build_vacuum_pump_service_uses_repo_local_relay_client(self) -> None:
        with patch(
            "src.robot_systems.paint.domain.vacuum_pump.RelayVacuumPumpController",
            return_value="vacuum",
        ) as controller_cls:
            result = build_vacuum_pump_service(object())

        self.assertEqual(result, "vacuum")
        kwargs = controller_cls.call_args.kwargs
        self.assertTrue(kwargs["relay_client_path"].endswith("domain/vacuum_pump/relay_client.py"))
        self.assertEqual(kwargs["host"], "localhost")
        self.assertEqual(kwargs["port"], 5003)
        self.assertEqual(kwargs["output_num"], 0)

    def test_height_measuring_provider_builds_mock_laser(self) -> None:
        provider = PaintRobotSystemHeightMeasuringProvider(robot_system=object())

        laser = provider.build_laser_control()

        self.assertIsInstance(laser, MockLaserControl)
        self.assertFalse(laser.is_on)
        laser.turn_on()
        self.assertTrue(laser.is_on)
        laser.turn_off()
        self.assertFalse(laser.is_on)


class TestPaintDashboardSupport(unittest.TestCase):
    def test_dashboard_config_and_state_defaults(self) -> None:
        config = PaintDashboardConfig()
        state = DashboardState()

        self.assertFalse(config.show_placeholders)
        self.assertEqual(PAINT_DASHBOARD_CARDS[0].label, "Paint Process")
        self.assertEqual(PAINT_DASHBOARD_ACTIONS[0].action_id, "reset_errors")
        self.assertEqual(state.process_state, "idle")
        self.assertEqual(state.mode_label, "Paint Mode")
        self.assertEqual(state.active_job_label, "No active job")
        self.assertEqual(state.status_lines, [])
        self.assertTrue(state.can_start)
        self.assertFalse(state.can_stop)
        self.assertFalse(state.can_pause)
        self.assertEqual(state.pause_label, "Pause")

    def test_factory_build_sets_messaging_and_constructs_components(self) -> None:
        factory = PaintDashboardFactory()
        service = object()
        messaging = object()

        with patch(
            "src.robot_systems.paint.applications.dashboard.paint_dashboard_factory.PaintDashboardModel",
            return_value="model",
        ) as model_cls, patch(
            "src.robot_systems.paint.applications.dashboard.paint_dashboard_factory.PaintCardFactory"
        ) as card_factory_cls, patch(
            "src.robot_systems.paint.applications.dashboard.paint_dashboard_factory.PaintDashboardView",
            return_value="view",
        ) as view_cls, patch(
            "src.robot_systems.paint.applications.dashboard.paint_dashboard_factory.PaintDashboardController",
            return_value="controller",
        ) as controller_cls, patch(
            "src.robot_systems.paint.applications.dashboard.paint_dashboard_factory.ApplicationFactory.build",
            return_value="widget",
        ) as base_build:
            card_factory_cls.return_value.build_cards.return_value = ["card"]
            result = factory.build(service, messaging=messaging)

            model = factory._create_model(service)
            view = factory._create_view()
            controller = factory._create_controller(model, view)

        self.assertEqual(result, "widget")
        base_build.assert_called_once_with(service, messaging=messaging, jog_service=None)
        model_cls.assert_called_once_with(service)
        view_cls.assert_called_once()
        self.assertIsInstance(view_cls.call_args.kwargs["config"], PaintDashboardConfig)
        self.assertEqual(view_cls.call_args.kwargs["action_buttons"], PAINT_DASHBOARD_ACTIONS)
        self.assertEqual(view_cls.call_args.kwargs["cards"], ["card"])
        controller_cls.assert_called_once_with("model", "view", messaging)
        self.assertEqual(model, "model")
        self.assertEqual(view, "view")
        self.assertEqual(controller, "controller")


class TestPaintSchemasAndLibraryService(unittest.TestCase):
    def test_contour_editor_schema_defines_expected_fields(self) -> None:
        layer_config = build_paint_layer_config()
        form_schema = build_paint_contour_form_schema()
        segment_schema = build_paint_segment_settings_schema()

        self.assertEqual(layer_config.default_segment_role, "workpiece")
        self.assertEqual(set(layer_config.roles), {"workpiece", "contour", "fill"})
        self.assertEqual(form_schema.id_key, "workpieceId")
        self.assertEqual([field.key for field in form_schema.fields], ["workpieceId", "name", "description", "height_mm", "dxfPath"])
        self.assertEqual(form_schema.fields[3].default_value, 0.0)
        self.assertEqual(segment_schema.combo_key, "")
        self.assertEqual([field.key for field in segment_schema.fields[:3]], ["velocity", "acceleration", "rz_angle"])

    def test_user_schema_uses_role_values_in_combo_field(self) -> None:
        schema = build_paint_user_schema(["admin", "operator"])

        self.assertEqual(schema.id_key, "id")
        self.assertEqual([field.key for field in schema.fields], ["id", "firstName", "lastName", "password", "role", "email"])
        self.assertEqual(schema.fields[4].options, ["admin", "operator"])
        self.assertTrue(schema.fields[3].mask_in_table)

    def test_workpiece_library_service_maps_records_and_updates(self) -> None:
        backing_service = MagicMock()
        backing_service.list_all.return_value = [
            {"id": "storage-1", "name": "Meta Name", "date": "2026-05-06"},
        ]
        backing_service.load_raw.return_value = {
            "workpieceId": "wp-1",
            "name": "Stored Name",
            "dxfPath": "/tmp/a.dxf",
            "description": "desc",
        }
        backing_service.update.return_value = (True, "updated")
        backing_service.delete.return_value = (True, "deleted")
        backing_service.get_thumbnail_bytes.return_value = b"img"
        service = PaintWorkpieceLibraryService(backing_service)

        schema = build_paint_workpiece_library_schema()
        records = service.list_all()
        updated = service.update("storage-1", {"name": "New"})

        self.assertEqual(service.get_schema().id_key, schema.id_key)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].get("id"), "storage-1")
        self.assertEqual(records[0].get("workpieceId"), "wp-1")
        self.assertEqual(records[0].get("name"), "Stored Name")
        self.assertEqual(records[0].get("dxfPath"), "/tmp/a.dxf")
        self.assertEqual(updated, (True, "updated"))
        backing_service.update.assert_called_once_with(
            "storage-1",
            {
                "workpieceId": "wp-1",
                "name": "New",
                "dxfPath": "/tmp/a.dxf",
                "description": "desc",
            },
        )
        self.assertEqual(service.delete("storage-1"), (True, "deleted"))
        self.assertEqual(service.get_thumbnail("storage-1"), b"img")

    def test_workpiece_library_update_reports_missing_workpiece(self) -> None:
        backing_service = MagicMock()
        backing_service.load_raw.return_value = None
        service = PaintWorkpieceLibraryService(backing_service)

        ok, message = service.update("missing", {"name": "x"})

        self.assertFalse(ok)
        self.assertEqual(message, "Workpiece 'missing' not found")


class TestPaintTargetingSettingsAdapter(unittest.TestCase):
    def test_to_editor_dict_merges_declared_and_persisted_items(self) -> None:
        settings = TargetingSettings(
            points=[
                RemoteTcpSettings(name="tool", display_name="Persisted Tool", x_mm=1.5, y_mm=2.5),
                RemoteTcpSettings(name="extra", display_name="Extra", x_mm=5.0, y_mm=6.0),
            ],
            frames=[
                TargetFrameSettings(
                    name="frame-a",
                    source_navigation_group="src-persisted",
                    target_navigation_group="dst-persisted",
                    use_height_correction=True,
                    work_area_id="spray",
                ),
                TargetFrameSettings(
                    name="frame-extra",
                    source_navigation_group="s2",
                    target_navigation_group="t2",
                    use_height_correction=False,
                ),
            ],
        )

        result = to_editor_dict(
            settings,
            point_definitions=[RemoteTcpDefinition(name="tool", display_name="Tool")],
            frame_definitions=[
                TargetFrameDefinition(
                    name="frame-a",
                    source_navigation_group="src",
                    target_navigation_group="dst",
                    use_height_correction=False,
                )
            ],
        )

        self.assertEqual(result["protected_points"], ["tool"])
        self.assertEqual(result["protected_frames"], ["frame-a"])
        self.assertEqual(result["points"][0]["display_name"], "Persisted Tool")
        self.assertEqual(result["points"][0]["x_mm"], 1.5)
        self.assertEqual(result["points"][1]["name"], "extra")
        self.assertEqual(result["frames"][0]["source_navigation_group"], "src-persisted")
        self.assertTrue(result["frames"][0]["use_height_correction"])
        self.assertEqual(result["frames"][1]["name"], "frame-extra")

    def test_from_editor_dict_restores_declared_items_and_preserves_base_work_area(self) -> None:
        base = TargetingSettings(
            frames=[
                TargetFrameSettings(
                    name="frame-a",
                    source_navigation_group="base-src",
                    target_navigation_group="base-dst",
                    use_height_correction=False,
                    work_area_id="spray",
                )
            ]
        )
        result = from_editor_dict(
            data={
                "points": [
                    {"name": "extra", "display_name": "Extra", "x_mm": 7, "y_mm": 8},
                    {"name": "tool", "display_name": "Tool", "x_mm": 1, "y_mm": 2},
                ],
                "frames": [
                    {
                        "name": "frame-extra",
                        "source_navigation_group": "sx",
                        "target_navigation_group": "tx",
                        "use_height_correction": False,
                    },
                    {
                        "name": "frame-a",
                        "source_navigation_group": "src",
                        "target_navigation_group": "dst",
                        "use_height_correction": True,
                    },
                ],
            },
            base=base,
            point_definitions=[RemoteTcpDefinition(name="tool", display_name="Tool Declared")],
            frame_definitions=[
                TargetFrameDefinition(
                    name="frame-a",
                    work_area_id="spray",
                    source_navigation_group="decl-src",
                    target_navigation_group="decl-dst",
                    use_height_correction=False,
                )
            ],
        )

        self.assertEqual([point.name for point in result.points], ["extra", "tool"])
        self.assertEqual(result.points[0].x_mm, 7.0)
        self.assertEqual(result.points[1].display_name, "Tool")
        self.assertEqual([frame.name for frame in result.frames], ["frame-extra", "frame-a"])
        self.assertEqual(result.frames[0].source_navigation_group, "sx")
        self.assertEqual(result.frames[1].source_navigation_group, "src")
        self.assertTrue(result.frames[1].use_height_correction)
        self.assertEqual(result.frames[1].work_area_id, "spray")


if __name__ == "__main__":
    unittest.main()
