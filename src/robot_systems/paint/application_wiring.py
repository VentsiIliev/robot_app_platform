import logging
from time import perf_counter

from src.applications.workpiece_editor.editor_core.config import SegmentEditorConfig
from src.engine.common_service_ids import CommonServiceID
from src.engine.common_settings_ids import CommonSettingsID
from src.robot_systems.paint.component_ids import ServiceID, SettingsID
from src.robot_systems.paint.processes.paint.config import (
    PAINT_PROCESS_CONFIG,
    PAINT_PROJECTION_RULES,
    PaintPivotProfile,
)


_logger = logging.getLogger(__name__)
_PAINT_PROCESS = PAINT_PROCESS_CONFIG
_PAINT_EXECUTION_TARGET_POINT = "tool"


def _get_paint_process_config(robot_system=None):
    service = getattr(robot_system, "_paint_process_config_service", None) if robot_system is not None else None
    if service is not None:
        try:
            return service.get_snapshot()
        except Exception:
            _logger.debug("[PAINT_CONFIG] Failed to read live Paint process settings", exc_info=True)
    return _PAINT_PROCESS


def _get_paint_execution_target_point_name(robot_system) -> str:
    target_key = _PAINT_EXECUTION_TARGET_POINT
    return getattr(robot_system.get_target_point_definition(target_key), "name", "") or target_key


def _get_paint_base_group_id(robot_system=None) -> str:
    config = _get_paint_process_config(robot_system)
    if config.pivot_motion_plane == "xz_y_ry":
        return config.secondary_group_id
    return config.primary_group_id


def _get_pickup_base_group_id(robot_system=None) -> str:
    return _get_paint_process_config(robot_system).primary_group_id


def _get_cleanup_base_group_id(robot_system=None) -> str:
    return _get_paint_process_config(robot_system).cleanup_group_id


def _get_dropoff_group_id(robot_system=None) -> str:
    return "Dropoff"


def _get_active_work_area_id(robot_system=None) -> str:
    service = getattr(robot_system, "_work_area_service", None) if robot_system is not None else None
    if service is not None:
        try:
            return str(service.get_active_area_id() or "").strip()
        except Exception:
            _logger.debug("[TARGETING] Failed to read active work area", exc_info=True)
    return "paint"


def _get_target_frame_name_for_work_area(robot_system=None, work_area_id: str = "paint") -> str:
    frame = (
        robot_system.get_target_frame_for_work_area(work_area_id)
        if robot_system is not None and str(work_area_id or "").strip()
        else None
    )
    return str(getattr(frame, "name", "") or "").strip().lower()


def _get_active_target_frame_name(robot_system=None) -> str:
    active_area_id = _get_active_work_area_id(robot_system)
    return (
        _get_target_frame_name_for_work_area(robot_system, active_area_id)
        or _get_target_frame_name_for_work_area(robot_system, "paint")
        or "calibration"
    )


def _get_capture_group_for_work_area(robot_system=None, work_area_id: str = "paint") -> str:
    area_id = str(work_area_id or "").strip()
    frame = (
        robot_system.get_target_frame_for_work_area(area_id)
        if robot_system is not None and area_id
        else None
    )
    group_name = (
        str(getattr(frame, "target_navigation_group", "") or "").strip()
        or str(getattr(frame, "source_navigation_group", "") or "").strip()
    )
    if group_name:
        return group_name
    return "CALIBRATION" if area_id == "paint" else ""


def _get_active_capture_group(robot_system=None) -> str:
    active_area_id = _get_active_work_area_id(robot_system)
    return (
        _get_capture_group_for_work_area(robot_system, active_area_id)
        or _get_capture_group_for_work_area(robot_system, "paint")
        or "CALIBRATION"
    )


def _angle_delta_degrees(a: float, b: float) -> float:
    return abs((float(a) - float(b) + 180.0) % 360.0 - 180.0)


