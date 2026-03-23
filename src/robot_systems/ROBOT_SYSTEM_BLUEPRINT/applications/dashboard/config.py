from __future__ import annotations

from dataclasses import dataclass

from pl_gui.dashboard.config import ActionButtonConfig, CardConfig, DashboardConfig


@dataclass
class MyDashboardConfig(DashboardConfig):
    show_placeholders: bool = False


MY_DASHBOARD_CARDS: list[CardConfig] = [
    CardConfig(card_id=1, label="Main Process"),
]


MY_DASHBOARD_ACTIONS: list[ActionButtonConfig] = [
    ActionButtonConfig(action_id="reset_errors", label="Reset Errors", row=1, col=0),
]
