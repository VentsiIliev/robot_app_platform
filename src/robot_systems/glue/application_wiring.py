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
_WORKPIECES_STORAGE = os.path.join(_SYSTEM_DIR, "storage", "workpieces")
_USERS_STORAGE = os.path.join(_SYSTEM_DIR, "storage", "users", "users.csv")

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
    workpiece_service = WorkpieceService(JsonWorkpieceRepository(_WORKPIECES_STORAGE))
    matching_service  = MatchingService(vision_service=vision_service,
                                        workpiece_service=workpiece_service)
    service = PickAndPlaceVisualizerService(
        matching_service=matching_service,
        config=PickAndPlaceConfig(),
        pick_and_place_process=robot_system.coordinator.pick_and_place_process,
    )
    return WidgetApplication(
        widget_factory=lambda ms: PickAndPlaceVisualizerFactory().build(service, ms)
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

    service = ContourMatchingTesterService(
        vision_service=vision_service,
        workpiece_service=workpiece_service,

    )
    return WidgetApplication(widget_factory=lambda ms: ContourMatchingTesterFactory().build(service, ms))


def _get_tools(robot_system) -> list:
    tc = robot_system._settings_service.get(SettingsID.TOOL_CHANGER_CONFIG)
    return tc.get_tool_options() if tc else []


def _build_tool_settings_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.tool_settings import (
        ToolSettingsFactory, ToolSettingsApplicationService,
    )
    service = ToolSettingsApplicationService(robot_system._settings_service)
    return WidgetApplication(
        widget_factory=lambda _ms: ToolSettingsFactory().build(service)
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
    return WidgetApplication(
        widget_factory=lambda _ms: WorkpieceLibraryFactory().build(service, _ms)
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
    robot_config = robot_system._robot_config

    transformer = (
        HomographyTransformer(
            vision_service.camera_to_robot_matrix_path,
            tcp_x_offset=robot_config.tcp_x_offset,
            tcp_y_offset=robot_config.tcp_y_offset,
        )
        if vision_service is not None and robot_config is not None else
        HomographyTransformer(vision_service.camera_to_robot_matrix_path)
        if vision_service is not None else None
    )

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
        save_fn=lambda data: workpiece_service.save(data),
        update_fn=lambda sid, data: workpiece_service.update(sid, data),
        form_schema=lambda: build_glue_workpiece_form_schema(  # ← lazy callable
            glue_types=_get_glue_types(),
            tools=_get_tools(),
        ),
        segment_config=SegmentEditorConfig(schema=build_glue_segment_settings_schema(_get_glue_types())),
        id_exists_fn=workpiece_service.workpiece_id_exists,
        transformer=transformer,
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
        widget = WorkpieceEditorFactory(ms).build(service)
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

    service = UserManagementApplicationService(CsvUserRepository(_USERS_STORAGE, GLUE_USER_SCHEMA))
    return WidgetApplication(widget_factory=lambda _ms: UserManagementFactory().build(service))


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
    return WidgetApplication(
        widget_factory=lambda ms: factory.build(service, ms)
    )


def _build_calibration_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.calibration.calibration_factory import CalibrationFactory
    from src.applications.calibration.service.calibration_application_service import CalibrationApplicationService
    from src.applications.base.robot_jog_service import RobotJogService
    from src.engine.vision.homography_transformer import HomographyTransformer

    vision_service = robot_system.get_optional_service(ServiceID.VISION)
    robot_config = robot_system._robot_config
    transformer = (
        HomographyTransformer(
            vision_service.camera_to_robot_matrix_path,
            tcp_x_offset=robot_config.tcp_x_offset,
            tcp_y_offset=robot_config.tcp_y_offset,
        )
        if vision_service is not None and robot_config is not None else
        HomographyTransformer(vision_service.camera_to_robot_matrix_path)
        if vision_service is not None else None
    )

    service = CalibrationApplicationService(
        vision_service=vision_service,
        process_controller=robot_system.coordinator,
        robot_service=robot_system.get_optional_service(ServiceID.ROBOT),
        height_service=getattr(robot_system, '_height_measuring_service', None),
        robot_config=robot_system._robot_config,
        calib_config=robot_system._robot_calibration,
        transformer=transformer,
        use_marker_centre=True,
    )

    jog_service = RobotJogService(robot_system.get_optional_service(ServiceID.ROBOT))
    return WidgetApplication(
        widget_factory=lambda ms: CalibrationFactory(ms,jog_service).build(service)
    )


def _build_dashboard_application(system):
    from src.applications.base.widget_application import WidgetApplication
    from src.robot_systems.glue.applications.dashboard.glue_dashboard import GlueDashboard

    coordinator = system.coordinator
    settings_service = system._settings_service
    weight_service = system.get_optional_service(ServiceID.WEIGHT)

    return WidgetApplication(
        widget_factory=lambda ms: GlueDashboard.create(
            coordinator=coordinator,
            settings_service=settings_service,
            messaging_service=ms,
            weight_service=weight_service,
        )
    )


def _build_broker_debug_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.broker_debug.broker_debug_factory import BrokerDebugFactory
    from src.applications.broker_debug.service.broker_debug_application_service import BrokerDebugApplicationService

    return WidgetApplication(
        widget_factory=lambda ms: BrokerDebugFactory(ms).build(
            BrokerDebugApplicationService(ms)
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
    return WidgetApplication(
        widget_factory=lambda ms: GlueCellSettingsFactory().build(service, ms)
    )


def _build_robot_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.robot_settings.robot_settings_factory import RobotSettingsFactory
    from src.applications.robot_settings.service.robot_settings_application_service import RobotSettingsApplicationService
    from src.robot_systems.glue.service_ids import ServiceID

    from src.applications.base.robot_jog_service import RobotJogService
    service = RobotSettingsApplicationService(
        robot_app._settings_service,
        config_key         = SettingsID.ROBOT_CONFIG,
        calibration_key    = SettingsID.ROBOT_CALIBRATION,
        robot_service      = robot_app.get_optional_service(ServiceID.ROBOT),
        tool_settings_key  = SettingsID.TOOL_CHANGER_CONFIG,
        navigation_service = robot_app.get_service(ServiceID.NAVIGATION),
    )
    jog_service = RobotJogService(robot_app.get_optional_service(ServiceID.ROBOT))
    return WidgetApplication(widget_factory=lambda ms: RobotSettingsFactory(ms, jog_service).build(service))

def _build_glue_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.robot_systems.glue.applications.glue_settings import GlueSettingsFactory, GlueSettingsApplicationService

    service = GlueSettingsApplicationService(robot_app._settings_service)
    return WidgetApplication(widget_factory=lambda _ms: GlueSettingsFactory().build(service))


def _build_modbus_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.engine.hardware.communication.modbus.modbus_action_service import ModbusActionService
    from src.applications.modbus_settings import ModbusSettingsFactory, ModbusSettingsApplicationService

    settings_service = ModbusSettingsApplicationService(
        robot_app._settings_service,
        config_key=SettingsID.MODBUS_CONFIG,
    )

    action_service = ModbusActionService()
    return WidgetApplication(
        widget_factory=lambda _ms: ModbusSettingsFactory().build(settings_service, action_service)
    )


def _build_pick_target_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.pick_target.pick_target_factory import PickTargetFactory
    from src.applications.pick_target.service.pick_target_application_service import PickTargetApplicationService
    from src.engine.vision.homography_transformer import HomographyTransformer

    vision_service = robot_system.get_optional_service(ServiceID.VISION)
    robot_service  = robot_system.get_optional_service(ServiceID.ROBOT)
    robot_config = robot_system._robot_config
    transformer = (
        HomographyTransformer(
            vision_service.camera_to_robot_matrix_path,
            tcp_x_offset=robot_config.tcp_x_offset,
            tcp_y_offset=robot_config.tcp_y_offset,
        )
        if vision_service is not None and robot_config is not None else
        HomographyTransformer(vision_service.camera_to_robot_matrix_path)
        if vision_service is not None else None
    )
    service = PickTargetApplicationService(
        vision_service=vision_service,
        robot_service=robot_service,
        transformer=transformer,
        robot_config=robot_system._robot_config,
        navigation=robot_system._navigation,
    )
    return WidgetApplication(widget_factory=lambda ms: PickTargetFactory(ms).build(service))


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
    return WidgetApplication(
        widget_factory=lambda _ms: DeviceControlFactory().build(service)
    )


def _build_height_measuring_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.height_measuring.height_measuring_factory import HeightMeasuringFactory
    from src.applications.height_measuring.service.height_measuring_application_service import (
        HeightMeasuringApplicationService,
    )

    from src.applications.base.robot_jog_service import RobotJogService
    settings_repo = robot_app._settings_service.get_repo(SettingsID.HEIGHT_MEASURING_SETTINGS)
    service = HeightMeasuringApplicationService(
        vision_service=robot_app.get_optional_service(ServiceID.VISION),
        height_measuring_service=robot_app._height_measuring_service,
        calibration_service=robot_app._height_measuring_calibration_service,
        settings_repo=settings_repo,
        laser_ops=robot_app._laser_detection_service,
    )
    jog_service = RobotJogService(robot_app.get_optional_service(ServiceID.ROBOT))
    return WidgetApplication(widget_factory=lambda ms: HeightMeasuringFactory(ms, jog_service).build(service))

