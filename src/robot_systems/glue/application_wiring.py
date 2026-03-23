from src.applications.workpiece_editor.editor_core.config import SegmentEditorConfig
from src.engine.robot.calibration.robot_calibration.config_helpers import AdaptiveMovementConfig, \
    RobotCalibrationEventsConfig
from src.engine.robot.configuration.robot_settings import SafetyLimits
from src.engine.vision.homography_transformer import HomographyTransformer
from src.robot_systems.glue.domain.workpieces.schemas import build_glue_workpiece_form_schema, \
    build_glue_segment_settings_schema
from src.robot_systems.glue.navigation import GlueNavigationService
from src.robot_systems.glue.service_ids import ServiceID
from src.robot_systems.glue.settings_ids import SettingsID
import os
import logging

from src.shared_contracts.events.robot_events import RobotCalibrationTopics

# ── Canonical storage paths ───────────────────────────────────────────────────
# Single definition — used by both editor (write) and library (read).
_logger = logging.getLogger(__name__)
_SYSTEM_DIR = os.path.dirname(os.path.abspath(__file__))
_WORKPIECES_STORAGE   = os.path.join(_SYSTEM_DIR, "storage", "workpieces")
_USERS_STORAGE        = os.path.join(_SYSTEM_DIR, "storage", "users", "users.csv")
_PERMISSIONS_STORAGE  = os.path.join(_SYSTEM_DIR, "storage", "settings", "permissions.json")


def _build_capture_snapshot_service(robot_system):
    from src.robot_systems.glue.capture_snapshot_service import GlueCaptureSnapshotService

    return GlueCaptureSnapshotService(
        vision_service=robot_system.get_optional_service(ServiceID.VISION),
        robot_service=robot_system.get_optional_service(ServiceID.ROBOT),
    )


def _build_glue_vision_resolver(robot_system):
    """Build a shared VisionTargetResolver for the glue robot system.

    Returns ``(base_transformer, resolver)`` where ``resolver`` may be None
    if no vision service is available.
    """
    from src.engine.robot.targeting import PointRegistry, VisionTargetResolver

    vision_service = robot_system.get_optional_service(ServiceID.VISION)
    robot_config = getattr(robot_system, "_robot_config", None)
    targeting_settings = getattr(robot_system, "_glue_targeting", None)
    if vision_service is None:
        return None, None

    base_transformer = (
        HomographyTransformer(
            vision_service.camera_to_robot_matrix_path,
            camera_to_tcp_x_offset=robot_config.camera_to_tcp_x_offset,
            camera_to_tcp_y_offset=robot_config.camera_to_tcp_y_offset,
        )
        if robot_config is not None else
        HomographyTransformer(vision_service.camera_to_robot_matrix_path)
    )

    registry = PointRegistry(targeting_settings)
    resolver = VisionTargetResolver(
        base_transformer=base_transformer,
        registry=registry,
        camera_to_tcp_x_offset=float(getattr(robot_config, "camera_to_tcp_x_offset", 0.0)) if robot_config else 0.0,
        camera_to_tcp_y_offset=float(getattr(robot_config, "camera_to_tcp_y_offset", 0.0)) if robot_config else 0.0,
    )
    return base_transformer, resolver


def _build_glue_jog_service(robot_system, reference_rz_provider=None):
    from src.applications.base.robot_jog_service import RobotJogService
    from src.engine.robot.targeting import JogFramePoseResolver, PointRegistry

    robot_service = robot_system.get_optional_service(ServiceID.ROBOT)
    robot_config = getattr(robot_system, "_robot_config", None)
    targeting_settings = getattr(robot_system, "_glue_targeting", None)
    pose_resolver = None
    if targeting_settings is not None:
        pose_resolver = JogFramePoseResolver(
            registry=PointRegistry(targeting_settings),
            camera_to_tcp_x_offset=float(getattr(robot_config, "camera_to_tcp_x_offset", 0.0)),
            camera_to_tcp_y_offset=float(getattr(robot_config, "camera_to_tcp_y_offset", 0.0)),
            reference_rz_provider=reference_rz_provider,
        )
    return RobotJogService(
        robot_service=robot_service,
        pose_resolver=pose_resolver,
        tool_getter=lambda: int(getattr(robot_config, "robot_tool", 0)) if robot_config is not None else 0,
        user_getter=lambda: int(getattr(robot_config, "robot_user", 0)) if robot_config is not None else 0,
    )

