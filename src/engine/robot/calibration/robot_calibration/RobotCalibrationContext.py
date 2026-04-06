"""
Robot Calibration Context

This module provides the execution context for robot calibration operations,
similar to the ExecutionContext used in the glue dispensing application.
It holds all the state and data needed during the calibration process.
"""
import threading
from dataclasses import dataclass
import time

from src.engine.vision import IVisionService


@dataclass
class Context:
    """Base context class for compatibility with ExecutableStateMachine"""
    pass


class RobotCalibrationContext(Context):
    """Holds execution state for robot calibration operations"""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset calibration context to initial state"""
        # System components
        self.vision_service = None
        self.height_measuring_service = None
        self.calibration_robot_controller = None
        self.calibration_vision = None
        self.axis_mapping_config = None
        self.stop_event = threading.Event()
        self.broker = None
        self.state_machine = None
        
        # Configuration
        self.required_ids = set()
        self.candidate_ids = set()
        self.target_marker_ids: list[int] = []
        self.recovery_marker_id: int | None = None
        self.min_targets = 4
        self.max_targets = 0
        self.min_target_separation_px = 120.0
        self.chessboard_size = None
        self.square_size_mm = None
        self.alignment_threshold_mm = 1.0
        self.debug = False
        self.step_by_step = False
        self.live_visualization = True
        self.show_debug_info = True
        self.broadcast_events = False
        self.use_marker_centre = False   # mean of 4 corners vs top-left corner
        self.use_ransac = False          # RANSAC vs plain DLT in findHomography
        
        # Event topics
        self.BROADCAST_TOPIC = None
        self.CALIBRATION_START_TOPIC = None
        self.CALIBRATION_STOP_TOPIC = None
        self.CALIBRATION_IMAGE_TOPIC = None
        
        # Error handling
        self.calibration_error_message = None
        
        # Calibration state
        self.bottom_left_chessboard_corner_px = None
        self.chessboard_center_px = None
        self.markers_offsets_mm = {}
        self.current_marker_id = 0
        
        # Z-axis configuration
        self.Z_current = None
        self.Z_target = None
        self.ppm_scale = None
        
        # Calibration results
        self.robot_positions_for_calibration = {}
        self.camera_points_for_homography = {}
        self.image_to_robot_mapping = None
        self.marker_neighbor_ids: dict[int, list[int]] = {}
        self.available_marker_points_px: dict[int, tuple[float, float]] = {}
        self.failed_target_ids: set[int] = set()
        self.skipped_target_ids: set[int] = set()
        self.target_selection_report: dict = {}
        self.camera_tcp_offset_config = None
        self.camera_tcp_offset_samples: list = []
        self.camera_tcp_offset_captured_markers = set()
        self.run_height_measurement = True
        self.settings_service = None
        self.robot_config = None
        self.robot_config_key = None
        
        # Iteration tracking
        self.iteration_count = 0
        self.max_iterations = 50
        self.max_acceptable_calibration_error = 1.0
        
        # Performance optimization
        self.min_camera_flush = 5

        # Height map samples collected during HEIGHT_SAMPLE states
        self.height_map_samples: list = []  # [[x, y, height_mm], ...]
        self.fast_iteration_wait = 1
        self.marker_not_found_retry_wait = 0.5
        
        # Timing and performance tracking
        self.state_timings = {}
        self.current_state_start_time = None
        self.total_calibration_start_time = None
        
        # Error handling
        self.calibration_error_message = None
        
    def get_current_state_name(self) -> str:
        """Get current state name for logging"""
        if self.state_machine and hasattr(self.state_machine, 'current_state'):
            return self.state_machine.current_state.name
        return "UNKNOWN"
    
    def start_state_timer(self, state_name: str):
        """Start timing for a state"""
        if self.current_state_start_time is not None:
            self.end_state_timer()
        
        self.current_state_start_time = time.time()
        
    def end_state_timer(self):
        """End timing for current state"""
        if self.current_state_start_time is None:
            return
            
        state_duration = time.time() - self.current_state_start_time
        state_name = self.get_current_state_name()
        
        # Store timing
        if state_name not in self.state_timings:
            self.state_timings[state_name] = []
        self.state_timings[state_name].append(state_duration)
        
        self.current_state_start_time = None

    def wait_for_frame(self):
        """Return next camera frame, or None if stop was requested before a frame arrived."""
        while True:
            if self.stop_event.is_set():
                return None
            frame = self.vision_service.get_latest_frame()
            if frame is not None:
                return frame

    def interruptible_sleep(self, seconds: float) -> bool:
        """Sleep up to `seconds`. Returns True if interrupted (stop requested), False otherwise."""
        return self.stop_event.wait(timeout=seconds)

    def flush_camera_buffer(self):
        if self.vision_service:
            for _ in range(self.min_camera_flush):
                self.vision_service.get_latest_frame()

    def to_debug_dict(self) -> dict:
        """
        Serialize context to dictionary for debug output.
        Returns a human-readable representation of current calibration state.
        """
        return {
            # Progress tracking
            "current_marker_id": self.current_marker_id,
            "total_markers": len(self.target_marker_ids) if self.target_marker_ids else (len(self.required_ids) if self.required_ids else 0),
            "target_markers": list(self.target_marker_ids),
            "recovery_marker_id": self.recovery_marker_id,
            "iteration_count": self.iteration_count,
            "max_iterations": self.max_iterations,
            
            # Calibration state
            "required_ids": list(self.required_ids) if self.required_ids else [],
            "markers_processed": len(self.robot_positions_for_calibration),
            "camera_points_collected": len(self.camera_points_for_homography),
            
            # Configuration
            "chessboard_size": self.chessboard_size,
            "square_size_mm": self.square_size_mm,
            "alignment_threshold_mm": self.alignment_threshold_mm,
            "Z_current": self.Z_current,
            "Z_target": self.Z_target,
            "ppm_scale": self.ppm_scale,
            
            # System state
            "has_system": self.vision_service is not None,
            "has_robot_controller": self.calibration_robot_controller is not None,
            "has_calibration_vision": self.calibration_vision is not None,
            "has_state_machine": self.state_machine is not None,
            
            # Performance metrics
            "state_timing_count": len(self.state_timings),
            "timing_states": list(self.state_timings.keys()),
            
            # Image processing state
            "has_chessboard_corner": self.bottom_left_chessboard_corner_px is not None,
            "has_chessboard_center": self.chessboard_center_px is not None,
            "has_image_to_robot_mapping": self.image_to_robot_mapping is not None,
            
            # Debug and visualization
            "debug_enabled": self.debug,
            "live_visualization": self.live_visualization,
            "broadcast_events": self.broadcast_events,
        }