def _validate_active_capture_area(robot_system, area_id: str, robot_pose) -> tuple[bool, str]:
    area_id = str(area_id or "").strip()
    if not area_id:
        return False, "Active work area is unknown. Move to Calibration or Magazine before capturing."

    group_name = _get_capture_group_for_work_area(robot_system, area_id)
    if not group_name:
        return False, f"Active work area '{area_id}' has no declared capture movement group."

    if robot_pose is None or len(robot_pose) < 6:
        return False, f"Cannot verify robot pose for active work area '{area_id}'."

    navigation = getattr(robot_system, "_navigation", None) if robot_system is not None else None
    expected = navigation.get_group_position(group_name) if navigation is not None else None
    if expected is None or len(expected) < 6:
        return False, f"Movement group '{group_name}' has no configured capture position."

    expected = [float(v) for v in expected[:6]]
    pose = [float(v) for v in robot_pose[:6]]
    if group_name.upper() == "CALIBRATION":
        vision = robot_system.get_optional_service(CommonServiceID.VISION) if robot_system is not None else None
        if vision is not None:
            try:
                expected[2] += float(vision.get_capture_pos_offset() or 0.0)
            except Exception:
                _logger.debug("[VISION_GUARD] Failed to read calibration capture Z offset", exc_info=True)

    xyz_tolerance_mm = 10.0
    angle_tolerance_deg = 5.0
    axis_labels = ("X", "Y", "Z")
    for index, label in enumerate(axis_labels):
        delta = abs(pose[index] - expected[index])
        if delta > xyz_tolerance_mm:
            return (
                False,
                f"Robot is not at {group_name} for active work area '{area_id}': "
                f"{label} differs by {delta:.1f} mm.",
            )
    for index, label in ((3, "RX"), (4, "RY"), (5, "RZ")):
        delta = _angle_delta_degrees(pose[index], expected[index])
        if delta > angle_tolerance_deg:
            return (
                False,
                f"Robot is not at {group_name} for active work area '{area_id}': "
                f"{label} differs by {delta:.1f} deg.",
            )

    return True, ""


def _validate_current_capture_state(robot_system) -> tuple[bool, str]:
    work_area_service = getattr(robot_system, "_work_area_service", None) if robot_system is not None else None
    if work_area_service is None:
        return False, "Work area service is not available."
    area_id = str(work_area_service.get_active_area_id() or "").strip()
    if not area_id:
        return False, "Active work area is unknown. Move to Calibration or Magazine before starting."
    is_verified = getattr(work_area_service, "is_active_area_verified", None)
    if callable(is_verified) and not bool(is_verified()):
        return (
            False,
            f"Active work area '{area_id}' is not verified. "
            "Move the robot to the capture position from the platform before starting.",
        )
    robot_service = robot_system.get_optional_service(CommonServiceID.ROBOT) if robot_system is not None else None
    if robot_service is None:
        return False, "Robot service is not available."
    try:
        robot_pose = list(robot_service.get_current_position())
    except Exception:
        _logger.exception("[VISION_GUARD] Failed to read robot pose before process execution")
        return False, "Cannot verify robot pose before starting."
    return _validate_active_capture_area(robot_system, area_id, robot_pose)


def _get_pickup_axis_alignment_sign(robot_system=None) -> float:
    config = _get_paint_process_config(robot_system)
    return -1.0 if float(config.pickup_axis_alignment_sign_value) < 0.0 else 1.0


def _get_pivot_side(robot_system=None) -> str:
    config = _get_paint_process_config(robot_system)
    side = str(config.pivot_contact_side or "positive").strip().lower()
    if side in PAINT_PROJECTION_RULES.side_signs:
        return side
    return PAINT_PROJECTION_RULES.default_paint_side


def _get_pivot_translation_direction(robot_system=None) -> str:
    config = _get_paint_process_config(robot_system)
    direction = str(config.pivot_direction or "forward").strip().lower()
    if direction in {"positive", "+", "forward"}:
        return "forward"
    if direction in {"negative", "-", "reverse"}:
        return "reverse"
    return PAINT_PROJECTION_RULES.default_translation_direction


def _get_pivot_profile(robot_system=None) -> PaintPivotProfile:
    config = _get_paint_process_config(robot_system)
    return PaintPivotProfile(
        motion_plane=config.pivot_motion_plane,
        translation_axis=str(config.pivot_axis or "x").strip().lower(),
        translation_direction=_get_pivot_translation_direction(robot_system),
        paint_side=_get_pivot_side(robot_system),
        mirror_execution_rotation=(
            config.pivot_motion_plane == "xz_y_ry"
            and bool(config.mirror_xz_ry_execution_rotation_value)
        ),
        mirror_pickup_handoff=False,
        pickup_axis_alignment_sign=_get_pickup_axis_alignment_sign(robot_system),
    )


def _get_paint_pivot_side(robot_system=None) -> str:
    return _get_pivot_profile(robot_system).paint_side


def _build_dashboard_application(robot_system):
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.base.widget_application import WidgetApplication
    from src.robot_systems.paint.applications.dashboard import PaintDashboardFactory

    dashboard_ui_config = robot_system.ui_config
    jog_service = (
        build_robot_system_jog_service(robot_system)
        if dashboard_ui_config.show_jog_widget
        else None
    )
    return WidgetApplication(
        widget_factory=lambda ms: PaintDashboardFactory(
            ui_config=dashboard_ui_config,
        ).build(
            robot_system._dashboard_service,
            messaging=ms,
            jog_service=jog_service,
        )
    )


