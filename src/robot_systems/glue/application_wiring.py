import logging

from src.engine.common_service_ids import CommonServiceID
from src.applications.workpiece_editor.editor_core.config import SegmentEditorConfig
from src.engine.common_settings_ids import CommonSettingsID
from src.engine.robot.configuration.robot_settings import SafetyLimits
from src.robot_systems.glue.domain.workpieces.schemas import build_glue_workpiece_form_schema, \
    build_glue_segment_settings_schema
from src.robot_systems.glue.component_ids import ServiceID
from src.robot_systems.glue.component_ids import SettingsID

_logger = logging.getLogger(__name__)


def _build_capture_snapshot_service(robot_system):
    from src.engine.vision.capture_snapshot_service import CaptureSnapshotService

    return CaptureSnapshotService(
        vision_service=robot_system.get_optional_service(CommonServiceID.VISION),
        robot_service=robot_system.get_optional_service(CommonServiceID.ROBOT),
    )


def _build_pick_and_place_visualizer(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.pick_and_place_visualizer import PickAndPlaceVisualizerFactory
    from src.applications.pick_and_place_visualizer.service.pick_and_place_visualizer_service import (
        PickAndPlaceVisualizerService,
    )
    from src.robot_systems.glue.domain.matching.matching_service import MatchingService
    from src.robot_systems.glue.domain.workpieces.repository.json_workpiece_repository import JsonWorkpieceRepository
    from src.robot_systems.glue.domain.workpieces.service.workpiece_service import WorkpieceService
    from src.robot_systems.glue.processes.pick_and_place.config import PickAndPlaceConfig

    vision_service = robot_system.get_optional_service(CommonServiceID.VISION)
    capture_snapshot_service = _build_capture_snapshot_service(robot_system)
    workpiece_service = WorkpieceService(JsonWorkpieceRepository(robot_system.workpieces_storage_path()))
    matching_service = MatchingService(
        vision_service=vision_service,
        workpiece_service=workpiece_service,
        capture_snapshot_service=capture_snapshot_service,
    )
    service = PickAndPlaceVisualizerService(
        matching_service=matching_service,
        config=PickAndPlaceConfig(),
        pick_and_place_process=robot_system.coordinator.pick_and_place_process,
    )
    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: PickAndPlaceVisualizerFactory().build(service, ms, jog_service=jog_service)
    )


def _build_contour_matching_tester(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.contour_matching_tester.contour_matching_tester_factory import ContourMatchingTesterFactory
    from src.applications.contour_matching_tester.service.contour_matching_tester_service import \
        ContourMatchingTesterService
    from src.robot_systems.glue.domain.workpieces.repository.json_workpiece_repository import JsonWorkpieceRepository
    from src.robot_systems.glue.domain.workpieces.service.workpiece_service import WorkpieceService

    workpiece_service = WorkpieceService(JsonWorkpieceRepository(robot_system.workpieces_storage_path()))
    vision_service = robot_system.get_optional_service(CommonServiceID.VISION)
    capture_snapshot_service = _build_capture_snapshot_service(robot_system)

    service = ContourMatchingTesterService(
        vision_service=vision_service,
        workpiece_service=workpiece_service,
        capture_snapshot_service=capture_snapshot_service,
    )
    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: ContourMatchingTesterFactory().build(service, ms, jog_service=jog_service)
    )


