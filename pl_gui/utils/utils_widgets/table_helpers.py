"""
table_helpers — shared QTableWidget factory for application views.

Eliminates the ~8-line table-construction boilerplate + duplicated stylesheet
that appeared identically in tool_settings, user_management, workpiece_library,
broker_debug, and contour_matching_tester views.

Usage::

    from pl_gui.utils.utils_widgets.table_helpers import make_table

    # Simple — all columns stretch equally
    self._table = make_table(["Name", "Role", "Status"],
                             min_height=200)
    self._table.horizontalHeader().setSectionResizeMode(
        QHeaderView.ResizeMode.Stretch)
    layout.addWidget(self._table)

    # Custom column widths — caller configures the header after make_table()
    self._table = make_table(["Topic", "Subs", "Actions"],
                             fixed_height=280)
    hdr = self._table.horizontalHeader()
    hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
    self._table.setColumnWidth(1, 90)
"""
from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QTableWidget


# ── Shared stylesheet ─────────────────────────────────────────────────────────
#
# Matches the app's light theme: white background, purple (#905BA9) accent,
# #E0E0E0 border, EDE7F6 header.  Apply via make_table() or import directly
# when you need to style a table that has special construction needs.

TABLE_STYLE = """
QTableWidget {
    background: white;
    border: 1px solid #E0E0E0;
    border-radius: 6px;
    gridline-color: #F0F0F0;
    font-size: 9pt;
    alternate-background-color: #F8F9FA;
}
QHeaderView::section {
    background: #EDE7F6;
    color: #1A1A2E;
    font-weight: bold;
    font-size: 9pt;
    padding: 6px 4px;
    border: none;
    border-bottom: 1px solid #D0C8E0;
}
QTableWidget::item { padding: 4px; }
QTableWidget::item:selected {
    background: rgba(144, 91, 169, 0.15);
    color: #1A1A2E;
}
"""


def make_table(
    headers: list[str],
    *,
    alternate_rows: bool = True,
    hide_vertical_header: bool = True,
    sortable: bool = False,
    min_height: Optional[int] = None,
    fixed_height: Optional[int] = None,
) -> QTableWidget:
    """
    Build a pre-configured ``QTableWidget`` matching the app visual style.

    The caller is responsible for setting column resize modes after this call —
    that part always varies per table, so ``make_table()`` does not abstract it.

    Parameters
    ----------
    headers:
        Column header labels.  ``setColumnCount`` is derived from this list.
    alternate_rows:
        Enable alternating row colors (default ``True``).
    hide_vertical_header:
        Hide the left-side row-number header (default ``True``).
    sortable:
        Enable column-header click sorting (default ``False``).
    min_height:
        If provided, calls ``setMinimumHeight``.
    fixed_height:
        If provided, calls ``setFixedHeight`` (overrides *min_height*).
    """
    table = QTableWidget()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(alternate_rows)
    table.setSortingEnabled(sortable)
    table.setStyleSheet(TABLE_STYLE)

    if hide_vertical_header:
        table.verticalHeader().setVisible(False)
    if fixed_height is not None:
        table.setFixedHeight(fixed_height)
    elif min_height is not None:
        table.setMinimumHeight(min_height)

    return table