def _build_capture_snapshot_service(robot_system):
    from src.engine.vision.capture_snapshot_service import CaptureSnapshotService

    return CaptureSnapshotService(
        vision_service=robot_system.get_optional_service(CommonServiceID.VISION),
        robot_service=robot_system.get_optional_service(CommonServiceID.ROBOT),
        work_area_service=getattr(robot_system, "_work_area_service", None),
        active_work_area_validator=lambda area_id, robot_pose: _validate_active_capture_area(
            robot_system,
            area_id,
            robot_pose,
        ),
    )


def _build_paint_workpiece_service(robot_system):
    from src.robot_systems.paint.domain.workpieces import JsonPaintWorkpieceRepository, PaintWorkpieceService

    return PaintWorkpieceService(JsonPaintWorkpieceRepository(robot_system.workpieces_storage_path()))


def _build_paint_path_debug_dump_dir():
    import os

    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "bootstrap", "debug_plots")
    )


def _build_dryer_release_coordinator(robot_system):
    from src.robot_systems.paint.processes.paint.dryer_release_coordinator import (
        DryerReleaseCoordinator,
    )

    dryer = robot_system.get_optional_service(ServiceID.DRYER)
    return DryerReleaseCoordinator(dryer) if dryer is not None else None


def _build_paint_path_executor(robot_system):
    from src.robot_systems.paint.processes.paint.execute import (
        PaintExecutorDependencies,
        PaintExecutorContactMotionConfig,
        PaintExecutorMotionConfig,
        PaintWorkpiecePathExecutor,
    )

    robot_service = robot_system.get_optional_service(CommonServiceID.ROBOT)
    robot_config = getattr(robot_system, "_robot_config", None)
    debug_dump_dir = _build_paint_path_debug_dump_dir()
    paint_config = _get_paint_process_config(robot_system)
    pivot_profile = _get_pivot_profile(robot_system)
    dryer_release = getattr(robot_system, "_dryer_release_coordinator", None)
    dryer_ready = getattr(dryer_release, "wait_until_ready_for_release", None)
    release_callback = getattr(dryer_release, "on_workpiece_release_verified", None)

    def vacuum_pump_enabled() -> bool:
        peripheral_config = robot_system._settings_service.get(SettingsID.PERIPHERALS)
        binding = peripheral_config.peripherals.get("vacuum_pump")
        return bool(binding is not None and binding.enabled)

    dependencies = PaintExecutorDependencies(
        robot_service=robot_service,
        path_preparation_service=_build_paint_path_preparation_service(robot_system),
        pickup_base_position_provider=lambda: (
            getattr(robot_system, "_navigation", None).get_group_position(_get_pickup_base_group_id(robot_system))
            if getattr(robot_system, "_navigation", None) is not None else None
        ),
        cleanup_base_position_provider=lambda: (
            getattr(robot_system, "_navigation", None).get_group_position(_get_cleanup_base_group_id(robot_system))
            if getattr(robot_system, "_navigation", None) is not None else None
        ),
        dropoff_position_provider=lambda: (
            getattr(robot_system, "_navigation", None).get_group_position(_get_dropoff_group_id(robot_system))
            if getattr(robot_system, "_navigation", None) is not None else None
        ),
        base_position_provider=lambda: (
            getattr(robot_system, "_navigation", None).get_group_position(_get_paint_base_group_id(robot_system))
            if getattr(robot_system, "_navigation", None) is not None else None
        ),
        post_execute_callback=None,
        dryer_ready_for_release=(dryer_ready if callable(dryer_ready) else None),
        on_workpiece_release_verified=(release_callback if callable(release_callback) else None),
        calibration_position_provider=lambda: (
            getattr(robot_system, "_navigation", None).get_group_position("CALIBRATION")
            if getattr(robot_system, "_navigation", None) is not None else None
        ),
        robot_config_provider=lambda: robot_system._settings_service.get(CommonSettingsID.ROBOT_CONFIG),
        vacuum_pump=getattr(robot_system, "_vacuum_pump", None),
        vacuum_pump_enabled_provider=vacuum_pump_enabled,
        vacuum_sensor=robot_system.get_optional_service(ServiceID.VACUUM_SENSOR),
        pickup_condition=getattr(robot_system, "_pickup_condition", None),
        pickup_condition_provider=getattr(robot_system, "_get_pickup_condition", None),
        paint_process_config_service=getattr(robot_system, "_paint_process_config_service", None),
        dropoff_motion_corridor_id=getattr(robot_system, "_dropoff_motion_corridor_id", None),
    )
    motion_config = PaintExecutorMotionConfig(
        enable_vacuum_pump=paint_config.enable_vacuum_pump,
        pickup_tool=int(getattr(robot_config, "robot_tool", 0)) if robot_config is not None else 0,
        pickup_user=int(getattr(robot_config, "robot_user", 0)) if robot_config is not None else 0,
        debug_dump_dir=debug_dump_dir,
    )
    contact_motion_config = PaintExecutorContactMotionConfig(
        motion_plane=pivot_profile.motion_plane,
        translation_axis=pivot_profile.translation_axis,
        paint_side=pivot_profile.paint_side,
        translation_direction=pivot_profile.translation_direction,
        flip_xz_ry_execution_rotation_direction=pivot_profile.mirror_execution_rotation,
        mirror_xz_ry_pickup_handoff=pivot_profile.mirror_pickup_handoff,
        apply_camera_to_tcp_for_pickup=paint_config.apply_camera_to_tcp_for_pickup,
        camera_to_tcp_x_offset=float(getattr(robot_config, "camera_to_tcp_x_offset", 0.0)) if robot_config is not None else 0.0,
        camera_to_tcp_y_offset=float(getattr(robot_config, "camera_to_tcp_y_offset", 0.0)) if robot_config is not None else 0.0,
    )
    return PaintWorkpiecePathExecutor(
        dependencies=dependencies,
        motion_config=motion_config,
        contact_motion_config=contact_motion_config,
    )