def _build_glue_process_driver_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.robot_systems.glue.applications.glue_process_driver import (
        GlueProcessDriverFactory,
        GlueProcessDriverService,
    )
    from src.robot_systems.glue.domain.glue_job_builder_service import GlueJobBuilderService
    from src.robot_systems.glue.domain.glue_job_execution_service import GlueJobExecutionService
    from src.robot_systems.glue.domain.matching.matching_service import MatchingService
    from src.robot_systems.glue.domain.workpieces.repository.json_workpiece_repository import JsonWorkpieceRepository
    from src.robot_systems.glue.domain.workpieces.service.workpiece_service import WorkpieceService

    workpiece_service = WorkpieceService(JsonWorkpieceRepository(robot_system.workpieces_storage_path()))
    vision_service = robot_system.get_optional_service(CommonServiceID.VISION)
    capture_snapshot_service = _build_capture_snapshot_service(robot_system)
    robot_config = getattr(robot_system, "_robot_config", None)
    tool_point_name = (
        getattr(robot_system.get_target_point_definition("tool"), "name", "") or ""
    )
    try:
        z_min = float(robot_config.safety_limits.z_min) if robot_config is not None else 0.0
    except Exception:
        z_min = 0.0
    base_transformer, resolver = robot_system.get_shared_vision_resolver()
    matching_service = MatchingService(
        vision_service=vision_service,
        workpiece_service=workpiece_service,
        capture_snapshot_service=capture_snapshot_service,
    )
    execution_service = GlueJobExecutionService(
        matching_service=matching_service,
        job_builder=GlueJobBuilderService(
            transformer=base_transformer,
            resolver=resolver,
            z_min=z_min,
            target_point_name=tool_point_name,
        ),
        glue_process=robot_system.coordinator.glue_process,
        navigation_service=robot_system.coordinator.glue_process.navigation_service,
        vision_service=vision_service,
        capture_snapshot_service=capture_snapshot_service,
        messaging_service=robot_system._messaging_service,
    )
    service = GlueProcessDriverService(
        matching_service=matching_service,
        job_builder=GlueJobBuilderService(
            transformer=base_transformer,
            resolver=resolver,
            z_min=z_min,
            target_point_name=tool_point_name,
        ),
        glue_process=robot_system.coordinator.glue_process,
        execution_service=execution_service,
    )
    return WidgetApplication(widget_factory=lambda ms: GlueProcessDriverFactory(ms).build(service))


def _get_tools(robot_system) -> list:
    tc = robot_system._settings_service.get(CommonSettingsID.TOOL_CHANGER_CONFIG)
    return tc.get_tool_options() if tc else []


def _build_tool_settings_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.tool_settings import (
        ToolSettingsFactory, ToolSettingsApplicationService,
    )
    service = ToolSettingsApplicationService(robot_system._settings_service)
    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: ToolSettingsFactory().build(service, messaging=ms, jog_service=jog_service)
    )


def _build_workpiece_library_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.workpiece_library.workpiece_library_factory import WorkpieceLibraryFactory
    from src.robot_systems.glue.domain.workpieces.glue_workpiece_library_service import GlueWorkpieceLibraryService
    from src.robot_systems.glue.domain.workpieces.repository.json_workpiece_repository import JsonWorkpieceRepository
    from src.robot_systems.glue.domain.workpieces.service.workpiece_service import WorkpieceService

    settings_service = robot_system._settings_service
    catalog = settings_service.get(SettingsID.GLUE_CATALOG)

    def _get_glue_types() -> list:
        return catalog.get_all_names() if hasattr(catalog, "get_all_names") else []

    repo = JsonWorkpieceRepository(robot_system.workpieces_storage_path())

    service = GlueWorkpieceLibraryService(
        WorkpieceService(repo),
        glue_types_fn=_get_glue_types,
        tools_fn=lambda: _get_tools(robot_system),
    )
    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: WorkpieceLibraryFactory().build(service, ms, jog_service=jog_service)
    )


