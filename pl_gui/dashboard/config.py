from dataclasses import dataclass, field


@dataclass
class DashboardConfig:
    trajectory_width: int = 800
    trajectory_height: int = 450
    card_min_height: int = 75
    card_grid_rows: int = 3
    card_grid_cols: int = 1
    card_grid_min_width: int = 350
    card_grid_max_width: int = 450
    display_fps_ms: int = 30
    trajectory_trail_length: int = 100
    action_grid_rows: int = 2
    action_grid_cols: int = 2
    bottom_section_height: int = 300
    preview_aux_rows: int = 2
    preview_aux_cols: int = 3
    show_placeholders: bool = True

@dataclass
class ActionButtonConfig:
    action_id: str
    label: str
    font_size: int = 20
    enabled: bool = True
    row: int | None = None
    col: int | None = None
    row_span: int = 1
    col_span: int = 1


@dataclass
class CardConfig:
    card_id: int
    label: str
    row: int | None = None
    col: int | None = None
