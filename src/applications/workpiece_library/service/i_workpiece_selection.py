"""Optional selection contract for a workpiece library."""

from __future__ import annotations

from typing import Protocol


class IWorkpieceSelection(Protocol):
    def get_selected_ids(self) -> tuple[str, ...] | None:
        """Return selected storage IDs, or None when all are selected."""

    def set_selected_ids(self, ids: tuple[str, ...] | None) -> None:
        """Save selected IDs; an empty tuple selects none, None selects all."""
