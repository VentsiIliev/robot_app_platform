import unittest
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