def _build_paint_path_preparation_service(robot_system):
    import numpy as np

    from src.applications.workpiece_editor.editor_core.config import SegmentEditorConfig
    from src.engine.robot.path_preparation import DefaultWorkpiecePathPreparationService
    from src.robot_systems.paint.domain.contour_editor_schema import build_paint_segment_settings_schema
    from src.robot_systems.paint.processes.paint.plan.paint_contour_interpolation import (
        PaintContourInterpolation,
        PaintContourInterpolationConfig,
        resample_contour_xy,
    )

    def _pose_path_from_xy(xy_points):
        return [[float(point[0]), float(point[1]), 0.0, 0.0, 0.0, 0.0] for point in xy_points]

    def _apply_process_interpolation_settings(settings):
        interpolation = _get_paint_process_config(robot_system).interpolation
        settings["path_tangent_lookahead_mm"] = float(interpolation.path_tangent_lookahead_mm)
        settings["path_tangent_deadband_deg"] = float(interpolation.path_tangent_deadband_deg)
        return settings

    def _paint_source_contour_processor(pts_px, settings):
        started_at = perf_counter()
        _apply_process_interpolation_settings(settings)
        include_debug_paths = not bool(settings.get("_skip_debug_plot", False))
        result = PaintContourInterpolation(
            PaintContourInterpolationConfig(
                units="px",
                fit_sample_spacing=1.0,
                output_spacing=1.0,
            )
        ).build(_pose_path_from_xy(pts_px), include_debug_paths=include_debug_paths)
        output = [point[:2] for point in result.execution_path]
        _logger.info(
            "[PATH_PREP_TIMING] stage=paint_source_contour_processor "
            "elapsed_s=%.3f input_points=%d output_points=%d debug_paths=%s",
            perf_counter() - started_at,
            len(pts_px),
            len(output),
            include_debug_paths,
        )
        return output

    def _paint_mm_contour_processor(path_pts, settings):
        started_at = perf_counter()
        _apply_process_interpolation_settings(settings)
        resample_start = perf_counter()
        resampled_xy = resample_contour_xy(
            np.asarray(path_pts, dtype=float)[:, :2],
            spacing=1.0,
            closed=True,
        )
        _logger.info(
            "[PATH_PREP_TIMING] stage=paint_mm_resample_contour_xy "
            "elapsed_s=%.3f input_points=%d output_points=%d",
            perf_counter() - resample_start,
            len(path_pts),
            len(resampled_xy),
        )
        _logger.info(
            "[PATH_PREP_TIMING] stage=paint_mm_contour_processor "
            "elapsed_s=%.3f input_points=%d output_points=%d",
            perf_counter() - started_at,
            len(path_pts),
            len(resampled_xy),
        )
        return {
            "method": "paint_mm_1mm_resample",
            "prepared_xy": resampled_xy.tolist(),
            "curve_xy": resampled_xy.tolist(),
        }

    def _paint_contour_processor(path_pts, settings):
        """Backward-compatible name for the mm-only contour processor."""
        return _paint_mm_contour_processor(path_pts, settings)

    robot_config = getattr(robot_system, "_robot_config", None)
    execution_target_point_name = _get_paint_execution_target_point_name(robot_system)
    calibration_frame_name = _get_active_target_frame_name(robot_system)
    z_min = 0.0
    if robot_config is not None:
        try:
            z_min = float(robot_config.safety_limits.z_min)
        except Exception:
            z_min = 0.0
    segment_config = SegmentEditorConfig(schema=build_paint_segment_settings_schema())
    debug_dump_dir = _build_paint_path_debug_dump_dir()
    if _PAINT_PROCESS.enable_z_shift_pixel_compensation:
        pixel_height_compensation_fn = (
            lambda height_mm: (
                float(getattr(robot_config, "camera_z_shift_x_per_mm_px", 0.0)) * float(height_mm),
                float(getattr(robot_config, "camera_z_shift_y_per_mm_px", 0.0)) * float(height_mm),
            )
            if robot_config is not None else (0.0, 0.0)
        )
    else:
        pixel_height_compensation_fn = lambda _height_mm: (0.0, 0.0)
    return DefaultWorkpiecePathPreparationService(
        logger=_logger,
        segment_config=segment_config,
        transformer=None,
        resolver=None,
        transformer_getter=lambda: robot_system.get_shared_vision_resolver()[0],
        resolver_getter=lambda: robot_system.get_shared_vision_resolver()[1],
        z_min=z_min,
        rz_mode="path_tangent",
        execute_from_workpiece_layer=True,
        target_point_name=execution_target_point_name,
        pickup_target_point_name=execution_target_point_name,
        calibration_frame_name=calibration_frame_name,
        calibration_frame_name_getter=lambda: _get_active_target_frame_name(robot_system),
        pixel_height_compensation_fn=pixel_height_compensation_fn,
        pickup_axis_alignment_sign=_get_pickup_axis_alignment_sign(robot_system),
        pixel_to_mm_mode=_PAINT_PROCESS.contour_pixel_to_mm_mode,
        debug_plot_dir=debug_dump_dir,
        base_position_provider=lambda: (
            getattr(robot_system, "_navigation", None).get_group_position(_get_pickup_base_group_id(robot_system))
            if getattr(robot_system, "_navigation", None) is not None else None
        ),
        source_contour_processor=_paint_source_contour_processor,
        contour_processor=_paint_contour_processor,
    )