def _build_workpiece_editor_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.workpiece_editor.workpiece_editor_factory import WorkpieceEditorFactory
    from src.applications.workpiece_editor.service.workpiece_editor_service import WorkpieceEditorService
    from src.robot_systems.glue.domain.workpieces.repository.json_workpiece_repository import JsonWorkpieceRepository
    from src.robot_systems.glue.domain.workpieces.service.workpiece_service import WorkpieceService
    from src.shared_contracts.events.workpiece_events import WorkpieceTopics

    settings_service = robot_system._settings_service
    vision_service = robot_system.get_optional_service(CommonServiceID.VISION)
    capture_snapshot_service = _build_capture_snapshot_service(robot_system)
    robot_config = robot_system._robot_config
    tool_point_name = (
        getattr(robot_system.get_target_point_definition("tool"), "name", "") or ""
    )

    base_transformer, resolver = robot_system.get_shared_vision_resolver()

    def _get_glue_types():
        catalog = settings_service.get(SettingsID.GLUE_CATALOG)
        return catalog.get_all_names() if hasattr(catalog, "get_all_names") else []

    def _get_tools():
        tc = settings_service.get(CommonSettingsID.TOOL_CHANGER_CONFIG)
        return tc.get_tool_options() if tc else []

    catalog = settings_service.get(SettingsID.GLUE_CATALOG)
    glue_types = catalog.get_all_names() if hasattr(catalog, "get_all_names") else []

    workpiece_service = WorkpieceService(JsonWorkpieceRepository(robot_system.workpieces_storage_path()), tool_provider=_get_tools)

    service = WorkpieceEditorService(
        vision_service=vision_service,
        capture_snapshot_service=capture_snapshot_service,
        save_fn=lambda data: workpiece_service.save(data),
        update_fn=lambda sid, data: workpiece_service.update(sid, data),
        form_schema=lambda: build_glue_workpiece_form_schema(  # ← lazy callable
            glue_types=_get_glue_types(),
            tools=_get_tools(),
        ),
        segment_config=SegmentEditorConfig(schema=build_glue_segment_settings_schema(_get_glue_types())),
        id_exists_fn=workpiece_service.workpiece_id_exists,
        transformer=base_transformer,
        resolver=resolver,
        z_min=float(robot_config.safety_limits.z_min) if robot_config is not None else float(SafetyLimits().z_min),
        robot_service=robot_system.get_optional_service(CommonServiceID.ROBOT),
        target_point_name=tool_point_name,
    )

    class _PendingLoader:
        def __init__(self):
            self.raw = None
            self.storage_id = None  # ← track which existing workpiece is being edited

        def on_open_requested(self, payload) -> None:
            # payload = {"raw": {...}, "storage_id": "2026-..."} OR just raw dict (legacy)
            if isinstance(payload, dict) and "storage_id" in payload:
                self.raw = payload["raw"]
                self.storage_id = payload["storage_id"]
            else:
                self.raw = payload
                self.storage_id = None

        def pop(self):
            raw, self.raw = self.raw, None
            sid, self.storage_id = self.storage_id, None
            return raw, sid

    pending = _PendingLoader()
    robot_system._messaging_service.subscribe(
        WorkpieceTopics.OPEN_IN_EDITOR, pending.on_open_requested
    )

    def _make_widget(ms):
        from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
        jog_service = build_robot_system_jog_service(robot_system)
        widget = WorkpieceEditorFactory().build(service, messaging=ms, jog_service=jog_service)
        raw, storage_id = pending.pop()
        if raw is not None:
            try:
                from src.applications.workpiece_editor.editor_core.adapters.workpiece_adapter import WorkpieceAdapter
                editor_data = WorkpieceAdapter.from_raw(raw)
                inner = widget._editor.contourEditor.editor_with_rulers.editor
                inner.workpiece_manager.load_editor_data(editor_data, close_contour=False)
                widget._editor.contourEditor.data = raw
                service.set_editing(storage_id)
            except Exception as exc:
                _logger.exception("Auto-load workpiece failed: %s", exc)
        else:
            service.set_editing(None)
        return widget

    return WidgetApplication(widget_factory=_make_widget)


