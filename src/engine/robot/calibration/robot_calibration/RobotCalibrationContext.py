"""
Robot Calibration Context

This module provides the execution context for robot calibration operations,
similar to the ExecutionContext used in the glue dispensing application.
It holds all the state and data needed during the calibration process.
"""
import threading
from dataclasses import dataclass
import time


@dataclass
class Context:
    """Base context class for compatibility with ExecutableStateMachine"""
    pass


@dataclass
class CalibrationServicesView:
    vision_service: object = None
    height_measuring_service: object = None
    calibration_robot_controller: object = None
    calibration_vision: object = None
    settings_service: object = None
    broker: object = None
    state_machine: object = None


@dataclass
class CalibrationTargetPlanView:
    required_ids: list[int] = None
    candidate_ids: list[int] = None
    target_marker_ids: list[int] = None
    homography_marker_ids: list[int] = None
    residual_marker_ids: list[int] = None
    validation_marker_ids: list[int] = None
    execution_marker_ids: list[int] = None
    recovery_marker_id: int | None = None
    marker_neighbor_ids: dict | None = None
    target_selection_report: dict | None = None


@dataclass
class CalibrationArtifactsView:
    bottom_left_chessboard_corner_px: object = None
    chessboard_center_px: object = None
    markers_offsets_mm: dict | None = None
    camera_points_for_homography: dict | None = None
    robot_positions_for_calibration: dict | None = None
    image_to_robot_mapping: object = None
    available_marker_points_px: dict | None = None
    failed_target_ids: set[int] | None = None
    skipped_target_ids: set[int] | None = None
    camera_tcp_offset_samples: list | None = None
    camera_tcp_offset_captured_markers: set[int] | None = None
    height_map_samples: list | None = None


@dataclass
class CalibrationProgressView:
    current_marker_id: int = 0
    iteration_count: int = 0
    max_iterations: int = 50
    alignment_threshold_mm: float = 1.0
    z_current: float | None = None
    z_target: float | None = None
    ppm_scale: float | None = None
    calibration_error_message: str | None = None
    total_calibration_start_time: float | None = None


@dataclass
class CalibrationTimingView:
    state_timings: dict | None = None
    current_state_start_time: float | None = None


