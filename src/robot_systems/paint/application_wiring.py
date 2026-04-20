import logging

from src.engine.common_service_ids import CommonServiceID
from src.engine.common_settings_ids import CommonSettingsID


_logger = logging.getLogger(__name__)


def _build_dashboard_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.robot_systems.paint.applications.dashboard import PaintDashboardFactory

    return WidgetApplication(
        widget_factory=lambda ms: PaintDashboardFactory().build(
            robot_system._dashboard_service,
            messaging=ms,
        )
    )


def _build_capture_snapshot_service(robot_system):
    from src.engine.vision.capture_snapshot_service import CaptureSnapshotService

    return CaptureSnapshotService(
        vision_service=robot_system.get_optional_service(CommonServiceID.VISION),
        robot_service=robot_system.get_optional_service(CommonServiceID.ROBOT),
    )


def _build_paint_contour_editor_application(robot_system):
    import os
    from contour_editor import AdditionalFormBehaviorProvider

    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.workpiece_editor.editor_core.config import SegmentEditorConfig
    from src.applications.workpiece_editor.service.workpiece_editor_service import WorkpieceEditorService
    from src.applications.workpiece_editor.workpiece_editor_factory import WorkpieceEditorFactory
    from src.robot_systems.paint.domain.workpieces import JsonPaintWorkpieceRepository, PaintWorkpieceService
    from src.robot_systems.paint.domain.dxf_path_form_behavior import PaintDxfPathFormBehavior
    from src.robot_systems.paint.workpiece_path_executor import PaintWorkpiecePathExecutor
    from src.robot_systems.paint.domain.contour_editor_schema import (
        build_paint_contour_form_schema,
        build_paint_segment_settings_schema,
    )
    from src.engine.cad import import_dxf_to_workpiece_data

    vision_service = robot_system.get_optional_service(CommonServiceID.VISION)
    capture_snapshot_service = _build_capture_snapshot_service(robot_system)
    robot_service = robot_system.get_optional_service(CommonServiceID.ROBOT)
    robot_config = getattr(robot_system, "_robot_config", None)
    transformer, resolver = robot_system.get_shared_vision_resolver()
    camera_point_name = (
        getattr(robot_system.get_target_point_definition("camera"), "name", "") or ""
    )
    workpiece_service = PaintWorkpieceService(JsonPaintWorkpieceRepository(robot_system.workpieces_storage_path()))
    debug_dump_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "bootstrap", "debug_plots")
    )

    def _save_fn(data: dict) -> tuple[bool, str]:
        return workpiece_service.save(data)

    def _update_fn(storage_id: str, data: dict) -> tuple[bool, str]:
        return workpiece_service.update(storage_id, data)

    def _id_exists_fn(contour_id: str) -> bool:
        return workpiece_service.workpiece_id_exists(contour_id)

    z_min = 0.0
    if robot_config is not None:
        try:
            z_min = float(robot_config.safety_limits.z_min)
        except Exception:
            z_min = 0.0

    service = WorkpieceEditorService(
        vision_service=vision_service,
        capture_snapshot_service=capture_snapshot_service,
        save_fn=_save_fn,
        update_fn=_update_fn,
        form_schema=build_paint_contour_form_schema(),
        segment_config=SegmentEditorConfig(schema=build_paint_segment_settings_schema()),
        id_exists_fn=_id_exists_fn,
        transformer=transformer,
        resolver=resolver,
        z_min=z_min,
        rz_mode="path_tangent",
        debug_dump_dir=debug_dump_dir,
        robot_service=robot_service,
        path_executor=PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            base_position_provider=lambda: (
                getattr(robot_system, "_navigation", None).get_group_position("PAINTING")
                if getattr(robot_system, "_navigation", None) is not None else None
            ),
            post_execute_callback=lambda: (
                getattr(robot_system, "_navigation", None).move_to_calibration_position()
                if getattr(robot_system, "_navigation", None) is not None else False
            ),
            pickup_tool=int(getattr(robot_config, "robot_tool", 0)) if robot_config is not None else 0,
            pickup_user=int(getattr(robot_config, "robot_user", 0)) if robot_config is not None else 0,
            debug_dump_dir=debug_dump_dir,
        ),
        target_point_name=camera_point_name,
        enable_dxf_import_test=True,
        execute_from_workpiece_layer=True,
        list_saved_workpieces_fn=workpiece_service.list_all,
        load_saved_workpiece_fn=workpiece_service.load_raw,
        run_matching_fn=vision_service.run_matching if vision_service is not None else None,
    )

    AdditionalFormBehaviorProvider.get().set_behaviors(
        [
            PaintDxfPathFormBehavior(
                prepare_dxf_raw_for_image=service.prepare_dxf_test_raw_for_image,
                dxf_importer=import_dxf_to_workpiece_data,
            )
        ]
    )

    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: WorkpieceEditorFactory().build(
            service,
            messaging=ms,
            jog_service=jog_service,
        )
    )