def _build_user_management_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.user_management.user_management_factory import UserManagementFactory
    from src.applications.user_management.service.user_management_application_service import \
        UserManagementApplicationService
    from src.applications.user_management.domain.csv_user_repository import CsvUserRepository
    from src.engine.auth.json_permissions_repository import JsonPermissionsRepository
    from src.robot_systems.glue.domain.users import build_glue_user_schema
    from src.engine.auth.authorization_service import AuthorizationService

    role_policy = robot_system.__class__.role_policy
    service = UserManagementApplicationService(
        CsvUserRepository(
            robot_system.users_storage_path(),
            build_glue_user_schema(role_policy.role_values),
        )
    )
    perm_repo = JsonPermissionsRepository(
        robot_system.permissions_storage_path(),
        default_role_values=role_policy.default_permission_role_values,
    )
    perm_svc = AuthorizationService(
        perm_repo,
        protected_app_role_values=role_policy.protected_app_role_values,
    )
    known_ids = [spec.app_id for spec in robot_system.shell.applications]
    jog_service = build_robot_system_jog_service(robot_system)

    def _build(messaging_service):
        return UserManagementFactory().build(
            service,
            perm_svc,
            known_ids,
            role_values=role_policy.role_values,
            default_role_values=role_policy.default_permission_role_values,
            messaging=messaging_service,
            jog_service=jog_service,
        )

    return WidgetApplication(widget_factory=_build)


def _build_camera_settings_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.camera_settings.camera_settings_factory import CameraSettingsFactory
    from src.applications.camera_settings.service.camera_settings_application_service import \
        CameraSettingsApplicationService
    from src.robot_systems.glue.component_ids import ServiceID

    service = CameraSettingsApplicationService(
        settings_service=robot_system._settings_service,
        vision_service=robot_system.get_optional_service(CommonServiceID.VISION),
    )
    factory = CameraSettingsFactory()
    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: factory.build(
            service,
            ms,
            jog_service=jog_service,
        )
    )


def _build_calibration_settings_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.calibration_settings import (
        CalibrationSettingsApplicationService,
        CalibrationSettingsFactory,
    )

    service = CalibrationSettingsApplicationService(robot_system._settings_service)
    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: CalibrationSettingsFactory().build(
            service,
            messaging=ms,
            jog_service=jog_service,
        )
    )


def _build_work_area_settings_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.work_area_settings.work_area_settings_factory import WorkAreaSettingsFactory
    from src.applications.work_area_settings.service.work_area_settings_application_service import (
        WorkAreaSettingsApplicationService,
    )

    service = WorkAreaSettingsApplicationService(
        work_area_service=robot_system.get_service(CommonServiceID.WORK_AREAS),
        vision_service=robot_system.get_optional_service(CommonServiceID.VISION),
    )
    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: WorkAreaSettingsFactory(
            work_area_definitions=robot_system.get_work_area_definitions()
        ).build(service, messaging=ms, jog_service=jog_service)
    )


