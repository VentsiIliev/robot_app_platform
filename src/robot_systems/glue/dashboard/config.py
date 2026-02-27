from __future__ import annotations
from dataclasses import dataclass
from pl_gui.dashboard.config import DashboardConfig, ActionButtonConfig, CardConfig
from src.shared_contracts.events.process_events import ProcessState


class GlueCellTopics:
    @staticmethod
    def weight(cell_id: int) -> str:    return f"glue/cell/{cell_id}/weight"
    @staticmethod
    def state(cell_id: int) -> str:     return f"glue/cell/{cell_id}/state"
    @staticmethod
    def glue_type(cell_id: int) -> str: return f"glue/cell/{cell_id}/glue_type"


class SystemTopics:
    SYSTEM_STATE  = "system/system_state"




@dataclass
class GlueDashboardConfig(DashboardConfig):
    default_cell_capacity_grams: float = 5000.0


GLUE_CELLS: list[CardConfig] = [
    CardConfig(card_id=1, label="Glue 1"),
    CardConfig(card_id=2, label="Glue 2"),
    CardConfig(card_id=3, label="Glue 3"),
]

ACTION_BUTTONS: list[ActionButtonConfig] = [
    ActionButtonConfig(action_id="reset_errors", label="Reset Errors", enabled=True, row=1, col=0),
    ActionButtonConfig(action_id="mode_toggle",  label="Pick And Spray", row_span=1, col_span=2),
    ActionButtonConfig(action_id="clean",        label="Clean"),
]

BUTTON_STATE_MAP: dict = {
    ProcessState.IDLE.value:    {"start": True,  "stop": False, "pause": False, "pause_text": "Pause",   "mode_toggle": True,  "clean": True,  "reset_errors": False},
    ProcessState.RUNNING.value: {"start": False, "stop": True,  "pause": True,  "pause_text": "Pause",   "mode_toggle": False, "clean": False, "reset_errors": False},
    ProcessState.PAUSED.value:  {"start": False, "stop": True,  "pause": True,  "pause_text": "Resume",  "mode_toggle": False, "clean": False, "reset_errors": False},
    ProcessState.STOPPED.value: {"start": True,  "stop": False, "pause": False, "pause_text": "Pause",   "mode_toggle": True,  "clean": True,  "reset_errors": False},
    ProcessState.ERROR.value:   {"start": False, "stop": True,  "pause": False, "pause_text": "Pause",   "mode_toggle": False, "clean": False, "reset_errors": True},
}



MODE_TOGGLE_LABELS = ("Pick And Spray", "Spray Only")
