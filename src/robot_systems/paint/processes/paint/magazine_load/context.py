from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable

from src.robot_systems.paint.processes.paint.config import PaintMagazineLoadConfig
from src.robot_systems.paint.processes.paint.magazine_load.state import MagazineLoadState


@dataclass
class MagazineLoadContext:
    service: object
    config: PaintMagazineLoadConfig
    stop_requested: Callable[[], bool]
    stop_event: threading.Event = field(default_factory=threading.Event)
    run_allowed: threading.Event = field(default_factory=threading.Event)
    state_machine: object | None = None
    current_state: MagazineLoadState | None = None
    paused_from_state: MagazineLoadState | None = None
    resume_state: MagazineLoadState | None = None
    is_resuming: bool = False
    resume_retry_available: bool = False
    result_ok: bool = False
    result_message: str = "Paint process stopped"
    magazine_group: str = ""
    calibration_group: str = ""
    snapshot: object | None = None
    contour: object | None = None
    magazine_pose: list[float] | None = None
    release_pose: list[float] | None = None
    target: dict | None = None

    def __post_init__(self) -> None:
        self.run_allowed.set()

    def should_stop(self) -> bool:
        try:
            external_stop = bool(self.stop_requested())
        except Exception:
            external_stop = True
        return self.stop_event.is_set() or external_stop

    def motion_cancel_requested(self) -> bool:
        return self.should_stop() or not self.run_allowed.is_set()

    def pause_from(self, state: MagazineLoadState) -> None:
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
            "resume_retry_available": self.resume_retry_available,
            "stop_requested": self.should_stop(),
            "run_allowed": self.run_allowed.is_set(),
            "result_ok": self.result_ok,
            "result_message": self.result_message,
        }