def _build_pick_and_place_visualizer(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.pick_and_place_visualizer import PickAndPlaceVisualizerFactory
    from src.applications.pick_and_place_visualizer.service.pick_and_place_visualizer_service import (
        PickAndPlaceVisualizerService,
    )
    from src.robot_systems.glue.domain.matching.matching_service import MatchingService
    from src.robot_systems.glue.domain.workpieces.repository.json_workpiece_repository import JsonWorkpieceRepository
    from src.robot_systems.glue.domain.workpieces.service.workpiece_service import WorkpieceService
    from src.robot_systems.glue.processes.pick_and_place.config import PickAndPlaceConfig

    vision_service    = robot_system.get_optional_service(ServiceID.VISION)
    capture_snapshot_service = _build_capture_snapshot_service(robot_system)
    workpiece_service = WorkpieceService(JsonWorkpieceRepository(_WORKPIECES_STORAGE))
    matching_service  = MatchingService(
        vision_service=vision_service,
        workpiece_service=workpiece_service,
        capture_snapshot_service=capture_snapshot_service,
    )
    service = PickAndPlaceVisualizerService(
        matching_service=matching_service,
        config=PickAndPlaceConfig(),
        pick_and_place_process=robot_system.coordinator.pick_and_place_process,
    )
    jog_service = _build_glue_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: PickAndPlaceVisualizerFactory().build(service, ms, jog_service=jog_service)
    )



def _build_contour_matching_tester(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.contour_matching_tester.contour_matching_tester_factory import ContourMatchingTesterFactory
    from src.applications.contour_matching_tester.service.contour_matching_tester_service import ContourMatchingTesterService
    from src.robot_systems.glue.domain.workpieces.repository.json_workpiece_repository import JsonWorkpieceRepository
    from src.robot_systems.glue.domain.workpieces.service.workpiece_service import WorkpieceService
    from src.robot_systems.glue.domain.matching.matching_service import MatchingService

    workpiece_service = WorkpieceService(JsonWorkpieceRepository(_WORKPIECES_STORAGE))
    vision_service    = robot_system.get_optional_service(ServiceID.VISION)
    capture_snapshot_service = _build_capture_snapshot_service(robot_system)

    service = ContourMatchingTesterService(
        vision_service=vision_service,
        workpiece_service=workpiece_service,
        capture_snapshot_service=capture_snapshot_service,
    )
    jog_service = _build_glue_jog_service(robot_system)
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

    workpiece_service = WorkpieceService(JsonWorkpieceRepository(_WORKPIECES_STORAGE))
    vision_service = robot_system.get_optional_service(ServiceID.VISION)
    capture_snapshot_service = _build_capture_snapshot_service(robot_system)
    robot_config = getattr(robot_system, "_robot_config", None)
    try:
        z_min = float(robot_config.safety_limits.z_min) if robot_config is not None else 0.0
    except Exception:
        z_min = 0.0
    base_transformer, resolver = _build_glue_vision_resolver(robot_system)
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
        ),
        glue_process=robot_system.coordinator.glue_process,
        execution_service=execution_service,
    )
    return WidgetApplication(widget_factory=lambda ms: GlueProcessDriverFactory(ms).build(service))


def _get_tools(robot_system) -> list:
    tc = robot_system._settings_service.get(SettingsID.TOOL_CHANGER_CONFIG)
    return tc.get_tool_options() if tc else []


def _build_tool_settings_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.tool_settings import (
        ToolSettingsFactory, ToolSettingsApplicationService,
    )
    service = ToolSettingsApplicationService(robot_system._settings_service)
    jog_service = _build_glue_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: ToolSettingsFactory().build(service, messaging=ms, jog_service=jog_service)
    )