def _build_paint_matching_service(robot_system, workpiece_service=None, capture_snapshot_service=None):
    from src.robot_systems.paint.processes.paint.match.workpiece_matching_service import PaintWorkpieceMatchingService

    vision_service = robot_system.get_optional_service(CommonServiceID.VISION)
    return PaintWorkpieceMatchingService(
        list_saved_workpieces_fn=(workpiece_service or _build_paint_workpiece_service(robot_system)).list_all,
        load_saved_workpiece_fn=(workpiece_service or _build_paint_workpiece_service(robot_system)).load_raw,
        run_matching_fn=vision_service.run_matching if vision_service is not None else None,
        capture_snapshot_service=capture_snapshot_service or _build_capture_snapshot_service(robot_system),
    )


def _build_paint_workpiece_preparation_service(robot_system):
    from src.robot_systems.paint.processes.paint.plan import PaintWorkpiecePreparationService
    from src.robot_systems.paint.domain.contour_editor_schema import build_paint_segment_settings_schema

    segment_defaults = build_paint_segment_settings_schema().get_defaults()

    def live_segment_defaults() -> dict:
        config = robot_system._paint_process_config_service.get_snapshot()
        return {
            **segment_defaults,
            "velocity": float(config.default_paint_velocity_percent),
            "acceleration": float(config.default_paint_acceleration_percent),
            "offset": float(config.default_paint_offset_mm),
        }

    return PaintWorkpiecePreparationService(
        can_match_fn=_build_paint_matching_service(robot_system).can_match_saved_workpieces,
        match_workpiece_fn=_build_paint_matching_service(robot_system).match_saved_workpieces,
        default_settings=segment_defaults,
        default_settings_getter=live_segment_defaults,
        transformer=None,
        transformer_getter=lambda: robot_system.get_shared_vision_resolver()[0],
    )


def _build_paint_magazine_load_service(robot_system):
    from src.robot_systems.paint.processes.paint.magazine_load_service import PaintMagazineLoadService

    return PaintMagazineLoadService(
        navigation=robot_system._navigation,
        capture_snapshot_service=robot_system._paint_capture_snapshot_service,
        path_executor=robot_system._paint_path_executor,
        resolver_getter=lambda: robot_system.get_shared_vision_resolver()[1],
        work_area_service=getattr(robot_system, "_work_area_service", None),
        target_point_name=_get_paint_execution_target_point_name(robot_system),
        camera_point_name="camera",
        frame_name="magazine",
        release_work_area_id="paint",
        release_frame_name="calibration",
    )


