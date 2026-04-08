"""
Refactored Robot Calibration using ExecutableStateMachine

This module provides a refactored version of the robot calibration vision_service
that uses the ExecutableStateMachine for better separation of concerns,
maintainability, and consistency with other vision_service components.
"""

import time
import numpy as np
import logging

from src.engine.process.executable_state_machine import ExecutableStateMachine, StateRegistry, State, \
    ExecutableStateMachineBuilder
from src.engine.robot.calibration.robot_calibration.states.handle_height_sample_state import handle_height_sample_state

from src.engine.robot.calibration.robot_calibration import metrics
from src.engine.robot.calibration.robot_calibration.CalibrationVision import CalibrationVision
from src.engine.robot.calibration.robot_calibration.config_helpers import (
    RobotCalibrationEventsConfig, 
    RobotCalibrationConfig, 
    AdaptiveMovementConfig
)
from src.engine.robot.calibration.robot_calibration.logging import (
    get_log_timing_summary, 
)
from src.engine.robot.calibration.robot_calibration.model_fitting import (
    build_calibration_dataset,
    build_calibration_model,
)
from src.engine.robot.calibration.robot_calibration.calibration_report import (
    build_calibration_reports,
    save_calibration_model_report,
    save_homography_residual_artifact,
)
from src.engine.robot.calibration.robot_calibration.live_feed import (
    stop_live_feed_thread,
)
from src.engine.robot.calibration.robot_calibration.robot_controller import CalibrationRobotController
from src.engine.robot.calibration.robot_calibration.RobotCalibrationContext import RobotCalibrationContext

# Import all state handlers
from src.engine.robot.calibration.robot_calibration.states.initializing import handle_initializing_state
from src.engine.robot.calibration.robot_calibration.states.axis_mapping import handle_axis_mapping_state
from src.engine.robot.calibration.robot_calibration.states.looking_for_chessboard_handler import handle_looking_for_chessboard_state
from src.engine.robot.calibration.robot_calibration.states.chessboard_found_handler import handle_chessboard_found_state
from src.engine.robot.calibration.robot_calibration.states.looking_for_aruco_markers_handler import (
    handle_looking_for_aruco_markers_state,
)
from src.engine.robot.calibration.robot_calibration.states.all_aruco_found_handler import handle_all_aruco_found_state
from src.engine.robot.calibration.robot_calibration.states.compute_offsets_handler import handle_compute_offsets_state
from src.engine.robot.calibration.robot_calibration.states.align_robot import (
    handle_align_robot_state,
)
from src.engine.robot.calibration.robot_calibration.states.error_handling import (
    set_calibration_error,
)
from src.engine.robot.calibration.robot_calibration.states.iterate_alignment import (
    handle_iterate_alignment_state,
)
from src.engine.robot.calibration.robot_calibration.states.tcp_offset_state import (
    handle_capture_tcp_offset_state,
)
from src.engine.robot.calibration.robot_calibration.states.terminal_states import (
    handle_done_state,
    handle_error_state,
)

# Import state machine components
from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import (
    RobotCalibrationStates, 
    RobotCalibrationTransitionRules
)

# TODO: wire IMessagingService from the platform once integrated

_logger = logging.getLogger(__name__)