def _build_workpiece_library_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.workpiece_library.workpiece_library_factory import WorkpieceLibraryFactory
    from src.robot_systems.paint.domain.workpieces import (
        JsonPaintWorkpieceRepository,
        PaintWorkpieceLibraryService,
        PaintWorkpieceService,
    )

    service = PaintWorkpieceLibraryService(
        PaintWorkpieceService(
            JsonPaintWorkpieceRepository(robot_system.workpieces_storage_path())
        )
    )
    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: WorkpieceLibraryFactory().build(service, ms, jog_service=jog_service)
    )


def _build_user_management_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.user_management.user_management_factory import UserManagementFactory
    from src.applications.user_management.service.user_management_application_service import \
        UserManagementApplicationService
    from src.applications.user_management.domain.csv_user_repository import CsvUserRepository
    from src.engine.auth.json_permissions_repository import JsonPermissionsRepository
    from src.robot_systems.paint.domain.users import build_paint_user_schema
    from src.engine.auth.authorization_service import AuthorizationService

    role_policy = robot_system.__class__.role_policy
    service = UserManagementApplicationService(
        CsvUserRepository(
            robot_system.users_storage_path(),
            build_paint_user_schema(role_policy.role_values),
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
        before_move=(lambda: work_area_service.set_active_area_id("paint")),
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
            settings_service=robot_system._settings_service,
        )
        if vision_service is not None and robot_service is not None and robot_config is not None else None
    )

    def _observer_position(group_id: str):
        navigation = getattr(robot_system, "_navigation", None)
        return navigation.get_group_position(group_id) if navigation is not None else None

    service = CalibrationApplicationService(
        vision_service=vision_service,
        process_controller=robot_system._calibration_coordinator,
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


def _build_robot_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.robot_settings.robot_settings_factory import RobotSettingsFactory
    from src.applications.robot_settings.service.robot_settings_application_service import \
        RobotSettingsApplicationService
    from src.robot_systems.paint.targeting.settings_adapter import from_editor_dict, to_editor_dict

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
        settings_service=robot_system._settings_service,
    )
    return WidgetApplication(
        widget_factory=lambda ms: IntrinsicCaptureFactory().build(service, messaging=ms)
    )


def _build_hand_eye_calibration_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.engine.vision.capture_snapshot_service import CaptureSnapshotService
    from src.applications.hand_eye_calibration.service.hand_eye_service import HandEyeCalibrationService
    from src.applications.hand_eye_calibration.hand_eye_calibration_factory import HandEyeCalibrationFactory

    def _factory(ms):
        snapshot_svc = CaptureSnapshotService(
            vision_service=robot_system.get_optional_service(CommonServiceID.VISION),
            robot_service=robot_system.get_optional_service(CommonServiceID.ROBOT),
        )
        service = HandEyeCalibrationService(
            snapshot_service=snapshot_svc,
            robot_service=robot_system.get_optional_service(CommonServiceID.ROBOT),
            vision_service=robot_system.get_optional_service(CommonServiceID.VISION),
            robot_config=robot_system._robot_config,
            messaging=ms,
        )
        return HandEyeCalibrationFactory().build(service, messaging=ms)

    return WidgetApplication(widget_factory=_factory)