def _build_paint_workpiece_editor_service(robot_system):
    from src.applications.workpiece_editor.service.workpiece_editor_service import (
        WorkpieceEditorOptions,
        WorkpieceEditorServices,
        WorkpieceEditorService,
        WorkpieceEditorStorage,
    )
    from src.robot_systems.paint.domain.paint_workpiece_editor_adapter import PaintWorkpieceEditorAdapter
    from src.robot_systems.paint.domain.contour_editor_schema import (
        build_paint_contour_form_schema,
        build_paint_segment_settings_schema,
    )

    vision_service = robot_system.get_optional_service(CommonServiceID.VISION)
    capture_snapshot_service = _build_capture_snapshot_service(robot_system)
    robot_service = robot_system.get_optional_service(CommonServiceID.ROBOT)
    segment_config = build_paint_segment_settings_schema()
    workpiece_service = _build_paint_workpiece_service(robot_system)
    matching_service = _build_paint_matching_service(
        robot_system,
        workpiece_service=workpiece_service,
        capture_snapshot_service=capture_snapshot_service,
    )
    path_preparation_service = _build_paint_path_preparation_service(robot_system)
    path_executor = _build_paint_path_executor(robot_system)
    debug_dump_dir = _build_paint_path_debug_dump_dir()

    def _save_fn(data: dict) -> tuple[bool, str]:
        return workpiece_service.save(data)

    def _update_fn(storage_id: str, data: dict) -> tuple[bool, str]:
        return workpiece_service.update(storage_id, data)

    def _id_exists_fn(contour_id: str) -> bool:
        return workpiece_service.workpiece_id_exists(contour_id)

    return WorkpieceEditorService(
        storage=WorkpieceEditorStorage(
            save_fn=_save_fn,
            update_fn=_update_fn,
            id_exists_fn=_id_exists_fn,
        ),
        services=WorkpieceEditorServices(
            vision_service=vision_service,
            capture_snapshot_service=capture_snapshot_service,
            robot_service=robot_service,
            transformer=None,
            transformer_getter=lambda: robot_system.get_shared_vision_resolver()[0],
            path_executor=path_executor,
            path_preparation_service=path_preparation_service,
            matching_service=matching_service,
            workpiece_data_adapter=PaintWorkpieceEditorAdapter(),
            process_execution_validator=lambda: _validate_current_capture_state(robot_system),
        ),
        form_schema=build_paint_contour_form_schema(),
        segment_config=SegmentEditorConfig(schema=segment_config),
        options=WorkpieceEditorOptions(
            debug_dump_dir=debug_dump_dir,
        ),
    )


def _build_paint_contour_editor_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.workpiece_editor.workpiece_editor_factory import WorkpieceEditorFactory

    service = _build_paint_workpiece_editor_service(robot_system)

    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: WorkpieceEditorFactory().build(
            service,
            messaging=ms,
            jog_service=jog_service,
        )
    )


def _build_paint_process_settings_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.robot_systems.paint.applications.paint_process_settings.paint_process_settings_factory import (
        PaintProcessSettingsFactory,
    )
    from src.robot_systems.paint.applications.paint_process_settings.service.paint_process_settings_application_service import (
        PaintProcessSettingsApplicationService,
    )

    service = PaintProcessSettingsApplicationService(
        process_config_service=robot_system._paint_process_config_service,
        dropoff_group_provider=lambda: (
            robot_system._settings_service.get(CommonSettingsID.MOVEMENT_GROUPS).movement_groups.get("Dropoff")
        ),
        current_position_provider=lambda: (
            robot_system.get_optional_service(CommonServiceID.ROBOT).get_current_position()
            if robot_system.get_optional_service(CommonServiceID.ROBOT) is not None
            else None
        ),
        robot_service_provider=lambda: robot_system.get_optional_service(CommonServiceID.ROBOT),
        robot_config_provider=lambda: robot_system._settings_service.get(CommonSettingsID.ROBOT_CONFIG),
        robot_tool=int(getattr(getattr(robot_system, "_robot_config", None), "robot_tool", 0)),
        robot_user=int(getattr(getattr(robot_system, "_robot_config", None), "robot_user", 0)),
        peripherals_provider=lambda: robot_system._settings_service.get(SettingsID.PERIPHERALS),
    )
    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: PaintProcessSettingsFactory().build(service, messaging=ms, jog_service=jog_service)
    )


