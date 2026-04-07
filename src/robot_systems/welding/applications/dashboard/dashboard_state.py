from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DashboardState:
    process_state: str = "idle"
    mode_label: str = "Welding Mode"
    active_job_label: str = "No active job"
    status_lines: list[str] = field(default_factory=list)
    can_start: bool = True
    can_stop: bool = False
    can_pause: bool = False
    pause_label: str = "Pause"