def _build_workpiece_library_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.workpiece_library.workpiece_library_factory import WorkpieceLibraryFactory
    from src.robot_systems.glue.domain.workpieces.glue_workpiece_library_service import GlueWorkpieceLibraryService
    from src.robot_systems.glue.domain.workpieces.repository.json_workpiece_repository import JsonWorkpieceRepository
    from src.robot_systems.glue.domain.workpieces.service.workpiece_service import WorkpieceService

    settings_service = robot_system._settings_service
    catalog = settings_service.get(SettingsID.GLUE_CATALOG)

    def _get_glue_types() -> list:
        return catalog.get_all_names() if hasattr(catalog, "get_all_names") else []

    repo = JsonWorkpieceRepository(_WORKPIECES_STORAGE)

    service = GlueWorkpieceLibraryService(
        WorkpieceService(repo),
        glue_types_fn=_get_glue_types,
        tools_fn=lambda: _get_tools(robot_system),
    )
    jog_service = _build_glue_jog_service(robot_system)
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
    vision_service = robot_system.get_optional_service(ServiceID.VISION)
    capture_snapshot_service = _build_capture_snapshot_service(robot_system)
    robot_config = robot_system._robot_config

    base_transformer, resolver = _build_glue_vision_resolver(robot_system)

    def _get_glue_types():
        catalog = settings_service.get(SettingsID.GLUE_CATALOG)
        return catalog.get_all_names() if hasattr(catalog, "get_all_names") else []

    def _get_tools():
        tc = settings_service.get(SettingsID.TOOL_CHANGER_CONFIG)
        return tc.get_tool_options() if tc else []

    catalog = settings_service.get(SettingsID.GLUE_CATALOG)
    glue_types = catalog.get_all_names() if hasattr(catalog, "get_all_names") else []

    workpiece_service = WorkpieceService(JsonWorkpieceRepository(_WORKPIECES_STORAGE),tool_provider=_get_tools)

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
        robot_service=robot_system.get_optional_service(ServiceID.ROBOT),
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
        jog_service = _build_glue_jog_service(robot_system)
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
    from src.applications.user_management.user_management_factory import UserManagementFactory
    from src.applications.user_management.service.user_management_application_service import \
        UserManagementApplicationService
    from src.applications.user_management.domain.csv_user_repository import CsvUserRepository
    from src.robot_systems.glue.domain.users import GLUE_USER_SCHEMA
    from src.robot_systems.glue.domain.permissions.permissions_repository import PermissionsRepository
    from src.engine.auth.authorization_service import AuthorizationService

    service     = UserManagementApplicationService(CsvUserRepository(_USERS_STORAGE, GLUE_USER_SCHEMA))
    perm_repo   = PermissionsRepository(_PERMISSIONS_STORAGE)
    perm_svc    = AuthorizationService(perm_repo)
    known_ids   = [spec.app_id for spec in robot_system.shell.applications]
    jog_service = _build_glue_jog_service(robot_system)

    def _build(messaging_service):
        return UserManagementFactory().build(
            service,
            perm_svc,
            known_ids,
            messaging=messaging_service,
            jog_service=jog_service,
        )

    return WidgetApplication(widget_factory=_build)


def _build_camera_settings_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.camera_settings.camera_settings_factory import CameraSettingsFactory
    from src.applications.camera_settings.service.camera_settings_application_service import \
        CameraSettingsApplicationService
    from src.robot_systems.glue.service_ids import ServiceID

    service = CameraSettingsApplicationService(
        settings_service=robot_system._settings_service,
        vision_service=robot_system.get_optional_service(ServiceID.VISION),
    )
    factory = CameraSettingsFactory()
    jog_service = _build_glue_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: factory.build(service, ms, jog_service=jog_service)
    )