def _build_paint_motion_recipe_application(robot_system):
    import os

    from src.applications.base.widget_application import WidgetApplication
    from src.robot_systems.paint.applications.paint_motion_recipe import PaintMotionRecipeFactory
    from src.robot_systems.paint.applications.paint_motion_recipe.service import PaintMotionRecipeService

    recipe_path = os.path.join(
        os.path.dirname(__file__),
        "storage",
        "settings",
        "paint",
        "dev_motion_recipe.json",
    )
    service = PaintMotionRecipeService(
        recipe_path=recipe_path,
        group_ids=[
            definition.id
            for definition in robot_system.get_movement_group_definitions()
        ],
        navigation_service=getattr(robot_system, "_navigation", None),
    )
    return WidgetApplication(
        widget_factory=lambda _ms: PaintMotionRecipeFactory().build(service)
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


def _build_paint_motion_plane_setup_application(robot_system):
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.base.widget_application import WidgetApplication
    from src.robot_systems.paint.applications.paint_motion_plane_setup import PaintMotionPlaneSetupFactory
    from src.robot_systems.paint.applications.paint_motion_plane_setup.service.paint_motion_plane_setup_service import (
        PaintMotionPlaneSetupService,
    )

    service = PaintMotionPlaneSetupService(
        robot_service=robot_system.get_optional_service(CommonServiceID.ROBOT),
        navigation_service=getattr(robot_system, "_navigation", None),
        paint_group_ids=[
            _get_paint_process_config(robot_system).primary_group_id,
            _get_paint_process_config(robot_system).secondary_group_id,
        ],
    )
    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: PaintMotionPlaneSetupFactory().build(
            service,
            messaging=ms,
            jog_service=jog_service,
        )
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

    service = CalibrationSettingsApplicationService(
        robot_system._settings_service,
        vision_service=robot_system.get_optional_service(CommonServiceID.VISION),
        robot_service=getattr(robot_system, "_robot", None),
        messaging=getattr(robot_system, "_messaging_service", None),
    )
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
    from src.engine.robot.calibration.camera_z_shift_calibration_service import (
        CameraZShiftCalibrationService,
    )
    from src.engine.robot.calibration.calibration_navigation_service import CalibrationNavigationService
    from src.engine.robot.calibration.ros_tool_registry_client import RosToolRegistryClient
    from src.engine.robot.calibration.tool_tcp_calibration_service import ToolTcpCalibrationService
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
            on_offsets_saved=robot_system.invalidate_shared_vision_resolver,
        )
        if vision_service is not None and robot_service is not None and robot_config is not None else None
    )
    camera_z_shift_calibrator = (
        CameraZShiftCalibrationService(
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

    ros_tool_registry_client = RosToolRegistryClient()
    tool_tcp_calibrator = ToolTcpCalibrationService(
        robot_service=robot_service,
        tool_registry_client=ros_tool_registry_client,
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
        camera_z_shift_calibrator=camera_z_shift_calibrator,
        marker_height_mapping_service=marker_height_mapping_service,
        intrinsic_capture_service=intrinsic_capture_service,
        tool_tcp_calibrator=tool_tcp_calibrator,
        calibration_settings_service=CalibrationSettingsApplicationService(
            robot_system._settings_service,
            robot_service=robot_service,
            messaging=getattr(robot_system, "_messaging_service", None),
        ),
        settings_service=robot_system._settings_service,
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


def _build_modbus_settings_application(robot_app):
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.modbus_settings import ModbusSettingsApplicationService, ModbusSettingsFactory
    from src.engine.hardware.communication.modbus.modbus_action_service import ModbusActionService

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


def _build_dryer_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.dryer_settings import DryerSettingsApplicationService, DryerSettingsFactory
    from src.robot_systems.paint.component_ids import ServiceID, SettingsID

    service = DryerSettingsApplicationService(
        settings_service=robot_app._settings_service,
        dryer_config_key=SettingsID.DRYER_CONFIG,
        modbus_config_key=CommonSettingsID.MODBUS_CONFIG,
        peripherals_config_key=SettingsID.PERIPHERALS,
        live_controller=robot_app.get_optional_service(ServiceID.DRYER),
    )
    return WidgetApplication(
        widget_factory=lambda _ms: DryerSettingsFactory().build(service)
    )


def _build_device_control_application(robot_system):
    """Build the shared dynamic device-control app from configured peripherals."""
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.device_control.device_control_factory import DeviceControlFactory
    from src.applications.device_control.service.device_control_application_service import (
        DeviceControlApplicationService,
    )
    from src.engine.hardware.peripherals.device_control_adapters import (
        build_device_control_adapters,
    )
    from src.robot_systems.paint.component_ids import ServiceID, SettingsID

    peripheral_config = robot_system._settings_service.get(SettingsID.PERIPHERALS)

    def persist_enabled(device_key: str, enabled: bool) -> None:
        from src.engine.hardware.peripherals import PeripheralBinding, PeripheralConfig

        current_config = robot_system._settings_service.get(SettingsID.PERIPHERALS)
        current = current_config.peripherals.get(device_key)
        if current is None:
            raise KeyError(f"Peripheral is not configured: {device_key}")
        updated = PeripheralBinding(
            slave_id=current.slave_id,
            enabled=enabled,
            inputs=current.inputs,
            outputs=current.outputs,
            commands=current.commands,
        )
        robot_system._settings_service.save(
            SettingsID.PERIPHERALS,
            PeripheralConfig({**current_config.peripherals, device_key: updated}),
        )
    services = {
        "vacuum_pump": robot_system.get_optional_service(ServiceID.VACUUM_PUMP),
        "fan": robot_system.get_optional_service(ServiceID.FAN),
        "vacuum_sensor": robot_system.get_optional_service(ServiceID.VACUUM_SENSOR),
        "physical_control_buttons": robot_system.get_optional_service(ServiceID.PHYSICAL_CONTROL_BUTTONS),
        "dryer": robot_system.get_optional_service(ServiceID.DRYER),
        "laser": getattr(robot_system, "_laser_detection_service", None),
    }
    devices = build_device_control_adapters(peripheral_config, services, persist_enabled)
    service = DeviceControlApplicationService(motors=[], devices=devices)
    return WidgetApplication(
        widget_factory=lambda _ms: DeviceControlFactory().build(service)
    )


def _build_ethercat_diagnostics_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.ethercat_diagnostics import EthercatDiagnosticsFactory
    from src.applications.ethercat_diagnostics.service import IghEthercatDiagnosticsService

    service = IghEthercatDiagnosticsService()
    return WidgetApplication(
        widget_factory=lambda ms: EthercatDiagnosticsFactory().build(service, messaging=ms)
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
    from src.applications.hand_eye_calibration.service.hand_eye_service import HandEyeCalibrationService
    from src.applications.hand_eye_calibration.hand_eye_calibration_factory import HandEyeCalibrationFactory

    def _factory(ms):
        snapshot_svc = _build_capture_snapshot_service(robot_system)
        service = HandEyeCalibrationService(
            snapshot_service=snapshot_svc,
            robot_service=robot_system.get_optional_service(CommonServiceID.ROBOT),
            vision_service=robot_system.get_optional_service(CommonServiceID.VISION),
            robot_config=robot_system._robot_config,
            messaging=ms,
        )
        return HandEyeCalibrationFactory().build(service, messaging=ms)

    return WidgetApplication(widget_factory=_factory)


def _build_pick_target_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.pick_target.pick_target_factory import PickTargetFactory
    from src.applications.pick_target.service.pick_target_application_service import PickTargetApplicationService

    vision_service = robot_system.get_optional_service(CommonServiceID.VISION)
    capture_snapshot_service = _build_capture_snapshot_service(robot_system)
    robot_service = robot_system.get_optional_service(CommonServiceID.ROBOT)
    height_service = getattr(robot_system, "_height_measuring_service", None)
    default_target_name = (
        robot_system.get_targeting_provider().get_default_target_name()
        if robot_system.get_targeting_provider() is not None else ""
    )
    calibration_frame_name = _get_active_target_frame_name(robot_system)
    service = PickTargetApplicationService(
        vision_service=vision_service,
        capture_snapshot_service=capture_snapshot_service,
        robot_service=robot_service,
        resolver=None,
        resolver_getter=lambda: robot_system.get_shared_vision_resolver()[1],
        robot_config=robot_system._robot_config,
        navigation=robot_system._navigation,
        height_measuring=height_service,
        default_target_name=default_target_name,
        calibration_frame_name=calibration_frame_name,
        pickup_frame_name="",
        active_frame_name_getter=lambda: _get_active_target_frame_name(robot_system),
        active_capture_group_getter=lambda: _get_active_capture_group(robot_system),
    )
    jog_service = build_robot_system_jog_service(
        robot_system,
        reference_rz_provider=service.get_jog_reference_rz,
    )
    return WidgetApplication(
        widget_factory=lambda ms: PickTargetFactory().build(service, messaging=ms, jog_service=jog_service)
    )
