from __future__ import annotations

from dataclasses import dataclass

from pl_gui.dashboard.config import ActionButtonConfig, CardConfig, DashboardConfig


@dataclass
class PaintDashboardConfig(DashboardConfig):
    show_placeholders: bool = False
    card_grid_rows: int = 4
    card_grid_cols: int = 1
    card_grid_min_width: int = 360
    card_grid_max_width: int = 430
    action_grid_rows: int = 1
    action_grid_cols: int = 1
    bottom_section_height: int = 380


PAINT_DASHBOARD_CARDS: list[CardConfig] = [
    CardConfig(card_id=1, label="Robot Status"),
    CardConfig(card_id=2, label="Vision Status"),
    CardConfig(card_id=3, label="Process Status"),
]


PAINT_DASHBOARD_ACTIONS: list[ActionButtonConfig] = [
    ActionButtonConfig(action_id="reset_errors", label="Reset Errors", row=0, col=0),
]
