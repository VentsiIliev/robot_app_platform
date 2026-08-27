from __future__ import annotations

import threading
from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable

from src.robot_systems.paint.processes.paint.config import PaintMagazineLoadConfig, PaintProcessConfig
from src.robot_systems.paint.processes.paint.execution_control import PaintExecutionControl
from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState


@dataclass
class PaintExecutionContext:
    """Per-cycle state shared by paint execution-machine handlers."""

    production_service: object
    stop_requested: Callable[[], bool]
    control: PaintExecutionControl
    process_config: PaintProcessConfig | None = None
    magazine_config: PaintMagazineLoadConfig | None = None
    cycle_index: int = 1
    repeats_after_success: bool = False
    stop_event: threading.Event = field(default_factory=threading.Event)
    run_allowed: threading.Event = field(default_factory=threading.Event)
    state_machine: object | None = None
    current_state: PaintExecutionState | None = None
    paused_from_state: PaintExecutionState | None = None
    resume_state: PaintExecutionState | None = None
    is_resuming: bool = False
    result_ok: bool = False
    result_message: str = "Paint process stopped"
    total_started_at: float = field(default_factory=perf_counter)
    snapshot: object | None = None
    contour: object | None = None
    raw_workpiece: object | None = None
    workpiece_description: str = ""
    execution_plan: object | None = None
    paint_started_at: float | None = None
    paint_previous_control: object | None = None
    paint_timing_session: object | None = None
    paint_timing_recorder: object | None = None
    state_timing_recorder: object | None = None
    paint_total_waypoints: int = 0
    paint_ordered_result: tuple[bool, str, int] | None = None
    paint_contact_executed_in_ordered_chain: bool = False
    paint_motion_active: bool = False
    resume_retry_available: bool = False
    magazine_group: str = ""
    calibration_group: str = ""
    magazine_snapshot: object | None = None
    magazine_contour: object | None = None
    magazine_pose: list[float] | None = None
    magazine_release_pose: list[float] | None = None
    magazine_target: dict | None = None
    magazine_fixed_pickup_pose: list[float] | None = None

    def __post_init__(self) -> None:
        self.run_allowed.set()

    def should_stop(self) -> bool:
        try:
            external_stop = bool(self.stop_requested())
        except Exception:
            external_stop = True
        return self.stop_event.is_set() or external_stop or self.control.should_stop()

    def motion_cancel_requested(self) -> bool:
        return self.should_stop() or not self.run_allowed.is_set() or self.control.pause_requested()

    def pause_from(self, state: PaintExecutionState) -> None:
        self.paused_from_state = state
        self.resume_state = state

    def mark_resuming(self) -> None:
        self.is_resuming = True
        self.resume_retry_available = True

    def consume_resume_retry(self) -> bool:
        if not self.resume_retry_available:
            return False
        self.resume_retry_available = False
        return True

    def set_result(self, ok: bool, message: str) -> None:
        self.result_ok = bool(ok)
        self.result_message = str(message or "")

    def snapshot_dict(self) -> dict:
        return {
            "current_state": getattr(self.current_state, "name", None),
            "paused_from_state": getattr(self.paused_from_state, "name", None),
            "resume_state": getattr(self.resume_state, "name", None),
            "stop_requested": self.should_stop(),
            "run_allowed": self.run_allowed.is_set(),
            "result_ok": self.result_ok,
            "result_message": self.result_message,
            "cycle_index": self.cycle_index,
            "has_snapshot": self.snapshot is not None,
            "has_contour": self.contour is not None,
            "has_raw_workpiece": self.raw_workpiece is not None,
            "has_execution_plan": self.execution_plan is not None,
            "paint_total_waypoints": self.paint_total_waypoints,
            "paint_contact_executed_in_ordered_chain": self.paint_contact_executed_in_ordered_chain,
            "paint_motion_active": self.paint_motion_active,
            "resume_retry_available": self.resume_retry_available,
            "magazine_group": self.magazine_group,
            "calibration_group": self.calibration_group,
            "has_magazine_snapshot": self.magazine_snapshot is not None,
            "has_magazine_contour": self.magazine_contour is not None,
            "has_magazine_target": self.magazine_target is not None,
        }
