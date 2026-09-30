from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaintDashboardLiveViewEvent:
    paused: bool
    image: object | None = None
    reason: str = ""


class PaintDashboardLiveViewTopics:
    STATE = "paint/dashboard/live-view/state"


@dataclass(frozen=True)
class PaintDashboardMessageEvent:
    level: str
    title: str
    message: str


class PaintDashboardMessageTopics:
    MESSAGE = "paint/dashboard/message"
