from __future__ import annotations
from dataclasses import dataclass
from pl_gui.dashboard.config import DashboardConfig, ActionButtonConfig, CardConfig


class GlueCellTopics:
    @staticmethod
    def weight(cell_id: int) -> str:    return f"glue/cell/{cell_id}/weight"
    @staticmethod
    def state(cell_id: int) -> str:     return f"glue/cell/{cell_id}/state"
    @staticmethod
    def glue_type(cell_id: int) -> str: return f"glue/cell/{cell_id}/glue_type"


class SystemTopics:
    APPLICATION_STATE  = "system/application_state"
    SYSTEM_MODE_CHANGE = "system/mode_change"
    COMMAND_CLEAN      = "glue/command/clean"
    COMMAND_RESET      = "glue/command/reset_errors"


class ApplicationState:
    IDLE         = "idle"
    STARTED      = "started"
    PAUSED       = "paused"
    INITIALIZING = "initializing"
    CALIBRATING  = "calibrating"
    STOPPED      = "stopped"
    ERROR        = "error"


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
    ApplicationState.IDLE:         {"start": True,  "stop": False, "pause": False, "pause_text": "Pause"},
    ApplicationState.STARTED:      {"start": False, "stop": True,  "pause": True,  "pause_text": "Pause"},
    ApplicationState.PAUSED:       {"start": False, "stop": True,  "pause": True,  "pause_text": "Resume"},
    ApplicationState.INITIALIZING: {"start": False, "stop": False, "pause": False, "pause_text": "Pause"},
    ApplicationState.CALIBRATING:  {"start": False, "stop": False, "pause": False, "pause_text": "Pause"},
    ApplicationState.STOPPED:      {"start": False, "stop": False, "pause": False, "pause_text": "Pause"},
    ApplicationState.ERROR:        {"start": False, "stop": True,  "pause": False, "pause_text": "Pause"},
}

MODE_TOGGLE_LABELS = ("Pick And Spray", "Spray Only")