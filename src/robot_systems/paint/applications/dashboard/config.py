from __future__ import annotations

from dataclasses import dataclass

from pl_gui.dashboard.config import ActionButtonConfig, CardConfig, DashboardConfig


@dataclass
class PaintDashboardConfig(DashboardConfig):
    show_placeholders: bool = False


PAINT_DASHBOARD_CARDS: list[CardConfig] = [
    CardConfig(card_id=1, label="Paint Process"),
]


PAINT_DASHBOARD_ACTIONS: list[ActionButtonConfig] = [
    ActionButtonConfig(action_id="test_pickup", label="Test Pickup", row=0, col=0),
    ActionButtonConfig(action_id="go_to_calibration", label="Go to Calibration", row=0, col=1),
    ActionButtonConfig(action_id="move_to_calibration_ptp", label="Move to Cal (PTP)", row=0, col=2),
    ActionButtonConfig(action_id="pickup_to_paint_position", label="Pickup to Paint Position", row=0, col=3),
    ActionButtonConfig(action_id="move_to_home_zeros", label="Go to Zeros", row=0, col=4),
    ActionButtonConfig(action_id="test_pre_paint_marker", label="Test Pre-Paint Marker", row=1, col=0),
    ActionButtonConfig(action_id="reset_errors", label="Reset Errors", row=1, col=1),
]