def _build_calibration_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.calibration.calibration_factory import CalibrationFactory
    from src.applications.calibration.service.calibration_application_service import CalibrationApplicationService
    from src.applications.base.robot_jog_service import RobotJogService
    from src.engine.robot.calibration.aruco_marker_height_mapping_service import (
        ArucoMarkerHeightMappingService,
    )
    from src.engine.robot.calibration.camera_tcp_offset_calibration_service import (
        CameraTcpOffsetCalibrationService,
    )
    from src.engine.vision.homography_transformer import HomographyTransformer
    from src.robot_systems.glue.navigation import GlueNavigationService

    vision_service = robot_system.get_optional_service(ServiceID.VISION)
    robot_service = robot_system.get_optional_service(ServiceID.ROBOT)
    robot_config = robot_system._robot_config
    navigation_service = GlueNavigationService(
        robot_system.get_service(ServiceID.NAVIGATION),
        vision=vision_service,
    )
    transformer = (
        HomographyTransformer(
            vision_service.camera_to_robot_matrix_path,
            camera_to_tcp_x_offset=robot_config.camera_to_tcp_x_offset,
            camera_to_tcp_y_offset=robot_config.camera_to_tcp_y_offset,
        )
        if vision_service is not None and robot_config is not None else
        HomographyTransformer(vision_service.camera_to_robot_matrix_path)
        if vision_service is not None else None
    )
    camera_tcp_offset_calibrator = (
        CameraTcpOffsetCalibrationService(
            vision_service=vision_service,
            robot_service=robot_service,
            navigation_service=navigation_service,
            settings_service=robot_system._settings_service,
            robot_config_key=SettingsID.ROBOT_CONFIG,
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

    service = CalibrationApplicationService(
        vision_service=vision_service,
        process_controller=robot_system.coordinator,
        robot_service=robot_service,
        height_service=getattr(robot_system, '_height_measuring_service', None),
        robot_config=robot_system._robot_config,
        calib_config=robot_system._robot_calibration,
        transformer=transformer,
        camera_tcp_offset_calibrator=camera_tcp_offset_calibrator,
        marker_height_mapping_service=marker_height_mapping_service,
        use_marker_centre=True,
    )

    jog_service = _build_glue_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: CalibrationFactory().build(service, messaging=ms, jog_service=jog_service)
    )


def _build_dashboard_application(system):
    from src.applications.base.widget_application import WidgetApplication
    from src.engine.vision.homography_transformer import HomographyTransformer
    from src.robot_systems.glue.applications.dashboard.glue_dashboard import GlueDashboard
    from src.robot_systems.glue.domain.glue_job_builder_service import GlueJobBuilderService
    from src.robot_systems.glue.domain.glue_job_execution_service import GlueJobExecutionService
    from src.robot_systems.glue.domain.matching.matching_service import MatchingService
    from src.robot_systems.glue.domain.workpieces.repository.json_workpiece_repository import JsonWorkpieceRepository
    from src.robot_systems.glue.domain.workpieces.service.workpiece_service import WorkpieceService

    coordinator = system.coordinator
    settings_service = system._settings_service
    weight_service = system.get_optional_service(ServiceID.WEIGHT)
    vision_service = system.get_optional_service(ServiceID.VISION)
    robot_service = system.get_optional_service(ServiceID.ROBOT)
    capture_snapshot_service = _build_capture_snapshot_service(system)
    robot_config = getattr(system, "_robot_config", None)

    try:
        z_min = float(robot_config.safety_limits.z_min) if robot_config is not None else 0.0
    except Exception:
        z_min = 0.0

    base_transformer, resolver = _build_glue_vision_resolver(system)
    execution_service = (
        GlueJobExecutionService(
            matching_service=MatchingService(
                vision_service=vision_service,
                workpiece_service=WorkpieceService(JsonWorkpieceRepository(_WORKPIECES_STORAGE)),
                capture_snapshot_service=capture_snapshot_service,
            ),
            job_builder=GlueJobBuilderService(
                transformer=base_transformer,
                resolver=resolver,
                z_min=z_min,
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
    from src.applications.broker_debug.broker_debug_factory import BrokerDebugFactory
    from src.applications.broker_debug.service.broker_debug_application_service import BrokerDebugApplicationService

    jog_service = _build_glue_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: BrokerDebugFactory().build(
            BrokerDebugApplicationService(ms),
            messaging=ms,
            jog_service=jog_service,
        )
    )


def _build_glue_cell_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.glue_cell_settings import GlueCellSettingsFactory, GlueCellSettingsService

    service = GlueCellSettingsService(
        robot_app._settings_service,
        settings_key=SettingsID.GLUE_CELLS,
        weight_service=robot_app.get_optional_service(ServiceID.WEIGHT)
    )
    jog_service = _build_glue_jog_service(robot_app)
    return WidgetApplication(
        widget_factory=lambda ms: GlueCellSettingsFactory().build(service, ms, jog_service=jog_service)
    )


def _build_robot_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.robot_settings.robot_settings_factory import RobotSettingsFactory
    from src.applications.robot_settings.service.robot_settings_application_service import RobotSettingsApplicationService
    from src.robot_systems.glue.service_ids import ServiceID

    service = RobotSettingsApplicationService(
        robot_app._settings_service,
        config_key         = SettingsID.ROBOT_CONFIG,
        calibration_key    = SettingsID.ROBOT_CALIBRATION,
        robot_service      = robot_app.get_optional_service(ServiceID.ROBOT),
        tool_settings_key  = SettingsID.TOOL_CHANGER_CONFIG,
        navigation_service = robot_app.get_service(ServiceID.NAVIGATION),
    )
    jog_service = _build_glue_jog_service(robot_app)
    return WidgetApplication(
        widget_factory=lambda ms: RobotSettingsFactory().build(service, messaging=ms, jog_service=jog_service)
    )

def _build_glue_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.robot_systems.glue.applications.glue_settings import GlueSettingsFactory, GlueSettingsApplicationService

    service = GlueSettingsApplicationService(robot_app._settings_service)
    jog_service = _build_glue_jog_service(robot_app)
    return WidgetApplication(
        widget_factory=lambda ms: GlueSettingsFactory().build(service, messaging=ms, jog_service=jog_service)
    )


def _build_modbus_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.engine.hardware.communication.modbus.modbus_action_service import ModbusActionService
    from src.applications.modbus_settings import ModbusSettingsFactory, ModbusSettingsApplicationService

    settings_service = ModbusSettingsApplicationService(
        robot_app._settings_service,
        config_key=SettingsID.MODBUS_CONFIG,
    )

    action_service = ModbusActionService()
    jog_service = _build_glue_jog_service(robot_app)
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
    from src.applications.pick_target.pick_target_factory import PickTargetFactory
    from src.applications.pick_target.service.pick_target_application_service import PickTargetApplicationService
    from src.engine.robot.height_measuring.height_correction_service import HeightCorrectionService

    vision_service = robot_system.get_optional_service(ServiceID.VISION)
    capture_snapshot_service = _build_capture_snapshot_service(robot_system)
    robot_service  = robot_system.get_optional_service(ServiceID.ROBOT)
    base_transformer, resolver = _build_glue_vision_resolver(robot_system)
    height_service = getattr(robot_system, "_height_measuring_service", None)
    height_correction = HeightCorrectionService(height_service) if height_service is not None else None
    service = PickTargetApplicationService(
        vision_service=vision_service,
        capture_snapshot_service=capture_snapshot_service,
        robot_service=robot_service,
        transformer=base_transformer,
        robot_config=robot_system._robot_config,
        navigation=robot_system._navigation,
        height_correction=height_correction,
        height_measuring=height_service,
    )
    jog_service = _build_glue_jog_service(robot_system, reference_rz_provider=service.get_jog_reference_rz)
    return WidgetApplication(
        widget_factory=lambda ms: PickTargetFactory().build(service, messaging=ms, jog_service=jog_service)
    )


def _build_device_control_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.device_control.device_control_factory import DeviceControlFactory
    from src.applications.device_control.service.device_control_application_service import DeviceControlApplicationService
    from src.applications.device_control.service.i_device_control_service import MotorEntry
    from src.robot_systems.glue.settings_ids import SettingsID

    config  = robot_system._settings_service.get(SettingsID.GLUE_MOTOR_CONFIG)
    motors  = [MotorEntry(name=m.name, address=m.address) for m in config.motors]

    service = DeviceControlApplicationService(
        motors        = motors,
        motor_service = getattr(robot_system, '_motor', None),
        generator     = getattr(robot_system, '_generator', None),
        laser         = getattr(robot_system, '_laser_detection_service', None),
        vacuum_pump   = None,
    )
    jog_service = _build_glue_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: DeviceControlFactory().build(service, messaging=ms, jog_service=jog_service)
    )


def _build_height_measuring_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.height_measuring.height_measuring_factory import HeightMeasuringFactory
    from src.applications.height_measuring.service.height_measuring_application_service import (
        HeightMeasuringApplicationService,
    )

    settings_repo = robot_app._settings_service.get_repo(SettingsID.HEIGHT_MEASURING_SETTINGS)
    service = HeightMeasuringApplicationService(
        vision_service=robot_app.get_optional_service(ServiceID.VISION),
        height_measuring_service=robot_app._height_measuring_service,
        calibration_service=robot_app._height_measuring_calibration_service,
        settings_repo=settings_repo,
        laser_ops=robot_app._laser_detection_service,
    )
    jog_service = _build_glue_jog_service(robot_app)
    return WidgetApplication(
        widget_factory=lambda ms: HeightMeasuringFactory().build(service, messaging=ms, jog_service=jog_service)
    )
