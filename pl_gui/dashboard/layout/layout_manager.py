from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLabel, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt
from typing import List

from pl_gui.utils.utils_widgets.MaterialButton import MaterialButton

try:
    from pl_gui.dashboard.resources.styles import BORDER, SLOT_PLACEHOLDER_STYLE
except ImportError:
    try:
        from dashboard.styles import BORDER, SLOT_PLACEHOLDER_STYLE
    except ImportError:
        BORDER = "#E4E6F0"
        SLOT_PLACEHOLDER_STYLE = "QFrame { border: 2px dashed #E4E6F0; border-radius: 12px; }"


class DashboardLayoutManager:
    def __init__(self, parent_widget: QWidget, config):
        self.parent = parent_widget
        self.config = config
        self.main_layout = QVBoxLayout(parent_widget)
        self.main_layout.setSpacing(15)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

    def setup_complete_layout(self, trajectory_widget, glue_cards: List[QWidget],
                              control_buttons: QWidget,
                              action_buttons: List[MaterialButton]) -> None:
        top_section = self._create_top_section(trajectory_widget, glue_cards)
        bottom_section = self._create_bottom_section(control_buttons, action_buttons)

        bottom_container = QWidget()
        bottom_container.setFixedHeight(self.config.bottom_section_height)
        bottom_container.setLayout(bottom_section)

        self.main_layout.addLayout(top_section, stretch=1)
        self.main_layout.addWidget(bottom_container)

    # ------------------------------------------------------------------ #
    #  Top section                                                         #
    # ------------------------------------------------------------------ #

    def _create_top_section(self, trajectory_widget, glue_cards: List[QWidget]) -> QHBoxLayout:
        top_section = QHBoxLayout()
        top_section.setSpacing(10)
        top_section.addWidget(self._create_preview_container(trajectory_widget), stretch=2)
        top_section.addWidget(self._create_glue_cards_container(glue_cards), stretch=1)
        return top_section

    def _create_preview_container(self, trajectory_widget) -> QWidget:
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(10)
        preview_layout.addWidget(trajectory_widget, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        preview_layout.addWidget(self._create_preview_aux_grid(), stretch=1)
        return preview_widget

    def _create_preview_aux_grid(self) -> QWidget:
        """Placeholder grid that fills the space below the trajectory widget."""
        rows = self.config.preview_aux_rows
        cols = self.config.preview_aux_cols

        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        grid = QGridLayout(container)
        grid.setSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)

        for r in range(rows):
            grid.setRowStretch(r, 1)
        for c in range(cols):
            grid.setColumnStretch(c, 1)

        if self.config.show_placeholders:
            for idx in range(rows * cols):
                r, c = divmod(idx, cols)
                grid.addWidget(self._create_placeholder("PreviewAux", r, c), r, c)

        return container

    def _create_glue_cards_container(self, cards: list) -> QWidget:
        """Place cards in a rows×cols grid.

        Each entry is a ``(widget, row_or_None, col_or_None)`` tuple.
        Explicit positions are placed first; remaining cards auto-fill in
        row-major order; empty cells become placeholders.
        """
        rows = self.config.card_grid_rows
        cols = self.config.card_grid_cols

        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        grid = QGridLayout(container)
        grid.setSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)

        for r in range(rows):
            grid.setRowStretch(r, 1)
        for c in range(cols):
            grid.setColumnStretch(c, 1)

        occupied: set[tuple[int, int]] = set()

        # Pass 1 — explicit positions
        auto_queue = []
        for entry in cards:
            widget, card_row, card_col = entry
            widget.setMinimumHeight(self.config.card_min_height)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            if card_row is not None and card_col is not None:
                grid.addWidget(widget, card_row, card_col)
                occupied.add((card_row, card_col))
            else:
                auto_queue.append(widget)

        # Pass 2 — auto-fill remaining cards, placeholders for empty cells
        free_cells = (
            (r, c)
            for r in range(rows)
            for c in range(cols)
            if (r, c) not in occupied
        )
        for r, c in free_cells:
            if auto_queue:
                grid.addWidget(auto_queue.pop(0), r, c)
            elif self.config.show_placeholders:
                grid.addWidget(self._create_placeholder("CardConfig", r, c), r, c)

        container.setMinimumWidth(self.config.card_grid_min_width)
        container.setMaximumWidth(self.config.card_grid_max_width)
        return container

    # ------------------------------------------------------------------ #
    #  Bottom section                                                      #
    # ------------------------------------------------------------------ #

    def _create_bottom_section(self, control_buttons: QWidget,
                               action_buttons: List[MaterialButton]) -> QHBoxLayout:
        bottom_section = QHBoxLayout()
        bottom_section.setSpacing(15)
        bottom_section.addWidget(self._create_action_grid(action_buttons), stretch=1)
        bottom_section.addWidget(control_buttons, stretch=1)
        return bottom_section

    def _create_action_grid(self, action_buttons: list) -> QWidget:
        """Place action buttons in a rows×cols grid where every cell is the same size.

        Each entry in *action_buttons* is a ``(widget, row_or_None, col_or_None, row_span, col_span)``
        tuple produced by ``DashboardWidget._prepare_action_buttons``.

        * Buttons with explicit (row, col) are placed first with their span values.
        * Buttons without a position are placed in the next available cell with their span.
        * Empty cells are filled with styled placeholder frames.
        """
        rows = self.config.action_grid_rows
        cols = self.config.action_grid_cols

        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        grid = QGridLayout(container)
        grid.setSpacing(10)
        grid.setContentsMargins(5, 5, 5, 5)

        for r in range(rows):
            grid.setRowStretch(r, 1)
        for c in range(cols):
            grid.setColumnStretch(c, 1)

        occupied: set[tuple[int, int]] = set()

        def mark_occupied(r: int, c: int, row_span: int, col_span: int):
            """Mark all cells occupied by a widget with the given span."""
            for dr in range(row_span):
                for dc in range(col_span):
                    if 0 <= r + dr < rows and 0 <= c + dc < cols:
                        occupied.add((r + dr, c + dc))

        # Pass 1 — place explicitly positioned buttons
        auto_queue = []
        for entry in action_buttons:
            widget, btn_row, btn_col, row_span, col_span = entry
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            if btn_row is not None and btn_col is not None:
                grid.addWidget(widget, btn_row, btn_col, row_span, col_span)
                mark_occupied(btn_row, btn_col, row_span, col_span)
            else:
                auto_queue.append((widget, row_span, col_span))

        # Pass 2 — auto-fill remaining buttons into free cells (row-major)
        def find_free_cell(needed_row_span: int, needed_col_span: int):
            """Find the first cell where a widget of given span fits."""
            for r in range(rows):
                for c in range(cols):
                    # Check if the top-left cell is free
                    if (r, c) in occupied:
                        continue
                    # Check if all cells in the span are free
                    can_fit = True
                    for dr in range(needed_row_span):
                        for dc in range(needed_col_span):
                            if r + dr >= rows or c + dc >= cols or (r + dr, c + dc) in occupied:
                                can_fit = False
                                break
                        if not can_fit:
                            break
                    if can_fit:
                        return r, c
            return None

        for widget, row_span, col_span in auto_queue:
            cell = find_free_cell(row_span, col_span)
            if cell:
                r, c = cell
                grid.addWidget(widget, r, c, row_span, col_span)
                mark_occupied(r, c, row_span, col_span)

        # Pass 3 — fill empty cells with placeholders
        if self.config.show_placeholders:
            for r in range(rows):
                for c in range(cols):
                    if (r, c) not in occupied:
                        grid.addWidget(self._create_placeholder("ActionButtonConfig", r, c), r, c)
                        occupied.add((r, c))

        return container

    def _create_placeholder(self, config_type: str = "", row: int = 0, col: int = 0) -> QFrame:
        placeholder_frame = QFrame()
        placeholder_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        placeholder_frame.setStyleSheet(SLOT_PLACEHOLDER_STYLE)

        layout = QVBoxLayout(placeholder_frame)
        layout.setContentsMargins(10, 10, 10, 10)

        if config_type:
            text = f"Configure Via\n{config_type}\nrow={row} col={col}"
            font_size = 11
        else:
            text = "+"
            font_size = 28

        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            f"color: #000000; font-size: {font_size}px; font-weight: 300; border: none; background: transparent;"
        )
        layout.addWidget(label)

        return placeholder_frame