def _build_calibration_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.calibration.calibration_factory import CalibrationFactory
    from src.applications.calibration.service.calibration_application_service import CalibrationApplicationService
    from src.applications.calibration_settings import CalibrationSettingsApplicationService
    from src.applications.intrinsic_calibration_capture.service.intrinsic_capture_service import (
        IntrinsicCaptureService,
    )
    from src.engine.robot.calibration.aruco_marker_height_mapping_service import (
        ArucoMarkerHeightMappingService,
    )
    from src.engine.robot.calibration.camera_tcp_offset_calibration_service import (
        CameraTcpOffsetCalibrationService,
    )
    from src.engine.robot.calibration.calibration_navigation_service import CalibrationNavigationService
    from src.engine.vision.homography_residual_transformer import HomographyResidualTransformer

    vision_service = robot_system.get_optional_service(CommonServiceID.VISION)
    work_area_service = robot_system.get_service(CommonServiceID.WORK_AREAS)
    robot_service = robot_system.get_optional_service(CommonServiceID.ROBOT)
    robot_config = robot_system._robot_config
    navigation_service = CalibrationNavigationService(
        robot_system.get_service(CommonServiceID.NAVIGATION),
        before_move=(lambda: work_area_service.set_active_area_id("spray")),
    )
    transformer = (
        HomographyResidualTransformer(
            vision_service.camera_to_robot_matrix_path,
            camera_to_tcp_x_offset=robot_config.camera_to_tcp_x_offset,
            camera_to_tcp_y_offset=robot_config.camera_to_tcp_y_offset,
        )
        if vision_service is not None and robot_config is not None else
        HomographyResidualTransformer(vision_service.camera_to_robot_matrix_path)
        if vision_service is not None else None
    )
    camera_tcp_offset_calibrator = (
        CameraTcpOffsetCalibrationService(
            vision_service=vision_service,
            robot_service=robot_service,
            navigation_service=navigation_service,
            settings_service=robot_system._settings_service,
            robot_config_key=CommonSettingsID.ROBOT_CONFIG,
            robot_config=robot_system._robot_config,
            calibration_settings=robot_system._robot_calibration,
            robot_tool=robot_system._robot_config.robot_tool,
            robot_user=robot_system._robot_config.robot_user,
        )
        if vision_service is not None and robot_service is not None and robot_config is not None else None
    )
    marker_height_mapping_service = (
        ArucoMarkerHeightMappingService(
            vision_service=vision_service,
            robot_service=robot_service,
            height_service=getattr(robot_system, "_height_measuring_service", None),
            robot_config=robot_system._robot_config,
            calib_config=robot_system._robot_calibration,
            transformer=transformer,
            use_marker_centre=True,
        )
        if vision_service is not None
           and robot_service is not None
           and getattr(robot_system, "_height_measuring_service", None) is not None
           and robot_config is not None
        else None
    )
    intrinsic_capture_service = (
        IntrinsicCaptureService(
            robot_service=robot_service,
            vision_service=vision_service,
            robot_config=robot_system._robot_config,
            messaging=getattr(robot_system, "_messaging_service", None),
            default_output_dir=robot_system.storage_path("settings", "vision", "data", "intrinsic_capture_output"),
        )
        if vision_service is not None and robot_service is not None and robot_config is not None else None
    )

    def _observer_position(group_id: str):
        navigation = getattr(robot_system, "_navigation", None)
        return navigation.get_group_position(group_id) if navigation is not None else None

    service = CalibrationApplicationService(
        vision_service=vision_service,
        process_controller=robot_system.coordinator,
        robot_service=robot_service,
        height_service=getattr(robot_system, '_height_measuring_service', None),
        robot_config=robot_system._robot_config,
        calib_config=robot_system._robot_calibration,
        transformer=transformer,
        work_area_service=work_area_service,
        camera_tcp_offset_calibrator=camera_tcp_offset_calibrator,
        marker_height_mapping_service=marker_height_mapping_service,
        intrinsic_capture_service=intrinsic_capture_service,
        calibration_settings_service=CalibrationSettingsApplicationService(robot_system._settings_service),
        laser_calibration_service=getattr(robot_system, "_height_measuring_calibration_service", None),
        laser_ops=getattr(robot_system, "_laser_detection_service", None),
        observer_group_provider=robot_system.get_observer_group_for_area,
        observer_position_provider=_observer_position,
        use_marker_centre=True,
        work_area_definitions=robot_system.get_work_area_definitions(),
    )

    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: CalibrationFactory(
            work_area_definitions=robot_system.get_work_area_definitions()
        ).build(service, messaging=ms, jog_service=jog_service)
    )


