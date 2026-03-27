from __future__ import annotations

from pl_gui.dashboard.config import CardConfig

from src.robot_systems.paint.applications.dashboard.ui.paint_status_card import (
    PaintStatusCard,
)


class PaintCardFactory:
    def build_cards(self, card_configs: list[CardConfig]) -> list[tuple]:
        return [
            (
                PaintStatusCard(cfg.label),
                cfg.card_id,
                getattr(cfg, "row", 0),
                getattr(cfg, "col", 0),
            )
            for cfg in card_configs
        ]