class RefactoredRobotCalibrationPipeline:
    """
    Refactored robot calibration pipeline using ExecutableStateMachine.
    
    This class provides the same functionality as the original pipeline
    but with better separation of concerns and maintainability.
    """

    def __init__(self, 
                 config: RobotCalibrationConfig,
                 adaptive_movement_config: AdaptiveMovementConfig = None,
                 events_config: RobotCalibrationEventsConfig = None):
        """
        Initialize the refactored calibration pipeline.
        
        Args:
            config: Main calibration configuration
            adaptive_movement_config: Movement adaptation settings
            events_config: Event broadcasting configuration
        """
        self.calibration_context = RobotCalibrationContext()
        self._setup_context(config, adaptive_movement_config, events_config)
        self.calibration_state_machine = self._create_state_machine()

        _logger.info(f"RefactoredRobotCalibrationPipeline initialized with {len(config.required_ids)} markers")


    def _setup_context(self, 
                      config: RobotCalibrationConfig,
                      adaptive_movement_config: AdaptiveMovementConfig,
                      events_config: RobotCalibrationEventsConfig):
        """Set up the calibration context with configuration data"""
        context = self.calibration_context
        
        # Basic configuration
        context.debug = config.debug
        context.step_by_step = config.step_by_step
        context.live_visualization = config.live_visualization
        context.vision_service = config.vision_service
        context.required_ids = set(config.required_ids)
        context.candidate_ids = set(getattr(config, "candidate_ids", []) or config.required_ids)
        context.min_target_separation_px = float(getattr(config, "min_target_separation_px", 120.0))
        context.homography_target_count = max(
            4,
            int(getattr(config, "homography_target_count", 16) or 16),
        )
        context.residual_target_count = max(
            0,
            int(getattr(config, "residual_target_count", 14) or 0),
        )
        context.validation_target_count = max(
            0,
            int(getattr(config, "validation_target_count", 6) or 0),
        )
        context.auto_skip_known_unreachable_markers = bool(
            getattr(config, "auto_skip_known_unreachable_markers", True)
        )
        context.unreachable_marker_failure_threshold = max(
            1,
            int(getattr(config, "unreachable_marker_failure_threshold", 1) or 1),
        )
        context.known_unreachable_marker_ids = {
            int(marker_id)
            for marker_id in (getattr(config, "known_unreachable_marker_ids", []) or [])
        }
        context.unreachable_marker_failure_counts = {
            int(marker_id): int(count)
            for marker_id, count in (getattr(config, "unreachable_marker_failure_counts", {}) or {}).items()
        }
        context.Z_target = config.z_target
        context.axis_mapping_config = config.axis_mapping_config
        context.use_marker_centre = getattr(config, 'use_marker_centre', False)
        context.reference_board_mode = str(getattr(config, "reference_board_mode", "auto") or "auto").lower()
        context.use_ransac = getattr(config, 'use_ransac', False)
        context.camera_tcp_offset_config = getattr(config, "camera_tcp_offset_config", None)
        context.run_height_measurement = getattr(config, "run_height_measurement", True)
        context.settings_service = getattr(config, "settings_service", None)
        context.calibration_settings_key = getattr(config, "calibration_settings_key", None)
        context.robot_config = getattr(config, "robot_config", None)
        context.robot_config_key = getattr(config, "robot_config_key", None)

        # Laser Detection/Height measuring service
        context.height_measuring_service = config.height_measuring_service

        # Camera configuration
        context.vision_service.set_draw_contours(False)
        context.chessboard_size = (
            context.vision_service.get_chessboard_width(),
            context.vision_service.get_chessboard_height()
        )
        context.square_size_mm = context.vision_service.get_square_size_mm()
        charuco_w = getattr(config, "charuco_board_width", None)
        charuco_h = getattr(config, "charuco_board_height", None)
        charuco_sq = getattr(config, "charuco_square_size_mm", None)
        context.charuco_board_size = (int(charuco_w), int(charuco_h)) if charuco_w and charuco_h else None
        if charuco_sq:
            context.square_size_mm = float(charuco_sq)
        context.charuco_marker_size_mm = (
            float(getattr(config, "charuco_marker_size_mm", 0.0) or 0.0) or None
        )

        _logger.info(
            "Robot calibration board config loaded: reference_board_mode=%s chessboard_size=%s chessboard_square_mm=%.3f charuco_board_size=%s charuco_square_mm=%s charuco_marker_mm=%s",
            context.reference_board_mode,
            context.chessboard_size,
            float(context.vision_service.get_square_size_mm()),
            context.charuco_board_size,
            (
                f"{float(getattr(config, 'charuco_square_size_mm', 0.0)):.3f}"
                if getattr(config, 'charuco_square_size_mm', None)
                else 'fallback-to-chessboard-square'
            ),
            (
                f"{float(context.charuco_marker_size_mm):.3f}"
                if context.charuco_marker_size_mm is not None
                else 'auto(0.75*square)'
            ),
        )

        # Adaptive movement configuration
        if adaptive_movement_config:
            context.alignment_threshold_mm = adaptive_movement_config.target_error_mm
            context.fast_iteration_wait = adaptive_movement_config.fast_iteration_wait
            context.post_align_settle_s = getattr(adaptive_movement_config, "post_align_settle_s", 0.3)

        # Event configuration
        if events_config:
            context.broker = events_config.broker
            context.BROADCAST_TOPIC = events_config.calibration_log_topic
            context.CALIBRATION_START_TOPIC = events_config.calibration_start_topic
            context.CALIBRATION_STOP_TOPIC = events_config.calibration_stop_topic
            context.CALIBRATION_IMAGE_TOPIC = events_config.calibration_image_topic
            context.broadcast_events = True
        else:
            context.broadcast_events = False

        # Initialize robot controller
        context.calibration_robot_controller = CalibrationRobotController(
            config.robot_service,
            config.navigation_service,
            config.robot_tool,
            config.robot_user,
            adaptive_movement_config,
            velocity=config.travel_velocity,
            acceleration=config.travel_acceleration,
            iterative_velocity=config.iterative_velocity,
            iterative_acceleration=config.iterative_acceleration,
        )
        context.calibration_robot_controller.move_to_calibration_position()

        # Initialize supporting components
        context.calibration_vision = CalibrationVision(
            context.vision_service,
            context.chessboard_size,
            context.square_size_mm,
            context.candidate_ids,
            context.debug,
            use_marker_centre=context.use_marker_centre,
            reference_board_mode=context.reference_board_mode,
            charuco_board_size=context.charuco_board_size,
            charuco_marker_size_mm=context.charuco_marker_size_mm,
        )

        # Z-axis calculations
        context.Z_current = context.calibration_robot_controller.get_current_z_value()
        context.ppm_scale = context.Z_current / context.Z_target

        _logger.info(f"Z_current: {context.Z_current}, Z_target: {context.Z_target}, ppm_scale: {context.ppm_scale}")


    def _create_state_machine(self) -> ExecutableStateMachine:
        """Create and configure the executable state machine"""
        
        # Create a state handlers map
        state_handlers_map = {
            RobotCalibrationStates.INITIALIZING: self._handle_initializing,
            RobotCalibrationStates.AXIS_MAPPING: self._handle_axis_mapping,
            RobotCalibrationStates.LOOKING_FOR_CHESSBOARD: self._handle_looking_for_chessboard,
            RobotCalibrationStates.CHESSBOARD_FOUND: self._handle_chessboard_found,
            RobotCalibrationStates.LOOKING_FOR_ARUCO_MARKERS: self._handle_looking_for_aruco_markers,
            RobotCalibrationStates.ALL_ARUCO_FOUND: self._handle_all_aruco_found,
            RobotCalibrationStates.COMPUTE_OFFSETS: self._handle_compute_offsets,
            RobotCalibrationStates.ALIGN_ROBOT: self._handle_align_robot,
            RobotCalibrationStates.ITERATE_ALIGNMENT: self._handle_iterate_alignment,
            RobotCalibrationStates.CAPTURE_TCP_OFFSET: self._handle_capture_tcp_offset,
            RobotCalibrationStates.SAMPLE_HEIGHT: self._take_height_sample,
            RobotCalibrationStates.DONE: self._handle_done,
            RobotCalibrationStates.ERROR: self._handle_error,
        }

        # Create a state registry
        registry = StateRegistry()
        for state_enum, handler in state_handlers_map.items():
            registry.register_state(State(
                state=state_enum,
                handler=handler,
                on_enter=lambda ctx, s=state_enum: self.calibration_context.start_state_timer(s.name),
                on_exit=lambda ctx, s=state_enum: self.calibration_context.end_state_timer()
            ))

        # Build the executable state machine
        transition_rules = RobotCalibrationTransitionRules.get_calibration_transition_rules()
        
        state_machine = (
            ExecutableStateMachineBuilder()
            .with_initial_state(RobotCalibrationStates.INITIALIZING)
            .with_transition_rules(transition_rules)
            .with_state_registry(registry)
            .with_context(self.calibration_context)
            .with_message_broker(self.calibration_context.broker)
            .with_state_topic("ROBOT_CALIBRATION_STATE")
            .build()
        )

        # Store reference in context for state handlers to access
        self.calibration_context.state_machine = state_machine
        
        return state_machine

    # State handler wrapper methods
    def _handle_initializing(self, context):
        init_frame = context.vision_service.get_latest_frame()
        result = handle_initializing_state(init_frame)
        return result.next_state

    def _handle_axis_mapping(self, context):
        result = handle_axis_mapping_state(
            context.vision_service,
            context.calibration_vision,
            context.calibration_robot_controller,
            context.axis_mapping_config,
            context.stop_event,
        )
        if not result.success:
            set_calibration_error(context, result.message)
        context.image_to_robot_mapping = result.data
        time.sleep(1)
        return result.next_state

    def _handle_looking_for_chessboard(self, context):
        return handle_looking_for_chessboard_state(context)

    def _handle_chessboard_found(self, context):
        return handle_chessboard_found_state(context)

    def _handle_looking_for_aruco_markers(self, context):
        return handle_looking_for_aruco_markers_state(context)

    def _handle_all_aruco_found(self, context):
        return handle_all_aruco_found_state(context)

    def _handle_compute_offsets(self, context):
        return handle_compute_offsets_state(context)

    def _handle_align_robot(self, context):
        return handle_align_robot_state(context)

    def _handle_iterate_alignment(self, context):
        return handle_iterate_alignment_state(context)

    def _take_height_sample(self,context):

        return handle_height_sample_state(context)

    def _handle_capture_tcp_offset(self, context):
        return handle_capture_tcp_offset_state(context)

    def _handle_done(self, context):
        next_state = handle_done_state(context)
        # If we're truly done (all markers processed), stop the state machine
        target_ids = list(context.target_plan.target_marker_ids or context.target_plan.required_ids)
        current_marker_id = context.progress.current_marker_id
        if next_state == RobotCalibrationStates.DONE and current_marker_id >= len(target_ids) - 1:
            self.calibration_state_machine.stop_execution()
        return next_state

    def _handle_error(self, context):
        next_state = handle_error_state(context)
        # Stop the state machine on error
        self.calibration_state_machine.stop_execution()
        return next_state

    def run(self):
        """
        Run the calibration process using the state machine.
        
        Returns:
            bool: True if calibration completed successfully, False if error occurred
        """
        try:
            _logger.info("=== STARTING REFACTORED ROBOT_CALIBRATION RUN ===")
            _logger.info(
                "Calibration candidates configured: candidate_ids=%s required_ids=%s homography_target_count=%s residual_target_count=%s validation_target_count=%s",
                list(self.calibration_context.target_plan.candidate_ids),
                list(self.calibration_context.target_plan.required_ids),
                self.calibration_context.homography_target_count,
                self.calibration_context.residual_target_count,
                self.calibration_context.validation_target_count,
            )
            if self.calibration_context.known_unreachable_marker_ids:
                _logger.info(
                    "Known unreachable calibration markers will be skipped: ids=%s threshold=%s",
                    sorted(int(marker_id) for marker_id in self.calibration_context.known_unreachable_marker_ids),
                    self.calibration_context.unreachable_marker_failure_threshold,
                )



            # Broadcast calibration start event
            if self.calibration_context.broadcast_events:
                self.calibration_context.broker.publish(
                    self.calibration_context.CALIBRATION_START_TOPIC, 
                    ""
                )

            # Start total calibration timer
            self.calibration_context.total_calibration_start_time = time.time()
            self.calibration_context.progress.total_calibration_start_time = self.calibration_context.total_calibration_start_time

            # Run the state machine
            self.calibration_state_machine.start_execution(delay=0.2)

            # Check final state
            final_state = self.calibration_state_machine.current_state
            success = final_state == RobotCalibrationStates.DONE
            cancelled = final_state == RobotCalibrationStates.CANCELLED

            if success:
                self._finalize_calibration()
            elif cancelled:
                self._stop_robot_motion()

            msg = "Calibration complete" if success else ("Calibration cancelled" if cancelled else "Calibration failed")
            return success, msg

        except Exception as e:
            _logger.error(f"Error in refactored calibration run: {e}")

            import traceback
            traceback.print_exc()
            return False, str(e)
        finally:
            # Always clean up the live feed thread when calibration ends
            _logger.info("=== ROBOT_CALIBRATION FINISHED ===")
            _logger.info("Stopping live feed thread...")
            stop_live_feed_thread()

    def _stop_robot_motion(self):
        try:
            self.calibration_context.calibration_robot_controller.robot_service.stop_motion()
        except Exception:
            pass

    def _finalize_calibration(self):
        """Finalize the calibration by computing and saving calibration model artifacts."""
        context = self.calibration_context

        _logger.info("--- Calibration Process Complete ---")

        dataset = build_calibration_dataset(context)
        if dataset.dropped_camera_ids:
            _logger.info(
                "Finalizing calibration with used correspondences only: used_camera_ids=%s dropped_detected_only_ids=%s",
                sorted(int(marker_id) for marker_id in context.artifacts.camera_points_for_homography.keys()),
                dataset.dropped_camera_ids,
            )
        model_result = build_calibration_model(
            dataset,
            use_ransac=context.use_ransac,
            metadata={
                "candidate_ids": list(context.target_plan.candidate_ids),
                "selected_target_ids": list(context.target_plan.target_marker_ids),
                "homography_marker_ids": list(context.target_plan.homography_marker_ids),
                "residual_marker_ids": list(context.target_plan.residual_marker_ids),
                "validation_marker_ids": list(context.target_plan.validation_marker_ids),
                "training_marker_ids": list(dataset.homography_training_ids),
                "residual_training_marker_ids": list(dataset.residual_training_ids),
                "used_marker_ids": list(dataset.used_marker_ids),
                "skipped_marker_ids": list(context.artifacts.skipped_target_ids),
                "failed_marker_ids": list(context.artifacts.failed_target_ids),
                "dropped_detected_only_ids": list(dataset.dropped_camera_ids),
                "known_unreachable_marker_ids": sorted(
                    int(marker_id) for marker_id in getattr(context, "known_unreachable_marker_ids", set())
                ),
                "unreachable_marker_failure_counts": {
                    int(marker_id): int(count)
                    for marker_id, count in getattr(context, "unreachable_marker_failure_counts", {}).items()
                },
                "recovery_marker_id": context.target_plan.recovery_marker_id,
                "selection_report": dict(context.target_plan.target_selection_report),
            },
        )

        # Save or warn based on error
        if model_result.average_error_mm <= 3:
            np.save(context.vision_service.camera_to_robot_matrix_path, model_result.homography_matrix)
            _logger.info(f"Homography matrix saved to {context.vision_service.camera_to_robot_matrix_path}")
        else:
            _logger.warning(f"High reprojection error: {model_result.average_error_mm:.3f} mm")

        # End final state timer and log summary
        context.end_state_timer()
        total_calibration_time = time.time() - context.progress.total_calibration_start_time

        # Log timing summary
        if context.timing.state_timings:
            summary = get_log_timing_summary(context.timing.state_timings)
            _logger.info(summary)

        # Structured final log
        report_bundle = build_calibration_reports(
            context=context,
            model_result=model_result,
            candidate_ids=list(context.target_plan.candidate_ids),
            selected_ids=list(context.target_plan.target_marker_ids or model_result.labels),
            used_ids=list(model_result.labels),
            skipped_ids=list(context.artifacts.skipped_target_ids),
            failed_ids=list(context.artifacts.failed_target_ids),
            recovery_marker_id=context.target_plan.recovery_marker_id,
            total_calibration_time=total_calibration_time,
        )
        _logger.info(report_bundle.completion_log)
        save_homography_residual_artifact(
            model_result.model_report["artifacts"]["homography_tps_residual"],
            report_bundle.artifact_paths["homography_residual_path"],
        )
        save_calibration_model_report(
            model_result.model_report,
            report_bundle.artifact_paths["report_path"],
        )
        _logger.info("Homography residual artifact saved to %s", report_bundle.artifact_paths["homography_residual_path"])
        _logger.info("Calibration model report saved to %s", report_bundle.artifact_paths["report_path"])
        _logger.info(report_bundle.model_comparison_report)
        _logger.info(report_bundle.calibration_analysis_report)

        # Broadcast calibration stop event
        if context.broadcast_events:
            context.broker.publish(context.CALIBRATION_STOP_TOPIC, "")

    def get_context(self) -> RobotCalibrationContext:
        """Get the calibration context for external access"""
        return self.calibration_context

    def get_state_machine(self) -> ExecutableStateMachine:
        """Get the state machine for external monitoring"""
        return self.calibration_state_machine