def _build_dashboard_application(system):
    from src.applications.base.widget_application import WidgetApplication
    from src.robot_systems.glue.applications.dashboard.glue_dashboard import GlueDashboard
    from src.robot_systems.glue.domain.glue_job_builder_service import GlueJobBuilderService
    from src.robot_systems.glue.domain.glue_job_execution_service import GlueJobExecutionService
    from src.robot_systems.glue.domain.matching.matching_service import MatchingService
    from src.robot_systems.glue.domain.workpieces.repository.json_workpiece_repository import JsonWorkpieceRepository
    from src.robot_systems.glue.domain.workpieces.service.workpiece_service import WorkpieceService

    coordinator = system.coordinator
    settings_service = system._settings_service
    weight_service = system.get_optional_service(ServiceID.WEIGHT)
    vision_service = system.get_optional_service(CommonServiceID.VISION)
    robot_service = system.get_optional_service(CommonServiceID.ROBOT)
    capture_snapshot_service = _build_capture_snapshot_service(system)
    robot_config = getattr(system, "_robot_config", None)

    try:
        z_min = float(robot_config.safety_limits.z_min) if robot_config is not None else 0.0
    except Exception:
        z_min = 0.0

    base_transformer, resolver = system.get_shared_vision_resolver()
    tool_point_name = (
        getattr(system.get_target_point_definition("tool"), "name", "") or ""
    )
    execution_service = (
        GlueJobExecutionService(
                matching_service=MatchingService(
                    vision_service=vision_service,
                    workpiece_service=WorkpieceService(JsonWorkpieceRepository(system.workpieces_storage_path())),
                    capture_snapshot_service=capture_snapshot_service,
                ),
            job_builder=GlueJobBuilderService(
                transformer=base_transformer,
                resolver=resolver,
                z_min=z_min,
                target_point_name=tool_point_name,
            ),
            glue_process=coordinator.glue_process,
            navigation_service=coordinator.glue_process.navigation_service,
            vision_service=vision_service,
            capture_snapshot_service=capture_snapshot_service,
            messaging_service=system._messaging_service,
        )
        if vision_service is not None else None
    )

    return WidgetApplication(
        widget_factory=lambda ms: GlueDashboard.create(
            coordinator=coordinator,
            settings_service=settings_service,
            messaging_service=ms,
            weight_service=weight_service,
            execution_service=execution_service,
            robot_service=robot_service,
            preview_transformer=base_transformer,
        )
    )


def _build_broker_debug_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.broker_debug.broker_debug_factory import BrokerDebugFactory
    from src.applications.broker_debug.service.broker_debug_application_service import BrokerDebugApplicationService

    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: BrokerDebugFactory().build(
            BrokerDebugApplicationService(ms),
            messaging=ms,
            jog_service=jog_service,
        )
    )


def _build_glue_cell_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.glue_cell_settings import GlueCellSettingsFactory, GlueCellSettingsService

    service = GlueCellSettingsService(
        robot_app._settings_service,
        settings_key=SettingsID.GLUE_CELLS,
        weight_service=robot_app.get_optional_service(ServiceID.WEIGHT)
    )
    jog_service = build_robot_system_jog_service(robot_app)
    return WidgetApplication(
        widget_factory=lambda ms: GlueCellSettingsFactory().build(service, ms, jog_service=jog_service)
    )


def _build_dispense_channel_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.robot_systems.glue.applications.dispense_channel_settings import (
        DispenseChannelSettingsFactory,
        DispenseChannelSettingsService,
    )

    service = DispenseChannelSettingsService(
        settings_service=robot_app._settings_service,
        channel_settings_key=SettingsID.DISPENSE_CHANNELS,
        cells_settings_key=SettingsID.GLUE_CELLS,
        catalog_settings_key=SettingsID.GLUE_CATALOG,
        glue_settings_key=SettingsID.GLUE_SETTINGS,
        channel_definitions=robot_app.get_dispense_channel_definitions(),
        weight_service=robot_app.get_optional_service(ServiceID.WEIGHT),
        motor_service=robot_app.get_optional_service(ServiceID.MOTOR),
    )
    jog_service = build_robot_system_jog_service(robot_app)
    return WidgetApplication(
        widget_factory=lambda ms: DispenseChannelSettingsFactory().build(service, ms, jog_service=jog_service)
    )


