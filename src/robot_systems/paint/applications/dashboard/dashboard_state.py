from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DashboardCardState:
    title: str
    value: str
    note: str


@dataclass
class DashboardState:
    process_state: str = "idle"
    mode_label: str = "Paint Mode"
    active_job_label: str = "No active job"
    status_lines: list[str] = field(default_factory=list)
    card_states: dict[int, DashboardCardState] = field(default_factory=dict)
    can_start: bool = True
    can_stop: bool = False
    can_pause: bool = False
    pause_label: str = "Pause"
