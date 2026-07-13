from __future__ import annotations

from pl_gui.dashboard.config import CardConfig

from src.robot_systems.paint.applications.dashboard.ui.paint_info_card import (
    PaintInfoCard,
)


_MOCK_CARD_DATA = {
    1: ("Mock", "Mock Status", "Mock Text"),
    2: ("Mock", "Mock Status", "Mock Text"),
    3: ("Mock", "Mock Status", "Mock Text"),
}


class PaintCardFactory:
    def build_cards(self, card_configs: list[CardConfig]) -> list[tuple]:
        return [
            (
                self._build_card(cfg),
                cfg.card_id,
                getattr(cfg, "row", 0),
                getattr(cfg, "col", 0),
            )
            for cfg in card_configs
        ]

    @staticmethod
    def _build_card(cfg: CardConfig) -> PaintInfoCard:
        title, value, note = _MOCK_CARD_DATA.get(
            cfg.card_id,
            (cfg.label, "Ready", "Status available"),
        )
        return PaintInfoCard(title, value, note)
