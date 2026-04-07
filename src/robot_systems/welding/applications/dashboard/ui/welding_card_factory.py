from __future__ import annotations

from pl_gui.dashboard.config import CardConfig

from src.robot_systems.welding.applications.dashboard.ui.welding_status_card import (
    WeldingStatusCard,
)


class WeldingCardFactory:
    def build_cards(self, card_configs: list[CardConfig]) -> list[tuple]:
        return [
            (
                WeldingStatusCard(cfg.label),
                cfg.card_id,
                getattr(cfg, "row", 0),
                getattr(cfg, "col", 0),
            )
            for cfg in card_configs
        ]