def _build_robot_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.robot_settings.robot_settings_factory import RobotSettingsFactory
    from src.applications.robot_settings.service.robot_settings_application_service import \
        RobotSettingsApplicationService
    from src.robot_systems.glue.component_ids import ServiceID
    from src.robot_systems.glue.targeting.settings_adapter import from_editor_dict, to_editor_dict

    def _save_targeting_definitions(data) -> None:
        robot_app._settings_service.save(
            CommonSettingsID.TARGETING,
            from_editor_dict(
                data,
                robot_app._settings_service.get(CommonSettingsID.TARGETING),
                robot_app.get_target_point_definitions(),
                robot_app.get_target_frame_definitions(),
            ),
        )
        robot_app.invalidate_shared_vision_resolver()

    service = RobotSettingsApplicationService(
        robot_app._settings_service,
        config_key=CommonSettingsID.ROBOT_CONFIG,
        movement_groups_key=CommonSettingsID.MOVEMENT_GROUPS,
        calibration_key=CommonSettingsID.ROBOT_CALIBRATION,
        robot_service=robot_app.get_optional_service(CommonServiceID.ROBOT),
        tool_settings_key=CommonSettingsID.TOOL_CHANGER_CONFIG,
        navigation_service=getattr(robot_app, "_navigation", None) or robot_app.get_service(CommonServiceID.NAVIGATION),
        load_targeting_definitions_fn=lambda: to_editor_dict(
            robot_app._settings_service.get(CommonSettingsID.TARGETING),
            robot_app.get_target_point_definitions(),
            robot_app.get_target_frame_definitions(),
        ),
        save_targeting_definitions_fn=_save_targeting_definitions,
        movement_group_definitions=robot_app.get_movement_group_definitions(),
    )
    jog_service = build_robot_system_jog_service(robot_app)
    return WidgetApplication(
        widget_factory=lambda ms: RobotSettingsFactory(
            movement_group_definitions=robot_app.get_movement_group_definitions()
        ).build(service, messaging=ms, jog_service=jog_service)
    )


def _build_glue_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.robot_systems.glue.applications.glue_settings import GlueSettingsFactory, GlueSettingsApplicationService

    service = GlueSettingsApplicationService(robot_app._settings_service)
    jog_service = build_robot_system_jog_service(robot_app)
    return WidgetApplication(
        widget_factory=lambda ms: GlueSettingsFactory().build(service, messaging=ms, jog_service=jog_service)
    )


def _build_modbus_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.engine.hardware.communication.modbus.modbus_action_service import ModbusActionService
    from src.applications.modbus_settings import ModbusSettingsFactory, ModbusSettingsApplicationService

    settings_service = ModbusSettingsApplicationService(
        robot_app._settings_service,
        config_key=CommonSettingsID.MODBUS_CONFIG,
    )

    action_service = ModbusActionService()
    jog_service = build_robot_system_jog_service(robot_app)
    return WidgetApplication(
        widget_factory=lambda ms: ModbusSettingsFactory().build(
            settings_service,
            action_service,
            messaging=ms,
            jog_service=jog_service,
        )
    )


def _build_pick_target_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.pick_target.pick_target_factory import PickTargetFactory
    from src.applications.pick_target.service.pick_target_application_service import PickTargetApplicationService

    vision_service = robot_system.get_optional_service(CommonServiceID.VISION)
    capture_snapshot_service = _build_capture_snapshot_service(robot_system)
    robot_service = robot_system.get_optional_service(CommonServiceID.ROBOT)
    _, resolver = robot_system.get_shared_vision_resolver()
    height_service = getattr(robot_system, "_height_measuring_service", None)
    default_target_name = (
        robot_system.get_targeting_provider().get_default_target_name()
        if robot_system.get_targeting_provider() is not None else ""
    )
    calibration_frame_name = (
        getattr(robot_system.get_target_frame_for_work_area("spray"), "name", "") or ""
    )
    pickup_frame_name = (
        getattr(robot_system.get_target_frame_for_work_area("pickup"), "name", "") or ""
    )
    service = PickTargetApplicationService(
        vision_service=vision_service,
        capture_snapshot_service=capture_snapshot_service,
        robot_service=robot_service,
        resolver=resolver,
        robot_config=robot_system._robot_config,
        navigation=robot_system._navigation,
        height_measuring=height_service,
        default_target_name=default_target_name,
        calibration_frame_name=calibration_frame_name,
        pickup_frame_name=pickup_frame_name,
    )
    jog_service = build_robot_system_jog_service(robot_system, reference_rz_provider=service.get_jog_reference_rz)
    return WidgetApplication(
        widget_factory=lambda ms: PickTargetFactory().build(service, messaging=ms, jog_service=jog_service)
    )


