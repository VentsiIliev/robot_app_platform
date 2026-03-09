"""
Refactored Robot Calibration using ExecutableStateMachine

This module provides a refactored version of the robot calibration vision_service
that uses the ExecutableStateMachine for better separation of concerns,
maintainability, and consistency with other vision_service components.
"""

import time
import cv2
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
from src.engine.robot.calibration.robot_calibration.debug import DebugDraw
from src.engine.robot.calibration.robot_calibration.logging import (
    get_log_timing_summary, 
    construct_calibration_completion_log_message
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
    stop_live_feed_thread
)
from src.engine.robot.calibration.robot_calibration.states.all_aruco_found_handler import handle_all_aruco_found_state
from src.engine.robot.calibration.robot_calibration.states.compute_offsets_handler import handle_compute_offsets_state
from src.engine.robot.calibration.robot_calibration.states.remaining_handlers import (
    handle_align_robot_state,
    handle_iterate_alignment_state,
    handle_done_state,
    handle_error_state
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
        context.Z_target = config.z_target
        context.axis_mapping_config = config.axis_mapping_config

        # Laser Detection/Height measuring service
        context.height_measuring_service = config.height_measuring_service

        # Camera configuration
        context.vision_service.set_draw_contours(False)
        context.chessboard_size = (
            context.vision_service.get_chessboard_width(),
            context.vision_service.get_chessboard_height()
        )
        context.square_size_mm = context.vision_service.get_square_size_mm()

        # Adaptive movement configuration
        if adaptive_movement_config:
            context.alignment_threshold_mm = adaptive_movement_config.target_error_mm

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
        )
        context.calibration_robot_controller.move_to_calibration_position()

        # Initialize supporting components
        context.debug_draw = DebugDraw()
        context.calibration_vision = CalibrationVision(
            context.vision_service,
            context.chessboard_size,
            context.square_size_mm,
            context.required_ids,
            context.debug_draw,
            context.debug
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
        )
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

    def _handle_done(self, context):
        next_state = handle_done_state(context)
        # If we're truly done (all markers processed), stop the state machine
        if next_state == RobotCalibrationStates.DONE and context.current_marker_id >= len(context.required_ids) - 1:
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
            _logger.info(f"Required IDs: {self.calibration_context.required_ids}")



            # Broadcast calibration start event
            if self.calibration_context.broadcast_events:
                self.calibration_context.broker.publish(
                    self.calibration_context.CALIBRATION_START_TOPIC, 
                    ""
                )

            # Start total calibration timer
            self.calibration_context.total_calibration_start_time = time.time()

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
            return False
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
        """Finalize the calibration by computing and saving the homography matrix"""
        context = self.calibration_context

        _logger.info("--- Calibration Process Complete ---")

        # Sort by marker ID
        sorted_robot_items = sorted(context.robot_positions_for_calibration.items(), key=lambda x: x[0])
        sorted_camera_items = sorted(context.camera_points_for_homography.items(), key=lambda x: x[0])

        # Prepare corresponding points in sorted order
        robot_positions = [pos[:2] for _, pos in sorted_robot_items]
        camera_points = [pt for _, pt in sorted_camera_items]

        # Compute homography
        src_pts = np.array(camera_points, dtype=np.float32)
        dst_pts = np.array(robot_positions, dtype=np.float32)
        H_camera_center, status = cv2.findHomography(src_pts, dst_pts)

        # Test and validate
        average_error_camera_center, _ = metrics.test_calibration(
            H_camera_center, src_pts, dst_pts, "transformation_to_camera_center"
        )

        # Save or warn based on error
        if average_error_camera_center <= 1:
            np.save(context.vision_service.camera_to_robot_matrix_path, H_camera_center)
            _logger.info(f"Homography matrix saved to {context.vision_service.camera_to_robot_matrix_path}")
        else:
            _logger.warning(f"High reprojection error: {average_error_camera_center:.3f} mm")

        # End final state timer and log summary
        context.end_state_timer()
        total_calibration_time = time.time() - context.total_calibration_start_time

        # Log timing summary
        if context.state_timings:
            summary = get_log_timing_summary(context.state_timings)
            _logger.info(summary)

        # Structured final log
        completion_log = construct_calibration_completion_log_message(
            sorted_robot_items=sorted_robot_items,
            sorted_camera_items=sorted_camera_items,
            H_camera_center=H_camera_center,
            status=status,
            average_error_camera_center=average_error_camera_center,
            matrix_path=context.vision_service.camera_to_robot_matrix_path,
            total_calibration_time=total_calibration_time
        )
        _logger.info(completion_log)

        # Broadcast calibration stop event
        if context.broadcast_events:
            context.broker.publish(context.CALIBRATION_STOP_TOPIC, "")

    def get_context(self) -> RobotCalibrationContext:
        """Get the calibration context for external access"""
        return self.calibration_context

    def get_state_machine(self) -> ExecutableStateMachine:
        """Get the state machine for external monitoring"""
        return self.calibration_state_machine