from __future__ import annotations
from dataclasses import asdict
import logging
import threading
from typing import Optional, Any

from src.robot_systems.glue.processes.glue_dispensing.dispensing_error import (
    DispensingErrorCode,
    DispensingErrorInfo,
    DispensingErrorKind,
)
from src.robot_systems.glue.processes.glue_dispensing.dispensing_path import (
    DispensingPathEntry,
    DispensingPathPoints,
)
from src.robot_systems.glue.processes.glue_dispensing.dispensing_settings import (
    DispensingSegmentSettings,
)
from src.robot_systems.glue.processes.glue_dispensing.context_ops.cleanup_ops import DispensingCleanupOps
from src.robot_systems.glue.processes.glue_dispensing.context_ops.motion_ops import DispensingMotionOps
from src.robot_systems.glue.processes.glue_dispensing.context_ops.path_ops import DispensingPathOps
from src.robot_systems.glue.processes.glue_dispensing.context_ops.pump_thread_ops import (
    DispensingPumpThreadOps,
)

_logger = logging.getLogger(__name__)


class DispensingContext:
    def __init__(self) -> None:
        self.stop_event:  threading.Event = threading.Event()
        self.run_allowed: threading.Event = threading.Event()
        self.run_allowed.set()
        self.paused_from_state = None
        self.cleanup = DispensingCleanupOps(self)
        self.path_ops = DispensingPathOps(self)
        self.motion_ops = DispensingMotionOps(self)
        self.pump_thread_ops = DispensingPumpThreadOps(self)
        self.reset()

    def reset(self) -> None:
        # Input data and external services
        self.paths: Optional[list[DispensingPathEntry]] = None
        self.spray_on: bool = False
        self.motor_service = None   # IMotorService
        self.generator = None       # IGeneratorController
        self.robot_service = None   # IRobotService
        self.resolver = None        # IGlueTypeResolver
        self.pump_controller = None # GluePumpController
        self.state_machine = None   # set by DispensingMachineFactory

        # Path progress and resume state
        self.current_path_index: int = 0
        self.current_point_index: int = 0
        self.target_point_index: int = 0
        self.current_segment_start_index: int = 0
        self.current_segment_task_id: int | None = None
        self.current_entry: Optional[DispensingPathEntry] = None
        self.current_settings: Optional[DispensingSegmentSettings] = None
        self.current_path: Optional[DispensingPathPoints] = None
        self.paused_from_state = None
        self.is_resuming: bool = False

        # Runtime resources and flags
        self.pump_thread = None
        self.pump_ready_event = None
        self.generator_started: bool = False
        self.motor_started: bool = False
        self.operation_just_completed: bool = False
        self.segment_trajectory_submitted: bool = False
        self.segment_trajectory_completed: bool = False
        self.last_error: Optional[DispensingErrorInfo] = None

        # Robot motion params (populated from GlueDispensingConfig)
        self.robot_tool: int = 0
        self.robot_user: int = 0
        self.global_velocity: float = 10.0
        self.global_acceleration: float = 30.0
        self.move_to_first_point_poll_s: float = 0.02
        self.move_to_first_point_timeout_s: float = 30.0
        self.pump_thread_wait_poll_s: float = 0.1
        self.final_position_poll_s: float = 0.1
        self.pump_ready_timeout_s: float = 5.0
        self.pump_thread_join_timeout_s: float = 2.0
        self.pump_adjuster_poll_s: float = 0.01

    def save_progress(self, path_index: int, point_index: int) -> None:
        self.current_path_index  = path_index
        self.current_point_index = point_index

    def pause_from(self, state) -> None:
        self.paused_from_state = state

    def stop_with_progress(self, path_index: int, point_index: int) -> None:
        self.save_progress(path_index, point_index)

    def pause_with_progress(self, state, path_index: int, point_index: int) -> None:
        self.save_progress(path_index, point_index)
        self.pause_from(state)

    def mark_segment_trajectory_submitted(self, start_index: int, task_id: int | None = None) -> None:
        self.current_segment_start_index = start_index
        self.current_point_index = start_index
        self.current_segment_task_id = task_id
        self.segment_trajectory_submitted = True
        self.segment_trajectory_completed = False

    def mark_segment_trajectory_completed(self) -> None:
        self.segment_trajectory_completed = True
        if self.current_entry is not None:
            self.current_point_index = len(self.current_entry.points)
        elif self.current_path is not None:
            self.current_point_index = len(self.current_path)

    def reset_segment_trajectory_state(self) -> None:
        self.current_segment_start_index = 0
        self.current_segment_task_id = None
        self.segment_trajectory_submitted = False
        self.segment_trajectory_completed = False

    def pause_current_segment_execution(self, state) -> None:
        self.current_point_index = self.current_segment_start_index
        self.pause_from(state)

    def stop_current_segment_execution(self) -> None:
        self.current_point_index = self.current_segment_start_index

    def mark_generator_stopped(self) -> None:
        self.generator_started = False

    def mark_motor_stopped(self) -> None:
        self.motor_started = False

    def mark_completed(self) -> None:
        self.operation_just_completed = True

    def clear_error(self) -> None:
        self.last_error = None

    def fail(
        self,
        kind: DispensingErrorKind,
        code: DispensingErrorCode,
        state,
        operation: str,
        message: str,
        exc: Exception | None = None,
        recoverable: bool = False,
    ):
        self.last_error = DispensingErrorInfo(
            kind=kind,
            code=code,
            state=state,
            operation=operation,
            message=message,
            exception_type=type(exc).__name__ if exc is not None else None,
            path_index=self.current_path_index,
            point_index=self.current_point_index,
            recoverable=recoverable,
        )
        if exc is not None:
            _logger.exception(
                "%s [state=%s operation=%s path=%s point=%s]",
                message,
                state.name,
                operation,
                self.current_path_index,
                self.current_point_index,
                exc_info=exc,
            )
        else:
            _logger.error(
                "%s [state=%s operation=%s path=%s point=%s]",
                message,
                state.name,
                operation,
                self.current_path_index,
                self.current_point_index,
            )
        from src.robot_systems.glue.processes.glue_dispensing.dispensing_state import GlueDispensingState

        return GlueDispensingState.ERROR

    def has_valid_context(self) -> bool:
        return self.paths is not None and len(self.paths) > 0

    def build_debug_snapshot(self) -> dict[str, Any]:
        current_entry = self.current_entry
        current_settings = self.get_segment_settings()
        last_error = asdict(self.last_error) if self.last_error is not None else None
        if last_error is not None:
            last_error["kind"] = self.last_error.kind.name
            last_error["code"] = self.last_error.code.name
            last_error["state"] = self.last_error.state.name

        return {
            "paths_total": len(self.paths or []),
            "current_path_index": self.current_path_index,
            "current_point_index": self.current_point_index,
            "target_point_index": self.target_point_index,
            "current_segment_start_index": self.current_segment_start_index,
            "current_segment_task_id": self.current_segment_task_id,
            "spray_on": self.spray_on,
            "is_resuming": self.is_resuming,
            "paused_from_state": getattr(self.paused_from_state, "name", None),
            "motor_started": self.motor_started,
            "generator_started": self.generator_started,
            "operation_just_completed": self.operation_just_completed,
            "segment_trajectory_submitted": self.segment_trajectory_submitted,
            "segment_trajectory_completed": self.segment_trajectory_completed,
            "stop_requested": self.stop_event.is_set(),
            "run_allowed": self.run_allowed.is_set(),
            "pump_thread_alive": bool(self.pump_thread and self.pump_thread.is_alive()),
            "pump_ready_event_set": bool(
                self.pump_ready_event is not None and self.pump_ready_event.is_set()
            ),
            "current_entry": {
                "point_count": len(current_entry.points),
                "metadata": dict(current_entry.metadata),
            } if current_entry is not None else None,
            "current_path_first_point": (
                self.current_path[0] if self.current_path else None
            ),
            "current_path_last_point": (
                self.current_path[-1] if self.current_path else None
            ),
            "current_settings": current_settings.to_dict() if current_settings is not None else None,
            "last_error": last_error,
        }

    def get_segment_settings(self) -> DispensingSegmentSettings | None:
        if self.current_settings is None:
            return None
        if isinstance(self.current_settings, DispensingSegmentSettings):
            return self.current_settings
        self.current_settings = DispensingSegmentSettings.from_raw(self.current_settings)
        return self.current_settings

    def get_motor_address_for_current_path(self) -> int:
        settings = self.get_segment_settings()
        if not settings:
            return 0
        glue_type = settings.glue_type
        if not glue_type:
            return -1
        if self.resolver is None:
            return -1
        return self.resolver.resolve(glue_type)

    def get_valid_motor_address_for_current_path(self) -> int | None:
        motor_address = self.get_motor_address_for_current_path()
        if motor_address == -1:
            return None
        return motor_address