def _build_device_control_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.device_control.device_control_factory import DeviceControlFactory
    from src.applications.device_control.service.device_control_application_service import \
        DeviceControlApplicationService
    from src.applications.device_control.service.i_device_control_service import MotorEntry
    from src.robot_systems.glue.component_ids import SettingsID

    config = robot_system._settings_service.get(SettingsID.GLUE_MOTOR_CONFIG)
    motors = [MotorEntry(name=m.name, address=m.address) for m in config.motors]

    service = DeviceControlApplicationService(
        motors=motors,
        motor_service=getattr(robot_system, '_motor', None),
        generator=getattr(robot_system, '_generator', None),
        laser=getattr(robot_system, '_laser_detection_service', None),
        vacuum_pump=None,
    )
    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: DeviceControlFactory().build(service, messaging=ms, jog_service=jog_service)
    )


def _build_intrinsic_capture_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.intrinsic_calibration_capture.service.intrinsic_capture_service import (
        IntrinsicCaptureService,
    )
    from src.applications.intrinsic_calibration_capture.intrinsic_capture_factory import (
        IntrinsicCaptureFactory,
    )

    service = IntrinsicCaptureService(
        robot_service=robot_system.get_optional_service(CommonServiceID.ROBOT),
        vision_service=robot_system.get_optional_service(CommonServiceID.VISION),
        robot_config=robot_system._robot_config,
        messaging=getattr(robot_system, "_messaging_service", None),
        default_output_dir=robot_system.storage_path("settings", "vision", "data", "intrinsic_capture_output"),
    )
    return WidgetApplication(
        widget_factory=lambda ms: IntrinsicCaptureFactory().build(service, messaging=ms)
    )


def _build_aruco_z_probe_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.aruco_z_probe.aruco_z_probe_factory import ArucoZProbeFactory
    from src.applications.aruco_z_probe.service.aruco_z_probe_application_service import (
        ArucoZProbeApplicationService,
    )

    service = ArucoZProbeApplicationService(
        navigation=getattr(robot_system, "_navigation", None),
        robot_service=robot_system.get_optional_service(CommonServiceID.ROBOT),
        vision_service=robot_system.get_optional_service(CommonServiceID.VISION),
        robot_config=getattr(robot_system, "_robot_config", None),
    )
    return WidgetApplication(
        widget_factory=lambda ms: ArucoZProbeFactory().build(service, messaging=ms)
    )


def _build_height_measuring_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.height_measuring.height_measuring_factory import HeightMeasuringFactory
    from src.applications.height_measuring.service.height_measuring_application_service import (
        HeightMeasuringApplicationService,
    )

    settings_repo = robot_app._settings_service.get_repo(CommonSettingsID.HEIGHT_MEASURING_SETTINGS)
    service = HeightMeasuringApplicationService(
        vision_service=robot_app.get_optional_service(CommonServiceID.VISION),
        height_measuring_service=robot_app._height_measuring_service,
        calibration_service=robot_app._height_measuring_calibration_service,
        settings_repo=settings_repo,
        laser_ops=robot_app._laser_detection_service,
    )
    jog_service = build_robot_system_jog_service(robot_app)
    return WidgetApplication(
        widget_factory=lambda ms: HeightMeasuringFactory().build(service, messaging=ms, jog_service=jog_service)
    )