class RobotCalibrationContext(Context):
    """Holds execution state for robot calibration operations"""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset calibration context to initial state"""
        self.services = CalibrationServicesView()
        self.target_plan = CalibrationTargetPlanView(
            required_ids=[],
            candidate_ids=[],
            target_marker_ids=[],
            homography_marker_ids=[],
            residual_marker_ids=[],
            validation_marker_ids=[],
            execution_marker_ids=[],
            marker_neighbor_ids={},
            target_selection_report={},
        )
        self.artifacts = CalibrationArtifactsView(
            markers_offsets_mm={},
            camera_points_for_homography={},
            robot_positions_for_calibration={},
            available_marker_points_px={},
            failed_target_ids=set(),
            skipped_target_ids=set(),
            camera_tcp_offset_samples=[],
            camera_tcp_offset_captured_markers=set(),
            height_map_samples=[],
        )
        self.progress = CalibrationProgressView()
        self.timing = CalibrationTimingView(state_timings={})

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
        self.target_marker_ids = []
        self.homography_marker_ids = []
        self.residual_marker_ids = []
        self.validation_marker_ids = []
        self.execution_marker_ids = []
        self.recovery_marker_id = None
        self.min_target_separation_px = 120.0
        self.homography_target_count = 0
        self.residual_target_count = 0
        self.validation_target_count = 0
        self.auto_skip_known_unreachable_markers = True
        self.unreachable_marker_failure_threshold = 1
        self.known_unreachable_marker_ids: set[int] = set()
        self.unreachable_marker_failure_counts: dict[int, int] = {}
        self.chessboard_size = None
        self.square_size_mm = None
        self.reference_board_mode = "auto"
        self.charuco_board_size = None
        self.charuco_marker_size_mm = None
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
        self.marker_neighbor_ids = {}
        self.available_marker_points_px = {}
        self.failed_target_ids = set()
        self.skipped_target_ids = set()
        self.target_selection_report = {}
        self.camera_tcp_offset_config = None
        self.camera_tcp_offset_samples = []
        self.camera_tcp_offset_captured_markers = set()
        self.run_height_measurement = True
        self.settings_service = None
        self.calibration_settings_key = None
        self.robot_config = None
        self.robot_config_key = None
        
        # Iteration tracking
        self.iteration_count = 0
        self.max_iterations = 50
        self.max_acceptable_calibration_error = 1.0
        
        # Performance optimization
        self.min_camera_flush = 5

        # Height map samples collected during HEIGHT_SAMPLE states
        self.height_map_samples = []  # [[x, y, height_mm], ...]
        self.fast_iteration_wait = 1
        self.marker_not_found_retry_wait = 0.5
        
        # Timing and performance tracking
        self.state_timings = {}
        self.current_state_start_time = None
        self.total_calibration_start_time = None
        
        # Error handling
        self.calibration_error_message = None

        self.refresh_group_views()

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
        self.refresh_group_views()
        return {
            # Progress tracking
            "current_marker_id": self.current_marker_id,
            "total_markers": len(self.target_marker_ids) if self.target_marker_ids else (len(self.required_ids) if self.required_ids else 0),
            "target_markers": list(self.target_marker_ids),
            "homography_markers": list(self.homography_marker_ids),
            "residual_markers": list(self.residual_marker_ids),
            "validation_markers": list(self.validation_marker_ids),
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

    def refresh_group_views(self) -> None:
        self.services.vision_service = self.vision_service
        self.services.height_measuring_service = self.height_measuring_service
        self.services.calibration_robot_controller = self.calibration_robot_controller
        self.services.calibration_vision = self.calibration_vision
        self.services.settings_service = self.settings_service
        self.services.broker = self.broker
        self.services.state_machine = self.state_machine

        self.target_plan.required_ids = sorted(int(v) for v in self.required_ids)
        self.target_plan.candidate_ids = sorted(int(v) for v in self.candidate_ids)

    @property
    def target_marker_ids(self):
        return self.target_plan.target_marker_ids

    @target_marker_ids.setter
    def target_marker_ids(self, value):
        self.target_plan.target_marker_ids = list(value)

    @property
    def homography_marker_ids(self):
        return self.target_plan.homography_marker_ids

    @homography_marker_ids.setter
    def homography_marker_ids(self, value):
        self.target_plan.homography_marker_ids = list(value)

    @property
    def residual_marker_ids(self):
        return self.target_plan.residual_marker_ids

    @residual_marker_ids.setter
    def residual_marker_ids(self, value):
        self.target_plan.residual_marker_ids = list(value)

    @property
    def validation_marker_ids(self):
        return self.target_plan.validation_marker_ids

    @validation_marker_ids.setter
    def validation_marker_ids(self, value):
        self.target_plan.validation_marker_ids = list(value)

    @property
    def execution_marker_ids(self):
        return self.target_plan.execution_marker_ids

    @execution_marker_ids.setter
    def execution_marker_ids(self, value):
        self.target_plan.execution_marker_ids = list(value)

    @property
    def recovery_marker_id(self):
        return self.target_plan.recovery_marker_id

    @recovery_marker_id.setter
    def recovery_marker_id(self, value):
        self.target_plan.recovery_marker_id = value

    @property
    def marker_neighbor_ids(self):
        return self.target_plan.marker_neighbor_ids

    @marker_neighbor_ids.setter
    def marker_neighbor_ids(self, value):
        self.target_plan.marker_neighbor_ids = dict(value)

    @property
    def target_selection_report(self):
        return self.target_plan.target_selection_report

    @target_selection_report.setter
    def target_selection_report(self, value):
        self.target_plan.target_selection_report = dict(value)

    @property
    def bottom_left_chessboard_corner_px(self):
        return self.artifacts.bottom_left_chessboard_corner_px

    @bottom_left_chessboard_corner_px.setter
    def bottom_left_chessboard_corner_px(self, value):
        self.artifacts.bottom_left_chessboard_corner_px = value

    @property
    def chessboard_center_px(self):
        return self.artifacts.chessboard_center_px

    @chessboard_center_px.setter
    def chessboard_center_px(self, value):
        self.artifacts.chessboard_center_px = value

    @property
    def markers_offsets_mm(self):
        return self.artifacts.markers_offsets_mm

    @markers_offsets_mm.setter
    def markers_offsets_mm(self, value):
        self.artifacts.markers_offsets_mm = dict(value)

    @property
    def camera_points_for_homography(self):
        return self.artifacts.camera_points_for_homography

    @camera_points_for_homography.setter
    def camera_points_for_homography(self, value):
        self.artifacts.camera_points_for_homography = dict(value)

    @property
    def robot_positions_for_calibration(self):
        return self.artifacts.robot_positions_for_calibration

    @robot_positions_for_calibration.setter
    def robot_positions_for_calibration(self, value):
        self.artifacts.robot_positions_for_calibration = dict(value)

    @property
    def image_to_robot_mapping(self):
        return self.artifacts.image_to_robot_mapping

    @image_to_robot_mapping.setter
    def image_to_robot_mapping(self, value):
        self.artifacts.image_to_robot_mapping = value

    @property
    def available_marker_points_px(self):
        return self.artifacts.available_marker_points_px

    @available_marker_points_px.setter
    def available_marker_points_px(self, value):
        self.artifacts.available_marker_points_px = dict(value)

    @property
    def failed_target_ids(self):
        return self.artifacts.failed_target_ids

    @failed_target_ids.setter
    def failed_target_ids(self, value):
        self.artifacts.failed_target_ids = {int(v) for v in value}

    @property
    def skipped_target_ids(self):
        return self.artifacts.skipped_target_ids

    @skipped_target_ids.setter
    def skipped_target_ids(self, value):
        self.artifacts.skipped_target_ids = {int(v) for v in value}

    @property
    def camera_tcp_offset_samples(self):
        return self.artifacts.camera_tcp_offset_samples

    @camera_tcp_offset_samples.setter
    def camera_tcp_offset_samples(self, value):
        self.artifacts.camera_tcp_offset_samples = list(value)

    @property
    def camera_tcp_offset_captured_markers(self):
        return self.artifacts.camera_tcp_offset_captured_markers

    @camera_tcp_offset_captured_markers.setter
    def camera_tcp_offset_captured_markers(self, value):
        self.artifacts.camera_tcp_offset_captured_markers = {int(v) for v in value}

    @property
    def height_map_samples(self):
        return self.artifacts.height_map_samples

    @height_map_samples.setter
    def height_map_samples(self, value):
        self.artifacts.height_map_samples = list(value)

    @property
    def current_marker_id(self):
        return self.progress.current_marker_id

    @current_marker_id.setter
    def current_marker_id(self, value):
        self.progress.current_marker_id = int(value)

    @property
    def iteration_count(self):
        return self.progress.iteration_count

    @iteration_count.setter
    def iteration_count(self, value):
        self.progress.iteration_count = int(value)

    @property
    def max_iterations(self):
        return self.progress.max_iterations

    @max_iterations.setter
    def max_iterations(self, value):
        self.progress.max_iterations = int(value)

    @property
    def alignment_threshold_mm(self):
        return self.progress.alignment_threshold_mm

    @alignment_threshold_mm.setter
    def alignment_threshold_mm(self, value):
        self.progress.alignment_threshold_mm = float(value)

    @property
    def Z_current(self):
        return self.progress.z_current

    @Z_current.setter
    def Z_current(self, value):
        self.progress.z_current = value

    @property
    def Z_target(self):
        return self.progress.z_target

    @Z_target.setter
    def Z_target(self, value):
        self.progress.z_target = value

    @property
    def ppm_scale(self):
        return self.progress.ppm_scale

    @ppm_scale.setter
    def ppm_scale(self, value):
        self.progress.ppm_scale = value

    @property
    def calibration_error_message(self):
        return self.progress.calibration_error_message

    @calibration_error_message.setter
    def calibration_error_message(self, value):
        self.progress.calibration_error_message = value

    @property
    def total_calibration_start_time(self):
        return self.progress.total_calibration_start_time

    @total_calibration_start_time.setter
    def total_calibration_start_time(self, value):
        self.progress.total_calibration_start_time = value

    @property
    def state_timings(self):
        return self.timing.state_timings

    @state_timings.setter
    def state_timings(self, value):
        self.timing.state_timings = dict(value)

    @property
    def current_state_start_time(self):
        return self.timing.current_state_start_time

    @current_state_start_time.setter
    def current_state_start_time(self, value):
        self.timing.current_state_start_time = value
